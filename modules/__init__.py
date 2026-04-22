"""
Module system for WebFace generation types.

Each module is a folder with:
- __init__.py    - Module registration
- workflow.json  - ComfyUI workflow
- config.py     - Module configuration
- handler.py    - Processing logic
"""

import os
import importlib
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseModule(ABC):
    """Base class for generation modules"""

    name: str = ""
    description: str = ""
    type: str = "text-to-image"  # text-to-image, text-to-video, image-edit
    category: str = ""

    # Default parameters
    default_width: int = 1024
    default_height: int = 1024
    min_width: int = 256
    max_width: int = 2048
    min_height: int = 256
    max_height: int = 2048
    size_step: int = 64

    # Supported features
    supports_negative_prompt: bool = True
    supports_seed: bool = True
    supports_batch: bool = False
    max_batch: int = 1

    def __init__(self, module_path: str):
        self.module_path = module_path
        self._workflow = None

    @abstractmethod
    def get_workflow(self) -> Dict[str, Any]:
        """Get ComfyUI workflow JSON"""
        pass

    @abstractmethod
    def prepare_workflow(self, workflow: Dict, prompt: str, negative_prompt: str, **kwargs) -> Dict:
        """Prepare workflow with user parameters"""
        pass

    @abstractmethod
    def validate_params(self, **params) -> tuple[bool, Optional[str]]:
        """Validate parameters, return (valid, error_message)"""
        pass

    def get_config(self) -> Dict[str, Any]:
        """Get module configuration"""
        return {
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'category': self.category,
            'default_width': self.default_width,
            'default_height': self.default_height,
            'min_width': self.min_width,
            'max_width': self.max_width,
            'min_height': self.min_height,
            'max_height': self.max_height,
            'size_step': self.size_step,
            'supports_negative_prompt': self.supports_negative_prompt,
            'supports_seed': self.supports_seed,
            'supports_batch': self.supports_batch,
            'max_batch': self.max_batch,
        }


class ModuleRegistry:
    """Registry for all generation modules"""

    _modules: Dict[str, BaseModule] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, module_id: str, module: BaseModule):
        """Register a module"""
        cls._modules[module_id] = module
        print(f"[MODULES] Registered: {module_id} - {module.name}")

    @classmethod
    def get(cls, module_id: str) -> Optional[BaseModule]:
        """Get module by ID"""
        return cls._modules.get(module_id)

    @classmethod
    def get_all(cls) -> Dict[str, BaseModule]:
        """Get all modules"""
        return cls._modules.copy()

    @classmethod
    def get_by_type(cls, gen_type: str) -> List[BaseModule]:
        """Get modules by generation type"""
        return [m for m in cls._modules.values() if m.type == gen_type]

    @classmethod
    def initialize(cls):
        """Auto-discover and load modules"""
        if cls._initialized:
            return

        modules_dir = os.path.dirname(__file__)

        # Scan for module packages
        for item in os.listdir(modules_dir):
            module_path = os.path.join(modules_dir, item)
            if os.path.isdir(module_path) and not item.startswith('_'):
                init_file = os.path.join(module_path, '__init__.py')
                if os.path.exists(init_file):
                    try:
                        module_name = f"modules.{item}"
                        importlib.import_module(module_name)
                    except Exception as e:
                        print(f"[MODULES] Failed to load {item}: {e}")

        cls._initialized = True
        print(f"[MODULES] Initialized {len(cls._modules)} modules")


# Decorator for registering modules
def register_module(module_id: str, module_type: str, category: str = ""):
    """Decorator to register a module"""
    def decorator(cls):
        cls.type = module_type
        cls.category = category
        ModuleRegistry.register(module_id, cls())
        return cls
    return decorator