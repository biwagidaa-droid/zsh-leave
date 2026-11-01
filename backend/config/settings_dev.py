import os

from .settings_base import *  # noqa F401,F403

DEBUG = True
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("ZSH_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
CORS_ALLOW_ALL_ORIGINS = True

if os.environ.get("ZSH_USE_SQLITE") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
