"""Request-local Forge adapter. Never patches classes, settings or registry lists."""
from types import MethodType

import torch

from . import VERSION
from .core import MODE_HANDLERS

SUPPORTED = {"sample_dpmpp_sde", "sample_dpmpp_2m_sde", "sample_er_sde", "sample_euler"}
KEY = "MOSS Scheduler"
MODE_KEY = "MOSS Scheduler Mode"
STATE = "_forge_moss_scheduler_request"
PATCH = "_forge_moss_scheduler_patch"


def normalize(params):
    """Normalize PNG/Send-to data; missing data must clear previous ON state."""
    enabled = params.get(KEY, False)
    enabled = enabled is True or (isinstance(enabled, str) and enabled.lower() == "true")
    mode = params.get(MODE_KEY, "MOSS Shift Scheduler")
    invalid = mode not in MODE_HANDLERS
    if invalid:
        enabled, mode = False, "MOSS Shift Scheduler"
    params[KEY], params[MODE_KEY] = enabled, mode
    return invalid


def capture(p, enabled, mode):
    # bool('False') is True, so accept only real booleans from the UI/API.
    setattr(p, STATE, (enabled, mode))


def is_moss(p):
    from backend.diffusion_engine.moss_image import MOSSImage
    return isinstance(p.sd_model, MOSSImage)


def install(p):
    sampler = p.sampler
    previous = getattr(sampler, PATCH, None)
    if previous:
        previous()
    enabled, mode = getattr(p, STATE, (False, "MOSS Shift Scheduler"))
    if enabled is False:
        return
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

    def replace(name, function):
        originals[name] = (name in vars(sampler), vars(sampler).get(name))
        bound = MethodType(function, sampler)
        replacements[name] = bound
        setattr(sampler, name, bound)

    def check(request):
        if request is not p:
            raise RuntimeError("MOSS Scheduler: generation ownership mismatch")
        if enabled is not True or mode not in MODE_HANDLERS:
            raise ValueError("MOSS Scheduler: invalid enabled value or mode")
        if not is_moss(p):
            raise ValueError("MOSS Scheduler: MOSS-Image models only; turn OFF for other models")
        if getattr(sampler, "funcname", None) not in SUPPORTED or not callable(getattr(sampler, "get_sigmas", None)):
            raise ValueError("MOSS Scheduler: use DPM++ SDE, DPM++ 2M SDE, ER SDE or Euler")
        if getattr(p, "sampler_noise_scheduler_override", None) is not None:
            raise ValueError("MOSS Scheduler: another sigma override is active; disable one override")

    def make_guard(original, img2img):
        def guard(self, request, *args, **kwargs):
            try:
                check(request)
                cut = None
                if img2img:
                    from modules.sd_samplers_common import setup_img2img_steps
                    # sample_img2img's optional steps follows four positional inputs.
                    steps_arg = kwargs.get("steps", args[4] if len(args) > 4 else None)
                    total, t_enc = setup_img2img_steps(p, steps_arg)
                    cut = total - t_enc - 1

                def get_sigmas(self, request, steps):
                    check(request)
                    if not isinstance(steps, int) or steps < 1:
                        raise ValueError("MOSS Scheduler: steps must be a positive integer")
                    sigmas = MODE_HANDLERS[mode](self.model_wrap, steps).cpu()
                    if (sigmas.ndim != 1 or len(sigmas) < 2
                            or not torch.isfinite(sigmas).all() or sigmas[-1] != 0
                            or not (sigmas[:-1] > 0).all()
                            or not (sigmas[:-1] >= sigmas[1:]).all()):
                        raise ValueError("MOSS Scheduler: invalid model sigma table/result")
                    if cut is not None and len(sigmas[cut:]) < 2:
                        raise ValueError("MOSS Scheduler: denoise leaves no sampling interval; reduce steps or increase denoise")
                    params = p.extra_generation_params
                    params.update({KEY: True, MODE_KEY: mode, "MOSS Scheduler Version": VERSION})
                    prefix = "MOSS Hires" if getattr(p, "is_hr_pass", False) else "MOSS"
                    params[prefix + " Schedule steps"] = steps
                    params[prefix + " Schedule intervals"] = len(sigmas) - 1
                    return sigmas

                replace("get_sigmas", get_sigmas)
                return original(request, *args, **kwargs)
            finally:
                restore()
        return guard

    # Exceptions here are not used as the validation path: Forge swallows script
    # callback exceptions. The guards above execute inside the sampling call.
    for name in ("sample", "sample_img2img"):
        original = getattr(sampler, name, None)
        if callable(original):
            replace(name, make_guard(original, name == "sample_img2img"))
    setattr(sampler, PATCH, restore)
