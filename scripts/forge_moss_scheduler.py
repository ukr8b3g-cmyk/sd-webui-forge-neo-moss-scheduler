"""Compact always-on extension for Forge Neo; no startup installs or settings writes."""
from pathlib import Path
import sys
import logging

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

import gradio as gr
from modules import scripts, script_callbacks
from modules.infotext_utils import PasteField
from forge_moss_scheduler import runtime, registry
from forge_moss_scheduler.core import MODES


def on_paste(infotext, params):
    if runtime.normalize(params):
        gr.Warning("MOSS Scheduler: unknown saved mode; switched OFF")


def restored_enabled(params):
    enabled, mode, invalid = runtime.restore_controls(params)
    if invalid:
        logging.warning('MOSS Scheduler: unknown saved mode; switched OFF')
    return enabled


script_callbacks.on_infotext_pasted(on_paste)
registry.register()
script_callbacks.on_before_ui(registry.register)
script_callbacks.on_script_unloaded(registry.unregister)


class Script(scripts.Script):
    create_group = False
    sorting_priority = 65

    def title(self):
        return "MOSS Scheduler"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Row(variant="compact", elem_id=self.elem_id("row"), elem_classes=["forge-moss-scheduler"]):
            enabled = gr.Checkbox(False, label="MOSS Scheduler", container=False,
                                  scale=0, min_width=145)
            mode = gr.Radio(choices=list(zip(("Shift", "Curve", "Sigma"), MODES)),
                            value=MODES[0], label="MOSS Scheduler Mode", show_label=False,
                            container=False, scale=0, min_width=210,
                            elem_classes=["forge-moss-modes"])
        enabled_field, mode_field = PasteField(enabled, runtime.KEY), PasteField(mode, runtime.MODE_KEY)
        enabled_field.function = restored_enabled
        mode_field.function = lambda params: runtime.restore_controls(params)[1]
        self.infotext_fields = [enabled_field, mode_field]
        self.paste_field_names = [runtime.KEY, runtime.MODE_KEY]
        return [enabled, mode]

    def process(self, p, enabled=False, mode=MODES[0]):
        if not hasattr(p, runtime.STATE):
            runtime.capture_input(p, enabled, mode)

    def before_process(self, p, enabled=False, mode=MODES[0]):
        runtime.begin_batch(p)
        runtime.capture_input(p, enabled, mode)

    def before_process_batch(self, p, *args, **kwargs):
        runtime.begin_batch(p)

    def process_before_every_sampling(self, p, enabled=False, mode=MODES[0], **kwargs):
        runtime.install(p)
