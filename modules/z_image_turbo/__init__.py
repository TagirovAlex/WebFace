"""
Z-Image-Turbo module for WebFace.
Fast image generation using Z-Image-Turbo model.
"""

import os
import json
from modules import BaseModule, ModuleRegistry, register_module


WORKFLOW_FILE = os.path.join(os.path.dirname(__file__), 'workflow.json')


@register_module('z_image_turbo', 'text-to-image', 'Z-Image')
class ZImageTurboModule(BaseModule):
    """Z-Image-Turbo fast generation module"""

    name = "Z-Image Turbo"
    description = "Быстрая генерация изображений с помощью Z-Image-Turbo"
    type = "text-to-image"
    category = "image"

    default_width = 1024
    default_height = 1024
    min_width = 256
    max_width = 2048
    min_height = 256
    max_height = 2048
    size_step = 64

    supports_negative_prompt = True
    supports_seed = True
    base_cost = 3  # Уменьшенная стоимость для Turbo модели

    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def get_workflow(self) -> dict:
        """Load workflow JSON from file"""
        if self._workflow is None:
            with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
                self._workflow = json.load(f)
        return self._workflow

    def prepare_workflow(self, workflow: dict, prompt: str, negative_prompt: str = "", **kwargs) -> dict:
        """Prepare workflow with parameters"""
        import copy
        wf = copy.deepcopy(workflow or self.get_workflow())

        width = kwargs.get('width', self.default_width)
        height = kwargs.get('height', self.default_height)
        seed = kwargs.get('seed')

        for node_id, node in wf.items():
            if isinstance(node, dict):
                if node.get('class_type') == 'EmptyLatentImage':
                    node['inputs']['width'] = width
                    node['inputs']['height'] = height

        for node_id, node in wf.items():
            if isinstance(node, dict) and 'inputs' in node:
                inputs = node['inputs']
                if node.get('class_type') == 'CLIPTextEncode':
                    title = str(node.get('_meta', {}) or {}).get('title', '').lower()
                    if 'positive' in title:
                        inputs['text'] = prompt
                    elif 'negative' in title:
                        inputs['text'] = negative_prompt or ""

        if seed is not None:
            for node_id, node in wf.items():
                if isinstance(node, dict) and node.get('class_type') in ('KSampler', 'KSamplerAdvanced'):
                    seed_key = 'noise_seed' if 'noise_seed' in node['inputs'] else 'seed'
                    node['inputs'][seed_key] = seed

        return wf

    def validate_params(self, **params) -> tuple[bool, str]:
        """Validate generation parameters"""
        width = params.get('width', self.default_width)
        height = params.get('height', self.default_height)

        if not (self.min_width <= width <= self.max_width):
            return False, f"Ширина должна быть {self.min_width}-{self.max_width}"

        if not (self.min_height <= height <= self.max_height):
            return False, f"Высота должна быть {self.min_height}-{self.max_height}"

        if width % self.size_step != 0 or height % self.size_step != 0:
            return False, f"Размеры должны быть кратны {self.size_step}"

        return True, ""