import os

from .settings_test import *  # noqa: F401,F403

DATABASE_NAME = os.environ.get("ZSH_DB_NAME", "zsh_test")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DATABASE_NAME,
        "USER": os.environ.get("ZSH_DB_USER", "postgres"),
        "PASSWORD": os.environ.get("ZSH_DB_PASSWORD", "postgres"),
        "HOST": os.environ.get("ZSH_DB_HOST", "localhost"),
        "PORT": os.environ.get("ZSH_DB_PORT", "5432"),
        "TEST": {
            "NAME": os.environ.get("ZSH_TEST_DB_NAME", f"test_{DATABASE_NAME}"),
        },
    }
}
