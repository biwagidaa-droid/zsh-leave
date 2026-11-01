from .settings_base import *  # noqa F401,F403

DEBUG = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
    }
}
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
