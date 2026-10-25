# Changelog

## Unreleased — 2026-10-25

- Removed the sampler-name allowlist. Sigma-based samplers exposing Forge's `get_sigmas` interface can use all three MOSS modes.
- DPM++ SDE and DPM++ 2M SDE remain recommendations, not mandatory choices.
- Retained an explicit interface error for timestep-only methods such as DDIM/PLMS; OFF restores their normal behavior.
- Added CPU checks with 19 installed solver entries across 342 mode/step/pass combinations per installation, using real Forge sampling methods and solver code with a stand-in denoiser.

## 0.9.0 — 2026-10-24

- Initial public Forge Neo port of ComfyUI-MOSS-Shift-Scheduler v0.9.
- Compact ON/OFF control with Shift / Curve / Sigma, initially OFF with Shift selected.
- ON uses the selected MOSS sigma schedule instead of the normal Schedule Type, for the current generation and HiRes pass.
- Japanese hover help for a Japanese WebUI locale; English for other locales.
- Added non-wrapping mode buttons with 4 px spacing and an explicit ON/OFF usage warning.
- Recommended starting range: 8–10 steps, CFG 3–5, model shift 5 and lora_latest strength 0.8.
  Personal starting point: 8 steps and CFG 5. These are adjustable preferences, not measured universal optima.
- Included the supplied control-row screenshot and bilingual documentation.
