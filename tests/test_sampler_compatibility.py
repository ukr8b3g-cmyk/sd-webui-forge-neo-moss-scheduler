"""CPU smoke tests of installed Forge sampler code with a small stand-in denoiser.

Loads numerical code by AST so backend/model startup and device selection never run.
The actual txt2img/img2img methods pass MOSS sigmas into the installed solver functions.
This tests the adapter contract, not image quality or real model inference.
"""
import ast
from contextlib import redirect_stderr
import importlib.util
import inspect
import io
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = ""
import torch
import tqdm

ROOT = Path(__file__).resolve().parents[1]
FORGE = Path(os.environ["FORGE_NEO_ROOT"])
sys.path.insert(0, str(ROOT))
from forge_moss_scheduler import core, runtime


def no_cuda(*args, **kwargs):
    raise AssertionError("CPU compatibility test attempted CUDA initialization")


torch.cuda.init = torch.cuda._lazy_init = no_cuda
torch.cuda.is_available = lambda: False
torch.cuda.device_count = lambda: 0


def load_functions(path, env, names=None):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
             and (names is None or n.name in names)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)


class Denoiser:
    def __init__(self):
        predictor = types.SimpleNamespace(
            prediction_type="const", percent_to_sigma=lambda p: 1 - p,
            noise_scaling=lambda sigma, noise, latent, **kw: sigma * noise + (1 - sigma) * latent,
        )
        self.inner_model = types.SimpleNamespace(
            predictor=predictor,
            forge_objects=types.SimpleNamespace(unet=types.SimpleNamespace(
                model_options={"transformer_options": {}})),
        )
        self.calls = 0

    def __call__(self, x, sigma, **kwargs):
        self.calls += 1
        denoised = 0.2 * x / (1 + sigma.reshape(-1, 1, 1, 1))
        for hook in kwargs.get("model_options", {}).get("sampler_post_cfg_function", []):
            denoised = hook({"denoised": denoised, "uncond_denoised": denoised * 0.5})
        return denoised


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        packages = FORGE / "modules_forge/packages/k_diffusion"
        helpers = {"torch": torch}
        load_functions(packages / "utils.py", helpers, {"append_dims"})
        load_functions(FORGE / "backend/patcher/base.py", helpers, {"set_model_options_post_cfg_function"})
        sampling = types.ModuleType("k_diffusion.sampling")
        sampling.__dict__.update({"utils": types.SimpleNamespace(append_dims=helpers["append_dims"]),
                                  "set_model_options_post_cfg_function": helpers["set_model_options_post_cfg_function"]})
        tree = ast.parse((packages / "sampling.py").read_text(encoding="utf-8-sig"))
        # Only backend glue and heavyweight image utilities are replaced; all solver code is real.
        tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom)
                     and (n.module == "backend.patcher.base" or n.module is None))]
        exec(compile(tree, str(packages / "sampling.py"), "exec"), sampling.__dict__)
        cls.sampling = sampling
        k_module = types.ModuleType("k_diffusion")
        k_module.sampling = sampling
        cls.module_patch = patch.dict(sys.modules, {"k_diffusion": k_module, "k_diffusion.sampling": sampling})
        cls.module_patch.start()
        cls.addClassCleanup(cls.module_patch.stop)

        spec = importlib.util.spec_from_file_location("offline_unipc", FORGE / "modules/uni_pc/uni_pc.py")
        unipc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(unipc)
        extra = {"torch": torch, "tqdm": tqdm, "k_diffusion": k_module, "unipc_impl": unipc}
        load_functions(FORGE / "modules/sd_samplers_extra.py", extra)
        tree = ast.parse((FORGE / "modules/sd_samplers_kdiffusion.py").read_text(encoding="utf-8-sig"))
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "samplers_k_diffusion" for t in n.targets))
        registry = {"opts": types.SimpleNamespace(forbidden_knowledge=False),
                    "sd_samplers_extra": types.SimpleNamespace(**{n: extra[n] for n in ("restart_sampler", "sample_unipc")})}
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), "installed_registry", "exec"), registry)
        cls.entries = []
        for label, function, _, options in registry["samplers_k_diffusion"]:
            function = getattr(sampling, function) if isinstance(function, str) else function
            cls.entries.append((label, function, options))
        alter = ast.parse((FORGE / "modules_forge/forge_alter_samplers.py").read_text(encoding="utf-8-sig"))
        assignment = next(n for n in alter.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "samplers_data_alter" for t in n.targets))
        for call in assignment.value.elts:
            label, key = (ast.literal_eval(a) for a in call.args)
            options = next((o.copy() for name, _, o in cls.entries if name == label.removesuffix(" CFG++")), {})
            cls.entries.append((label, getattr(sampling, "sample_" + key), options))

        cls.opts = types.SimpleNamespace(img2img_fix_steps=False, img2img_extra_noise=0, sgm_noise_multiplier=False)
        common = {"opts": cls.opts}
        load_functions(FORGE / "modules/sd_samplers_common.py", common, {"setup_img2img_steps"})
        cls.common = types.ModuleType("modules.sd_samplers_common")
        cls.common.setup_img2img_steps = common["setup_img2img_steps"]
        env = {"torch": torch, "inspect": inspect, "opts": cls.opts, "sd_samplers_common": cls.common,
               "sampling_prepare": lambda *a, **kw: None, "sampling_cleanup": lambda *a: None}
        methods = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "KDiffusionSampler")
        for fn in methods.body:
            if isinstance(fn, ast.FunctionDef) and fn.name in ("sample", "sample_img2img"):
                exec(compile(ast.Module(body=[fn], type_ignores=[]), "installed_sampling_method", "exec"), env)
        cls.sampler_class = type("InstalledForgeMethods", (), {
            "sample": env["sample"], "sample_img2img": env["sample_img2img"],
            "get_sigmas": lambda self, p, n: torch.linspace(1, 0, n + 1),
        })

    def test_installed_solvers_all_modes_and_passes(self):
        self.assertEqual(len(self.entries), 19)
        cases = 0
        with redirect_stderr(io.StringIO()), patch.object(runtime, "is_moss", return_value=True), patch.dict(sys.modules, {"modules.sd_samplers_common": self.common}):
            for label, function, options in self.entries:
                for mode in core.MODES:
                    for steps in (8, 10):
                        for kind in ("txt2img", "img2img", "hires"):
                            with self.subTest(sampler=label, mode=mode, steps=steps, kind=kind):
                                torch.manual_seed(42)
                                denoiser = Denoiser()
                                sampler = self.sampler_class()
                                sampler.funcname = function  # Forge also stores callable solver functions here.
                                sampler.func = function
                                sampler.model_wrap_cfg = denoiser
                                sampler.model_wrap = types.SimpleNamespace(
                                    sigmas=torch.linspace(0.001, 1, 1000),
                                    inner_model=denoiser.inner_model, predictor=denoiser.inner_model.predictor)
                                sampler.config = types.SimpleNamespace(options=options)
                                sampler.s_min_uncond = 0
                                sampler.initialize = lambda p: {}
                                sampler.launch_sampling = lambda n, fn: fn()
                                sampler.add_infotext = lambda p: None
                                sampler.callback_state = lambda info: None
                                sampler.create_noise_sampler = lambda x, sigmas, p: lambda a, b: torch.randn_like(x)
                                p = types.SimpleNamespace(
                                    sampler=sampler, sd_model=denoiser.inner_model, steps=steps, cfg_scale=3,
                                    extra_generation_params={}, sampler_noise_scheduler_override=None,
                                    denoising_strength=0.5, is_hr_pass=kind == "hires")
                                runtime.capture(p, True, mode)
                                runtime.install(p)
                                x = torch.randn(1, 4, 2, 2)
                                if kind == "txt2img":
                                    result = sampler.sample(p, x, None, None)
                                    total = steps
                                else:
                                    result = sampler.sample_img2img(p, x, torch.randn_like(x), None, None)
                                    total, _ = self.common.setup_img2img_steps(p)
                                self.assertEqual(result.shape, x.shape)
                                self.assertEqual(result.device.type, "cpu")
                                self.assertTrue(torch.isfinite(result).all())
                                self.assertGreater(denoiser.calls, 0)
                                recorded = p.sd_model.forge_objects.unet.model_options["transformer_options"]["sampling_sigmas"]
                                self.assertTrue(torch.equal(recorded, core.MODE_HANDLERS[mode](sampler.model_wrap, total)))
                                self.assertEqual(p.extra_generation_params[runtime.MODE_KEY], mode)
                                self.assertNotIn(runtime.PATCH, vars(sampler))
                                self.assertNotIn("get_sigmas", vars(sampler))
                                self.assertFalse(torch.cuda.is_initialized())
                                cases += 1
        print(f"PASS: {len(self.entries)} installed solvers, {cases} mode/step/pass cases; CPU only")

    def test_timestep_interface_is_not_silently_ignored(self):
        path = FORGE / "modules/sd_samplers_timesteps.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CompVisSampler")
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name != "__init__"]
        env = {}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), "exec"), env)
        sampler = type("InstalledTimestepMethods", (), env)()
        p = types.SimpleNamespace(sampler=sampler)
        with patch.object(runtime, "is_moss", return_value=True):
            for method in ("sample", "sample_img2img"):
                runtime.capture(p, True, core.MODES[0])
                runtime.install(p)
                with self.assertRaisesRegex(ValueError, "no sigma-schedule interface"):
                    getattr(sampler, method)(p, None, None, None, None)
                self.assertNotIn(runtime.PATCH, vars(sampler))
                self.assertNotIn("sample", vars(sampler))


if __name__ == "__main__":
    unittest.main(verbosity=2)
