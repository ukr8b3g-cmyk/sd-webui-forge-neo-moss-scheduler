"""Owned additions to Forge's scheduler registry; no sampler-class patch."""
import sys
import logging
from types import SimpleNamespace
from .core import MODES

IDS = ('moss_shift_scheduler', 'moss_curve_scheduler', 'moss_sigma_scheduler')
NAMES = dict(zip(IDS, MODES)) | dict(zip(MODES, MODES))
_entries = []
_active = False
_original = None
_guard = None
_error = None


def require(name):
    from modules import sd_schedulers
    mode = NAMES.get(name)
    entry = next((e for e in _entries if e.label == mode), None)
    if _error or entry is None or sd_schedulers.schedulers_map.get(name) is not entry or not any(x is entry for x in sd_schedulers.all_schedulers):
        raise ValueError('MOSS Scheduler [REGISTRY_UNAVAILABLE]: ' + str(_error or name))


def _adapter(mode):
    def calculate(n, sigma_min, sigma_max, inner_model, device):
        from .runtime import build_moss_sigmas, is_moss
        from modules import shared
        if not is_moss(SimpleNamespace(sd_model=shared.sd_model)):
            raise ValueError('MOSS Scheduler [MODEL_UNSUPPORTED]: MOSS-Image models only')
        return build_moss_sigmas(inner_model, mode, n).to(device)
    return calculate


def _register():
    global _active, _original, _guard, _error
    from modules import sd_schedulers as s, sd_samplers, shared
    _active = True
    if not _entries:
        _entries.extend(s.Scheduler(i, m, _adapter(m), need_inner_model=True) for i, m in zip(IDS, MODES))
    if _guard is None:
        _original = sd_samplers.get_sampler_and_scheduler
        original = _original
        def guarded(sampler_name, scheduler_name, *, convert_automatic=True):
            if _active and scheduler_name in NAMES:
                require(scheduler_name)
            return original(sampler_name, scheduler_name, convert_automatic=convert_automatic)
        for attribute in ('cache_clear', 'cache_info', 'cache_parameters'):
            if hasattr(original, attribute):
                setattr(guarded, attribute, getattr(original, attribute))
        _guard = guarded
        sd_samplers.get_sampler_and_scheduler = guarded
    owned = lambda value: any(value is e for e in _entries)
    reserved = {x.casefold() for x in NAMES}
    foreign = [e for e in s.all_schedulers + s.schedulers if not owned(e)]
    collisions = [e.label for e in foreign if any(str(n).casefold() in reserved for n in (e.name, e.label, *(e.aliases or [])))]
    collisions += [k for k, v in s.schedulers_map.items() if k.casefold() in reserved and not owned(v)]
    k = sys.modules.get('modules.sd_samplers_kdiffusion')
    table = getattr(k, 'k_diffusion_scheduler', {})
    collisions += [e.name for e in _entries if e.name in table and table[e.name] is not e.function]
    if collisions:
        _error = 'REGISTRY_CONFLICT: ' + ', '.join(collisions)
        return
    _error = None
    for e in _entries:
        if not any(x is e for x in s.all_schedulers):
            s.all_schedulers.append(e)
        visible = e.label not in shared.opts.hide_schedulers
        s.schedulers[:] = [x for x in s.schedulers if x is not e]
        if visible:
            s.schedulers.append(e)
        s.schedulers_map[e.name] = s.schedulers_map[e.label] = e
        k = sys.modules.get('modules.sd_samplers_kdiffusion')
        if isinstance(getattr(k, 'k_diffusion_scheduler', None), dict):
            k.k_diffusion_scheduler[e.name] = e.function
    _original.cache_clear()


def register():
    global _error
    try:
        _register()
    except (AttributeError, TypeError, KeyError, ValueError) as exc:
        unregister(keep_guard=True)
        _error = 'REGISTRY_UNAVAILABLE: ' + str(exc)
        logging.error('MOSS Scheduler: %s', _error)


def unregister(*, keep_guard=False):
    global _active, _guard
    from modules import sd_schedulers as s, sd_samplers
    _active = keep_guard
    for e in _entries:
        s.all_schedulers[:] = [x for x in s.all_schedulers if x is not e]
        s.schedulers[:] = [x for x in s.schedulers if x is not e]
        for name in (e.name, e.label):
            if s.schedulers_map.get(name) is e:
                del s.schedulers_map[name]
        k = sys.modules.get('modules.sd_samplers_kdiffusion')
        table = getattr(k, 'k_diffusion_scheduler', {})
        if table.get(e.name) is e.function:
            del table[e.name]
    if not keep_guard and sd_samplers.get_sampler_and_scheduler is _guard:
        sd_samplers.get_sampler_and_scheduler = _original
        _guard = None
    if _original:
        _original.cache_clear()
