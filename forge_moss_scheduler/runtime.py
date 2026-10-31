"""Request-local Forge adapter. Never patches classes, settings or registry lists."""
from types import MethodType

import torch

from . import VERSION
from .core import MODE_HANDLERS
from . import registry

KEY = "MOSS Scheduler"
MODE_KEY = "MOSS Scheduler Mode"
STATE = "_forge_moss_scheduler_request"
PATCH = "_forge_moss_scheduler_patch"
LEDGER = "_forge_moss_scheduler_metadata"


def restore_controls(params):
    enabled = params.get(KEY, False)
    enabled = enabled is True or (isinstance(enabled, str) and enabled.lower() == 'true')
    mode = params.get(MODE_KEY, 'MOSS Shift Scheduler')
    invalid = mode not in MODE_HANDLERS
    return (False, 'MOSS Shift Scheduler', True) if invalid else (enabled, mode, False)


def resolve_pass(primary, hires, enabled, mode, *, is_hr_pass=False):
    selected = primary if not is_hr_pass or hires in (None, '', 'Use same scheduler') else hires
    if type(enabled) is not bool:
        raise ValueError('MOSS Scheduler [INVALID_CONTROL]: enabled must be bool')
    if selected in registry.NAMES:
        return registry.NAMES[selected], 'dropdown'
    if enabled:
        if mode not in MODE_HANDLERS:
            raise ValueError('MOSS Scheduler [INVALID_CONTROL]: unknown mode')
        return mode, 'legacy'
    return None, 'native'


def begin_batch(p):
    for key, (existed, old, written) in getattr(p, LEDGER, {}).items():
        if p.extra_generation_params.get(key) == written:
            if existed:
                p.extra_generation_params[key] = old
            else:
                p.extra_generation_params.pop(key, None)
    setattr(p, LEDGER, {})


def record(p, values):
    ledger = getattr(p, LEDGER, {})
    for key, value in values.items():
        existed, old, _ = ledger.get(key, (key in p.extra_generation_params, p.extra_generation_params.get(key), None))
        ledger[key] = (existed, old, value)
        p.extra_generation_params[key] = value
    setattr(p, LEDGER, ledger)


def build_moss_sigmas(model_wrap, mode, steps):
    if type(steps) is not int or steps < 1:
        raise ValueError('MOSS Scheduler [INVALID_STEPS]: steps must be a positive integer')
    sigmas = MODE_HANDLERS[mode](model_wrap, steps).cpu()
    if (sigmas.dtype != torch.float32 or sigmas.ndim != 1 or len(sigmas) < 2
            or not torch.isfinite(sigmas).all() or sigmas[-1] != 0
            or not (sigmas[:-1] > 0).all() or not (sigmas[:-1] >= sigmas[1:]).all()):
        raise ValueError('MOSS Scheduler [INVALID_SIGMAS]: invalid model sigma table/result')
    return sigmas


def normalize(params):
    """Normalize PNG/Send-to data; missing data must clear previous ON state."""
    enabled, mode, invalid = restore_controls(params)
    params[KEY], params[MODE_KEY] = enabled, mode
    return invalid


def capture(p, enabled, mode):
    # bool('False') is True, so accept only real booleans from the UI/API.
    setattr(p, STATE, (enabled, mode))


def capture_input(p, enabled, mode):
    capture(p, enabled, mode)
    setattr(p, STATE + '_selection', (getattr(p, 'scheduler', None), getattr(p, 'hr_scheduler', None)))
    if getattr(p, 'hr_scheduler', None) in ('', 'Use same scheduler'):
        p.hr_scheduler = None
    elif getattr(p, 'hr_scheduler', None) in registry.NAMES:
        p.hr_scheduler = registry.NAMES[p.hr_scheduler]


def is_moss(p):
    from backend.diffusion_engine.moss_image import MOSSImage
    return isinstance(p.sd_model, MOSSImage)


def install(p):
    sampler = p.sampler
    previous = getattr(sampler, PATCH, None)
    if previous:
        if previous.owner is not p or previous.active:
            return  # Keep the installed guard: it rejects ownership/reentry itself.
        previous()
    enabled, mode = getattr(p, STATE, (False, "MOSS Shift Scheduler"))
    primary, hires = getattr(p, STATE + '_selection', (getattr(p, 'scheduler', None), getattr(p, 'hr_scheduler', None)))
    try:
        effective, source = resolve_pass(primary, hires, enabled, mode, is_hr_pass=getattr(p, 'is_hr_pass', False))
        error = None
    except ValueError as exc:
        effective, source, error = None, 'invalid', exc
    if effective is None and error is None:
        return
    lower_mode = mode if mode in MODE_HANDLERS else 'MOSS Shift Scheduler'
    mode = effective
    original_getter = getattr(sampler, 'get_sigmas', None)
    originals, replacements = {}, {}

    def restore():
        for name, replacement in replacements.items():
            if getattr(sampler, name, None) is replacement:
                existed, value = originals[name]
                if existed:
                    setattr(sampler, name, value)
                else:
                    delattr(sampler, name)
        if getattr(sampler, PATCH, None) is restore:
            delattr(sampler, PATCH)
    restore.owner, restore.active = p, False

    def replace(name, function):
        originals[name] = (name in vars(sampler), vars(sampler).get(name))
        bound = MethodType(function, sampler)
        replacements[name] = bound
        setattr(sampler, name, bound)

    def check(request):
        if request is not p:
            raise RuntimeError("MOSS Scheduler: generation ownership mismatch")
        if error is not None:
            raise error
        if source == 'dropdown':
            registry.require(mode)
        if not is_moss(p):
            raise ValueError("MOSS Scheduler [MODEL_UNSUPPORTED]: MOSS-Image models only; change this pass's schedule and turn the lower override OFF for other models")
        if not callable(getattr(sampler, "get_sigmas", None)):
            raise ValueError("MOSS Scheduler [SIGMA_INTERFACE_MISSING]: this sampler has no sigma-schedule interface (get_sigmas); use a sigma-based sampler or a non-MOSS schedule")
        if getattr(p, "sampler_noise_scheduler_override", None) is not None:
            raise ValueError("MOSS Scheduler [SIGMA_OVERRIDE_CONFLICT]: another sigma override is active; disable one override")
        if 'get_sigmas' in vars(sampler):
            raise ValueError('MOSS Scheduler [SIGMA_OVERRIDE_CONFLICT]: instance get_sigmas is already overridden')
        if getattr(sampler, 'get_sigmas', None) != original_getter:
            raise ValueError('MOSS Scheduler [SIGMA_OVERRIDE_CONFLICT]: get_sigmas changed after install')

    def make_guard(original, img2img):
        def guard(self, request, *args, **kwargs):
            if request is not p:
                raise RuntimeError('MOSS Scheduler [OWNER_MISMATCH]: generation ownership mismatch')
            if restore.active:
                raise RuntimeError('MOSS Scheduler [REENTRANT_SAMPLING]: recursive sampling')
            restore.active = True
            try:
                check(request)
                cut = None
                total = None
                calls = 0
                if img2img:
                    from modules.sd_samplers_common import setup_img2img_steps
                    # sample_img2img's optional steps follows four positional inputs.
                    steps_arg = kwargs.get("steps", args[4] if len(args) > 4 else None)
                    total, t_enc = setup_img2img_steps(p, steps_arg)
                    cut = total - t_enc - 1

                def get_sigmas(self, request, steps):
                    nonlocal calls
                    if request is not p:
                        raise RuntimeError('MOSS Scheduler [OWNER_MISMATCH]: generation ownership mismatch')
                    calls += 1
                    if calls != 1:
                        raise RuntimeError('MOSS Scheduler [SCHEDULE_CALLED_TWICE]: expected one schedule per sampling call')
                    if total is not None and steps != total:
                        raise ValueError('MOSS Scheduler [STEP_CONTRACT_MISMATCH]: img2img total changed')
                    sigmas = build_moss_sigmas(self.model_wrap, mode, steps)
                    if cut is not None and len(sigmas[cut:]) < 2:
                        raise ValueError("MOSS Scheduler [NO_SAMPLING_INTERVAL]: denoise leaves no sampling interval; reduce steps or increase denoise")
                    prefix = "MOSS Hires" if getattr(p, "is_hr_pass", False) else "MOSS"
                    values = {KEY: enabled, MODE_KEY: lower_mode, 'MOSS Scheduler Version': VERSION,
                              prefix + ' Schedule steps': steps, prefix + ' Schedule intervals': len(sigmas)-1,
                              prefix + ' Sampling intervals': len(sigmas[cut:])-1 if cut is not None else len(sigmas)-1,
                              'Hires schedule type' if getattr(p, 'is_hr_pass', False) else 'Schedule type': mode}
                    if getattr(p, 'is_hr_pass', False) and getattr(p, 'firstpass_image', None) is not None:
                        values['Schedule type'] = None
                    record(p, values)
                    return sigmas

                replace("get_sigmas", get_sigmas)
                result = original(request, *args, **kwargs)
                if calls != 1:
                    raise RuntimeError('MOSS Scheduler [NOT_APPLIED]: sampler did not use the schedule')
                return result
            finally:
                restore.active = False
                restore()
        return guard

    # Exceptions here are not used as the validation path: Forge swallows script
    # callback exceptions. The guards above execute inside the sampling call.
    for name in ("sample", "sample_img2img"):
        original = getattr(sampler, name, None)
        if callable(original):
            replace(name, make_guard(original, name == "sample_img2img"))
    setattr(sampler, PATCH, restore)
