"""Environment-driven project settings entry point."""

import os
from importlib import import_module

ENV = os.environ.get("ZSH_ENV", "development").lower()
MODULE_MAP = {
    "development": "config.settings_dev",
    "dev": "config.settings_dev",
    "testing": "config.settings_test",
    "test": "config.settings_test",
    "production": "config.settings_prod",
    "prod": "config.settings_prod",
}
settings_module = MODULE_MAP.get(ENV, "config.settings_dev")
module = import_module(settings_module)
globals().update({k: v for k, v in module.__dict__.items() if not k.startswith("__")})
