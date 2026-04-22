"""
Image Edit Single module for WebFace.
Uses Qwen for single image editing.
"""

import os
import json
from modules import BaseModule, register_module


WORKFLOW_FILE = os.path.join(os.path.dirname(__file__), 'workflow.json')


@register_module('qwen_single', 'image-edit', 'Qwen')
class ImageEditSingleModule(BaseModule):
    """Single image edit module using Qwen"""

    name = "Qwen Single Edit"
    description = "Редактирование одного изображения с помощью Qwen"
    type = "image-edit"
    category = "edit"

    min_width = 256
    max_width = 2048
    min_height = 256
    max_height = 2048
    size_step = 8

    max_images = 1
    supports_negative_prompt = True

    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def get_workflow(self) -> dict:
        if self._workflow is None:
            with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
                self._workflow = json.load(f)
        return self._workflow

    def prepare_workflow(self, workflow: dict, prompt: str, negative_prompt: str = "", **kwargs) -> dict:
        import copy
        wf = copy.deepcopy(workflow or self.get_workflow())

        input_images = kwargs.get('input_images', [])

        for node_id, node in wf.items():
            if not isinstance(node, dict):
                continue

            class_type = node.get('class_type', '')

            if class_type == 'LoadImage':
                if input_images and 'inputs' in node:
                    node['inputs']['image'] = input_images[0]

            if class_type in ('CLIPTextEncode', 'CLIPTextEncodeSDXL'):
                inputs = node.get('inputs', {})
                meta_title = node.get('_meta', {}).get('title', '').lower()

                if 'negative' in meta_title:
                    inputs['text'] = negative_prompt or ""
                elif 'positive' in meta_title:
                    inputs['text'] = prompt

        return wf

    def validate_params(self, **params) -> tuple[bool, str]:
        input_images = params.get('input_images', [])

        if not input_images:
            return False, "Необходимо загрузить изображение"

        if len(input_images) > self.max_images:
            return False, f"Максимум {self.max_images} изображение"

        return True, ""