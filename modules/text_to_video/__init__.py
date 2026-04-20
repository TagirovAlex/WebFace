"""
Text-to-Video module for WebFace.
Uses WAN 2.2 model for video generation.
"""

import os
import json
from modules import BaseModule, register_module


WORKFLOW_FILE = os.path.join(os.path.dirname(__file__), 'workflow.json')


@register_module('wan22_video', 'text-to-video', 'WAN')
class TextToVideoModule(BaseModule):
    """Text-to-video generation module using WAN 2.2"""

    name = "WAN 2.2 Video"
    description = "Генерация видео из текста с помощью WAN 2.2"
    type = "text-to-video"
    category = "video"

    default_width = 512
    default_height = 512
    min_width = 256
    max_width = 1024
    min_height = 256
    max_height = 1024
    size_step = 16

    default_duration = 4
    max_duration = 10

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

        width = kwargs.get('width', self.default_width)
        height = kwargs.get('height', self.default_height)
        duration = kwargs.get('duration', self.default_duration)
        seed = kwargs.get('seed')

        fps = 16
        frames = duration * fps

        for node_id, node in wf.items():
            if not isinstance(node, dict):
                continue

            class_type = node.get('class_type', '')

            if class_type in ('EmptyHunyuanLatentVideo', 'EmptyLatentVideo'):
                if 'inputs' in node:
                    node['inputs']['width'] = width
                    node['inputs']['height'] = height
                    if 'length' in node['inputs']:
                        node['inputs']['length'] = frames

            if class_type == 'CreateVideo':
                if 'inputs' in node:
                    node['inputs']['fps'] = fps

            if class_type in ('CLIPTextEncode', 'CLIPTextEncodeSDXL'):
                inputs = node.get('inputs', {})
                text = inputs.get('text', '')

                meta_title = node.get('_meta', {}).get('title', '').lower()

                if 'negative' in meta_title and negative_prompt:
                    inputs['text'] = negative_prompt
                elif 'positive' in meta_title or not negative_prompt:
                    inputs['text'] = prompt

        if seed is not None:
            for node_id, node in wf.items():
                if isinstance(node, dict):
                    class_type = node.get('class_type', '')
                    if class_type in ('KSampler', 'KSamplerAdvanced'):
                        inputs = node.get('inputs', {})
                        if 'seed' in inputs:
                            inputs['seed'] = seed
                        elif 'noise_seed' in inputs:
                            inputs['noise_seed'] = seed

        return wf

    def validate_params(self, **params) -> tuple[bool, str]:
        """Validate generation parameters"""
        width = params.get('width', self.default_width)
        height = params.get('height', self.default_height)
        duration = params.get('duration', self.default_duration)

        if not (self.min_width <= width <= self.max_width):
            return False, f"Ширина должна быть {self.min_width}-{self.max_width}"

        if not (self.min_height <= height <= self.max_height):
            return False, f"Высота должна быть {self.min_height}-{self.max_height}"

        if not (1 <= duration <= self.max_duration):
            return False, f"Длительность должна быть 1-{self.max_duration} секунд"

        if width % self.size_step != 0 or height % self.size_step != 0:
            return False, f"Размеры должны быть кратны {self.size_step}"

        return True, ""