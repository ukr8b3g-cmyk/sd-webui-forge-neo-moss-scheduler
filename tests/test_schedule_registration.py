"""CPU host contracts, with native Scheduler/PasteField exercised separately."""
import dataclasses
import ast
import functools
import itertools
import sys
import types
import unittest
from unittest.mock import patch
from test_extension import FakeSampler, FORGE
from typing import Callable
from forge_moss_scheduler import registry, runtime, core
import torch


tree = ast.parse((FORGE / 'modules/sd_schedulers.py').read_text(encoding='utf-8-sig'))
definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Scheduler')
exec(compile(ast.Module(body=[definition], type_ignores=[]), 'native_Forge_Scheduler', 'exec'))


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        registry._entries.clear(); registry._guard = None; registry._error = None
        @functools.cache
        def lookup(sampler, scheduler, *, convert_automatic=True):
            item = self.s.schedulers_map.get(scheduler)
            return sampler, item.label if item else 'Automatic'
        self.original = lookup
        self.s = types.SimpleNamespace(Scheduler=Scheduler, all_schedulers=[], schedulers=[], schedulers_map={})
        self.samplers = types.SimpleNamespace(get_sampler_and_scheduler=lookup)
        self.shared = types.SimpleNamespace(opts=types.SimpleNamespace(hide_schedulers=[]))
        self.secondary = types.SimpleNamespace(k_diffusion_scheduler={})
        host = types.ModuleType('modules')
        host.sd_schedulers, host.sd_samplers, host.shared = self.s, self.samplers, self.shared
        self.mock = patch.dict(sys.modules, {'modules': host, 'modules.sd_samplers_kdiffusion': self.secondary})
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.addCleanup(registry.unregister)

    def test_registration_hidden_cache_and_lifecycle(self):
        self.assertEqual(self.original('Euler', core.MODES[0])[1], 'Automatic')
        registry.register(); registry.register()
        self.assertEqual([e.label for e in self.s.schedulers], list(core.MODES))
        self.assertEqual(self.samplers.get_sampler_and_scheduler('Euler', registry.IDS[0])[1], core.MODES[0])
        self.shared.opts.hide_schedulers = [core.MODES[0]]
        registry.register()
        self.assertEqual(len(self.s.schedulers), 2)
        registry.require(registry.IDS[0])
        registry.unregister(); registry.register()
        self.assertEqual(len(self.s.all_schedulers), 3)

    def test_conflict_and_foreign_ownership(self):
        foreign = Scheduler('other', core.MODES[0], object())
        self.s.all_schedulers.append(foreign)
        registry.register()
        self.assertEqual(self.s.all_schedulers, [foreign])
        with self.assertRaisesRegex(ValueError, 'REGISTRY_'):
            self.samplers.get_sampler_and_scheduler('Euler', core.MODES[0])
        self.assertEqual(self.samplers.get_sampler_and_scheduler('Euler', 'Beta')[1], 'Automatic')
        self.s.all_schedulers.clear(); registry.register()
        self.s.schedulers_map[core.MODES[0]] = foreign
        registry.unregister()
        self.assertIs(self.s.schedulers_map[core.MODES[0]], foreign)

    def test_partial_registration_failure_rolls_back(self):
        class FailOnce(dict):
            def __setitem__(self, key, value):
                if key == registry.IDS[1]:
                    raise ValueError('simulated host failure')
                super().__setitem__(key, value)
        self.s.schedulers_map = FailOnce()
        registry.register()
        self.assertEqual(self.s.all_schedulers, [])
        self.assertEqual(self.s.schedulers, [])
        self.assertEqual(self.s.schedulers_map, {})
        with self.assertRaisesRegex(ValueError, 'REGISTRY_UNAVAILABLE'):
            self.samplers.get_sampler_and_scheduler('Euler',core.MODES[0])

    def test_native_hires_and_cancellation_are_isolated(self):
        registry.register()
        sampler = FakeSampler(torch.linspace(.001,1,1000))
        p = types.SimpleNamespace(sampler=sampler,scheduler=core.MODES[0],hr_scheduler='Automatic',is_hr_pass=True,
                                  steps=8,extra_generation_params={},sampler_noise_scheduler_override=None)
        runtime.capture_input(p,False,core.MODES[0])
        with patch.object(runtime,'is_moss',side_effect=AssertionError('native path checked model')):
            runtime.install(p)
            self.assertEqual(sampler.sample(p),'ordinary Forge scheduler')
        class Cancel(FakeSampler):
            def sample(self,p): raise KeyboardInterrupt()
        p.sampler = Cancel(sampler.model_wrap.sigmas); p.is_hr_pass=False
        with patch.object(runtime,'is_moss',return_value=True):
            runtime.install(p)
            with self.assertRaises(KeyboardInterrupt): p.sampler.sample(p)
        self.assertFalse(hasattr(p.sampler,runtime.PATCH))

    def test_inactive_guard_in_external_chain_does_not_recurse(self):
        registry.register()
        previous = self.samplers.get_sampler_and_scheduler
        def outside(*a, **kw): return previous(*a, **kw)
        outside.cache_clear = previous.cache_clear
        self.samplers.get_sampler_and_scheduler = outside
        registry.unregister()
        self.assertEqual(outside('Euler', core.MODES[0])[1], 'Automatic')
        registry.register()
        self.assertEqual(self.samplers.get_sampler_and_scheduler('Euler', core.MODES[0])[1], core.MODES[0])

    def test_selection_720_independent_cases(self):
        primary = [*registry.NAMES, 'Beta', 'Simple', 'Automatic', None, '', 'Karras']
        count = 0
        for main, hr, enabled, lower, is_hr in itertools.product(primary, [None, 'Use same scheduler', 'Automatic', 'Beta', core.MODES[2]], [False, True], core.MODES, [False, True]):
            selected = main if not is_hr or hr in (None, 'Use same scheduler') else hr
            expected = next((m for i, m in zip(registry.IDS, core.MODES) if selected in (i,m)), lower if enabled else None)
            self.assertEqual(runtime.resolve_pass(main, hr, enabled, lower, is_hr_pass=is_hr)[0], expected)
            count += 1
        self.assertEqual(count, 720)

    def test_dropdown_runtime_and_metadata(self):
        registry.register()
        sampler = FakeSampler(torch.linspace(.001, 1, 1000))
        p = types.SimpleNamespace(sampler=sampler, scheduler=core.MODES[1], hr_scheduler=core.MODES[2], is_hr_pass=False,
                                  steps=8, extra_generation_params={}, sampler_noise_scheduler_override=None)
        runtime.capture_input(p, False, core.MODES[0])
        with patch.object(runtime, 'is_moss', return_value=True):
            runtime.install(p)
            actual = sampler.sample(p)
            self.assertTrue(torch.equal(actual, core.MODE_HANDLERS[core.MODES[1]](sampler.model_wrap,8)))
            self.assertFalse(p.extra_generation_params[runtime.KEY])
            self.assertEqual(p.extra_generation_params[runtime.MODE_KEY], core.MODES[0])
            self.assertEqual(p.extra_generation_params['Schedule type'], core.MODES[1])
            p.is_hr_pass = True
            runtime.install(p); sampler.sample(p)
            self.assertEqual(p.extra_generation_params['Hires schedule type'], core.MODES[2])
            runtime.begin_batch(p)
            self.assertEqual(p.extra_generation_params, {})

    def test_owner_reentry_missing_and_duplicate_calls(self):
        registry.register()
        for action in ('missing','twice','recursive'):
            class Special(FakeSampler):
                def sample(self, p, *a, **kw):
                    if action == 'missing': return None
                    if action == 'recursive': return self.sample(p)
                    self.get_sigmas(p,8); return self.get_sigmas(p,8)
            sampler = Special(torch.linspace(.001,1,1000))
            p = types.SimpleNamespace(sampler=sampler, scheduler=core.MODES[0], steps=8, extra_generation_params={}, sampler_noise_scheduler_override=None)
            runtime.capture_input(p,False,core.MODES[0])
            with patch.object(runtime,'is_moss',return_value=True):
                runtime.install(p)
                with self.assertRaisesRegex(RuntimeError,'OWNER_MISMATCH'): sampler.sample(object())
                self.assertTrue(hasattr(sampler,runtime.PATCH))
                with self.assertRaisesRegex(RuntimeError,{'missing':'NOT_APPLIED','twice':'SCHEDULE_CALLED_TWICE','recursive':'REENTRANT'}[action]): sampler.sample(p)
                self.assertFalse(hasattr(sampler,runtime.PATCH))


if __name__ == '__main__': unittest.main()
