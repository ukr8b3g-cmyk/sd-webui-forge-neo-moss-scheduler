# Third-party notices

Forge Neo port (2026-10-24): the unmodified `scheduler.py` from the user's
ComfyUI-MOSS-Shift-Scheduler v0.9 is included as `forge_moss_scheduler/core.py`.
SHA256: `1E74A759DDBADD6F571120DA95F5B74BD83CF4193DA07EC04CC32FF07119F139`.
Forge UI and request-local sampler adapters are new; ComfyUI registration code
is not loaded. The upstream notices below are preserved as provenance.

The port source is https://github.com/ukr8b3g-cmyk/ComfyUI-MOSS-Shift-Scheduler
at commit 6dcaa963d5cb78e4ae395f8edd08d9737efb4e71 (v0.9 source).
The same source is bundled as tests/reference/comfy_scheduler.py for CPU comparison.
Forge extension version 0.9.0 adds the Forge adapter, compact controls and locale-dependent
hover help. The supplied control-row screenshot is included with the repository owner's permission.

The Power Shift and Radiance Shift calculations are adapted from
silveroxides/ComfyUI_PowerShiftScheduler, Copyright (c) 2025 Silver, MIT License.

- Source: https://github.com/silveroxides/ComfyUI_PowerShiftScheduler
- Pinned commit: `770d7b8e4104b8d864d1fed0a65713e4a3e7a953`
- File: `__init__.py`, functions `power_shift_scheduler` and `radiance_shift_scheduler`.
- Full upstream license is included in `LICENSE`.
- The upstream README credits Clybius's InverserSquaredScheduler as inspiration.

Changes on 2026-10-24: isolated the two calculations from the MIT source,
added one independent node, two experimental mode wrappers, denoise tail selection,
and three namespaced Core scheduler registrations. No code was copied from the
AGPL UtilsCollection package. Its implementation is not a dependency.

Additional change on 2026-10-24: DMD uses a fractional grid offset of 0.75 to move
its timestep placement toward Radiance. The original compatibility mode and
Standard mode retain their calculations.

The reference source in `tests/reference/*.py.txt` is preserved as data for AST
extraction during CPU verification; its imports and registration code are not run.

Naming change on 2026-10-24: renamed the display to MOSS Shift Scheduler and
the modes to Balanced, Power and Offset. Balanced is the new-node default.
The calculations are unchanged. Added conversion of old workflow names on browser
load, and retained the node ID and legacy dedicated-node mode aliases.

MOSS Shift Scheduler is an unofficial extension. It is not endorsed by OpenMOSS or
the upstream scheduler author.

Final naming correction on 2026-10-24: the three choices in both selectors are
MOSS Shift Scheduler, MOSS Curve Scheduler and MOSS Sigma Scheduler, without abbreviations.
Calculations are unchanged; earlier mode and Core selector names migrate on workflow load.
