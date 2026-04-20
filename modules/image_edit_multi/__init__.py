"""
Image Edit Multi module for WebFace.
Uses Qwen for multi image editing.
"""

import os
import json
from modules import BaseModule, register_module


WORKFLOW_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image_edit', 'qwen_edit_multi.json')


@register_module('qwen_multi', 'image-edit', 'Qwen')
class ImageEditMultiModule(BaseModule):
    """Multi image edit module using Qwen"""

    name = "Qwen Multi Edit"
    description = "Редактирование нескольких изображений с помощью Qwen"
    type = "image-edit"
    category = "edit"

    min_width = 256
    max_width = 2048
    min_height = 256
    max_height = 2048
    size_step = 8

    max_images = 4
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
                inputs = node.get('inputs', {})
                if 'image' in inputs:
                    idx = 0
                    for img in input_images:
                        if idx == 0:
                            inputs['image'] = img
                        elif f'image_{idx}' in inputs:
                            inputs[f'image_{idx}'] = img
                        idx += 1

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
            return False, "Необходимо загрузить хотя бы одно изображение"

        if len(input_images) > self.max_images:
            return False, f"Максимум {self.max_images} изображений"

        return True, ""