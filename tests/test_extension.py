import ast
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forge_moss_scheduler import core, runtime

FORGE = Path(os.environ.get("FORGE_NEO_ROOT", ROOT.parents[1]))
CANONICAL = Path(os.environ.get("MOSS_COMFY_SOURCE", ROOT / "tests/reference/comfy_scheduler.py"))


def extracted(path, name, env):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), env)
    return env[name]


class FakeSampler:
    funcname = "sample_dpmpp_sde"

    def __init__(self, table):
        self.model_wrap = types.SimpleNamespace(sigmas=table)

    def get_sigmas(self, p, steps):
        return "ordinary Forge scheduler"

    def sample(self, p, *args, **kwargs):
        return self.get_sigmas(p, p.steps)

    def sample_img2img(self, p, *args, **kwargs):
        from modules.sd_samplers_common import setup_img2img_steps
        n, t = setup_img2img_steps(p, kwargs.get("steps"))
        return self.get_sigmas(p, n)[n - t - 1:]


class Tests(unittest.TestCase):
    def setUp(self):
        self.table = torch.linspace(0.001, 1, 1000)
        self.p = types.SimpleNamespace(sampler=FakeSampler(self.table), steps=25,
                                      extra_generation_params={}, sampler_noise_scheduler_override=None,
                                      denoising_strength=0.5, is_hr_pass=False)
        self.moss = patch.object(runtime, "is_moss", return_value=True)
        self.moss_mock = self.moss.start()
        self.addCleanup(self.moss.stop)
        self.opts = types.SimpleNamespace(img2img_fix_steps=False)
        setup = extracted(FORGE / "modules/sd_samplers_common.py", "setup_img2img_steps", {"opts": self.opts})
        module = types.ModuleType("modules.sd_samplers_common")
        module.setup_img2img_steps = setup
        self.mods = patch.dict(sys.modules, {"modules.sd_samplers_common": module})
        self.mods.start()
        self.addCleanup(self.mods.stop)

    def enable(self, mode=core.MODES[0]):
        runtime.capture(self.p, True, mode)
        runtime.install(self.p)

    def test_exact_canonical_all_modes(self):
        spec = importlib.util.spec_from_file_location("canonical_scheduler", CANONICAL)
        reference = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference)
        for shift in (1., 3., 5.):
            x = torch.arange(1, 1001) / 1000
            model = types.SimpleNamespace(sigmas=shift * x / (1 + (shift - 1) * x))
            for steps in (1, 2, 3, 8, 20, 25, 50, 100, 1000):
                for mode in core.MODES:
                    with self.subTest(shift=shift, steps=steps, mode=mode):
                        self.assertTrue(torch.equal(core.MODE_HANDLERS[mode](model, steps),
                                                   reference.get_sigmas(model, mode, steps)))

    def test_off_untouched(self):
        runtime.capture(self.p, False, "invalid ignored while OFF")
        runtime.install(self.p)
        self.assertEqual(vars(self.p.sampler), {"model_wrap": self.p.sampler.model_wrap})
        self.assertEqual(self.p.sampler.sample(self.p), "ordinary Forge scheduler")
        self.assertEqual(self.p.extra_generation_params, {})

    def test_modes_and_repeated_requests(self):
        for mode in core.MODES:
            self.enable(mode)
            actual = self.p.sampler.sample(self.p)
            self.assertTrue(torch.equal(actual, core.MODE_HANDLERS[mode](self.p.sampler.model_wrap, 25)))
            self.assertNotIn("sample", vars(self.p.sampler))
            self.assertNotIn("get_sigmas", vars(self.p.sampler))
            self.assertEqual(self.p.extra_generation_params[runtime.MODE_KEY], mode)

    def test_idempotent_and_on_to_off(self):
        self.enable()
        runtime.install(self.p)
        runtime.capture(self.p, False, core.MODES[0])
        runtime.install(self.p)
        self.assertEqual(self.p.sampler.sample(self.p), "ordinary Forge scheduler")

    def test_errors_escape_sampling_not_callback(self):
        for kind in ("mode", "model", "sampler", "override", "enabled"):
            with self.subTest(kind=kind):
                self.setUp_request()
                if kind == "model":
                    self.moss_mock.return_value = False
                if kind == "sampler":
                    self.p.sampler.get_sigmas = None
                if kind == "override":
                    self.p.sampler_noise_scheduler_override = lambda n: None
                runtime.capture(self.p, "True" if kind == "enabled" else True,
                                "bad" if kind == "mode" else core.MODES[0])
                runtime.install(self.p)  # succeeds even if callback exceptions are swallowed
                with self.assertRaises(ValueError):
                    self.p.sampler.sample(self.p)
                self.assertNotIn(runtime.PATCH, vars(self.p.sampler))
                self.assertNotIn("sample", vars(self.p.sampler))
                self.moss_mock.return_value = True

    def test_sampler_names_and_callable_functions_are_not_restricted(self):
        for name in ("sample_dpmpp_2m", "sample_euler_ancestral", "sample_heun", "sample_lms",
                     "sample_dpm_2", "sample_res_multistep", "sample_lcm",
                     "sample_dpmpp_2m_cfg_pp", "future_custom_sampler", lambda *a: None, None):
            with self.subTest(name=name):
                self.setUp_request()
                self.p.sampler.funcname = name
                for mode in core.MODES:
                    self.enable(mode)
                    result = self.p.sampler.sample(self.p)
                    self.assertTrue(torch.equal(result, core.MODE_HANDLERS[mode](self.p.sampler.model_wrap, 25)))

    def test_missing_sigma_interface_errors_clearly_and_off_delegates(self):
        self.p.sampler.get_sigmas = None
        self.p.sampler.sample = lambda p: "timestep sampler"
        self.enable()
        with self.assertRaisesRegex(ValueError, "no sigma-schedule interface"):
            self.p.sampler.sample(self.p)
        self.assertEqual(self.p.sampler.sample(self.p), "timestep sampler")
        runtime.capture(self.p, False, core.MODES[0])
        runtime.install(self.p)
        self.assertEqual(self.p.sampler.sample(self.p), "timestep sampler")

    def setUp_request(self):
        self.p.sampler = FakeSampler(self.table)
        self.p.sampler_noise_scheduler_override = None

    def test_exception_cleanup_and_preserve_foreign_patch(self):
        def failing(p, *a, **k):
            self.p.sampler.get_sigmas = lambda p, n: "foreign"
            raise InterruptedError("cancel")
        self.p.sampler.sample = failing
        self.enable()
        with self.assertRaises(InterruptedError):
            self.p.sampler.sample(self.p)
        self.assertIs(self.p.sampler.sample, failing)
        self.assertEqual(self.p.sampler.get_sigmas(self.p, 1), "foreign")

    def test_native_img2img_hires(self):
        for hires in (False, True):
            for fixed in (False, True):
                self.opts.img2img_fix_steps = fixed
                self.p.is_hr_pass = hires
                self.enable(core.MODES[2])
                result = self.p.sampler.sample_img2img(self.p, steps=15 if hires else None)
                from modules.sd_samplers_common import setup_img2img_steps
                n, t = setup_img2img_steps(self.p, 15 if hires else None)
                expected = core.MODE_HANDLERS[core.MODES[2]](self.p.sampler.model_wrap, n)[n-t-1:]
                self.assertTrue(torch.equal(result, expected))

    def test_invalid_slice_and_invalid_table(self):
        self.p.steps = 1000
        self.p.denoising_strength = 0.01
        self.enable()
        with self.assertRaisesRegex(ValueError, "no sampling interval"):
            self.p.sampler.sample_img2img(self.p)
        self.p.sampler.model_wrap.sigmas[:] = float("nan")
        self.enable()
        with self.assertRaisesRegex(ValueError, "invalid model sigma"):
            self.p.sampler.sample(self.p)

    def test_info_roundtrip_and_missing(self):
        for mode in core.MODES:
            info = {runtime.KEY: "True", runtime.MODE_KEY: mode}
            self.assertFalse(runtime.normalize(info))
            self.assertIs(info[runtime.KEY], True)
            self.assertEqual(info[runtime.MODE_KEY], mode)
        for info in ({}, {runtime.KEY: "False"}, {runtime.KEY: "True", runtime.MODE_KEY: "obsolete"}):
            runtime.normalize(info)
            self.assertIs(info[runtime.KEY], False)

    def test_real_gradio_ui_and_script_hooks(self):
        import gradio as gr
        module = types.ModuleType("modules")
        module.scripts = types.SimpleNamespace(Script=type("Base", (), {"elem_id": lambda s, x: str(id(s))+x}), AlwaysVisible=object())
        callbacks = []
        module.script_callbacks = types.SimpleNamespace(on_infotext_pasted=callbacks.append)
        with patch.dict(sys.modules, {"modules": module}):
            spec = importlib.util.spec_from_file_location("test_ui_entry", ROOT / "scripts/forge_moss_scheduler.py")
            entry = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(entry)
            self.assertEqual(len(callbacks), 1)
            with gr.Blocks(analytics_enabled=False) as block:
                instances = [entry.Script(), entry.Script()]
                controls = [s.ui(i == 1) for i, s in enumerate(instances)]
            for enabled, mode in controls:
                self.assertFalse(enabled.value)
                self.assertEqual(mode.value, core.MODES[0])
                self.assertEqual([v for _, v in mode.choices], list(core.MODES))
            self.assertEqual(instances[0].paste_field_names, instances[1].paste_field_names)
            self.assertEqual(len([c for c in block.config["components"] if c["type"] == "row"]), 2)

    def test_actual_forge_get_sigmas_discard_and_off(self):
        tree = ast.parse((FORGE / "modules/sd_samplers_kdiffusion.py").read_text(encoding="utf-8-sig"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "KDiffusionSampler")
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "get_sigmas")
        opts = types.SimpleNamespace(always_discard_next_to_last_sigma=False, sigma_min=0, sigma_max=0, rho=0)
        scheduler = types.SimpleNamespace(label="Simple", default_rho=-1, need_inner_model=False,
                                        function=lambda n, **kw: torch.linspace(1, 0, n+1))
        env = {"torch": torch, "opts": opts,
               "sd_schedulers": types.SimpleNamespace(schedulers_map={"Simple": scheduler}),
               "devices": types.SimpleNamespace(cpu="cpu")}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "actual_forge_get_sigmas", "exec"), env)
        actual_class = type("ActualForgeGetter", (FakeSampler,), {"get_sigmas": env["get_sigmas"]})
        self.p.sampler = actual_class(self.table)
        self.p.sampler.config = types.SimpleNamespace(options={})
        self.p.scheduler = self.p.hr_scheduler = "Simple"
        for discard in (False, True):
            opts.always_discard_next_to_last_sigma = discard
            baseline = self.p.sampler.sample(self.p)
            for mode in core.MODES:
                self.enable(mode)
                result = self.p.sampler.sample(self.p)
                self.assertTrue(torch.equal(result, core.MODE_HANDLERS[mode](self.p.sampler.model_wrap, 25)))
                runtime.capture(self.p, False, mode)
                runtime.install(self.p)
                self.assertTrue(torch.equal(self.p.sampler.sample(self.p), baseline))
            self.assertEqual(opts.always_discard_next_to_last_sigma, discard)


if __name__ == "__main__":
    unittest.main(verbosity=2)
