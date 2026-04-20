"""
Text-to-Image module for WebFace.
Uses WAN 2.2 model for image generation.
"""

import os
import json
from modules import BaseModule, ModuleRegistry, register_module


WORKFLOW_FILE = os.path.join(os.path.dirname(__file__), 'workflow.json')


@register_module('wan22', 'text-to-image', 'WAN')
class TextToImageModule(BaseModule):
    """Text-to-image generation module using WAN 2.2"""

    name = "WAN 2.2"
    description = "Генерация изображений из текста с помощью WAN 2.2"
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

        # Update dimensions
        width = kwargs.get('width', self.default_width)
        height = kwargs.get('height', self.default_height)
        seed = kwargs.get('seed')

        # Update dimensions in workflow
        for node_id, node in wf.items():
            if isinstance(node, dict):
                if node.get('class_type') == 'EmptyLatentImage':
                    node['inputs']['width'] = width
                    node['inputs']['height'] = height

        # Update prompts - simplified version
        for node_id, node in wf.items():
            if isinstance(node, dict) and 'inputs' in node:
                inputs = node['inputs']
                if 'text' in inputs and isinstance(inputs.get('text'), str) is False:
                    # Skip if already set
                    pass
                elif node.get('class_type') == 'CLIPTextEncode':
                    if 'positive' in str(node.get('_meta', {}) or '').lower():
                        inputs['text'] = prompt
                    elif 'negative' in str(node.get('_meta', {}) or '').lower():
                        inputs['text'] = negative_prompt or ""

        # Set seed
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

        # Check dimensions
        if not (self.min_width <= width <= self.max_width):
            return False, f"Ширина должна быть {self.min_width}-{self.max_width}"

        if not (self.min_height <= height <= self.max_height):
            return False, f"Высота должна быть {self.min_height}-{self.max_height}"

        # Check step
        if width % self.size_step != 0 or height % self.size_step != 0:
            return False, f"Размеры должны быть кратны {self.size_step}"

        return True, ""