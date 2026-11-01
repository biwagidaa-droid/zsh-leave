"""تنظیمات پایه. همه رازها فقط از Environment؛ هیچ مقدار واقعی در کد نیست."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None, required: bool = False) -> str:
    v = os.environ.get(name, default)
    if required and not v:
        raise RuntimeError(f"متغیر محیطی {name} تنظیم نشده است")
    return v


SECRET_KEY = env("ZSH_SECRET_KEY", required=True)
DEBUG = env("ZSH_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in env("ZSH_ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "rest_framework", "leave",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": env("ZSH_DB_NAME", "zsh"), "USER": env("ZSH_DB_USER", "zsh"),
    "PASSWORD": env("ZSH_DB_PASSWORD", required=True),
    "HOST": env("ZSH_DB_HOST", "db"), "PORT": env("ZSH_DB_PORT", "5432"),
    "ATOMIC_REQUESTS": False,   # تراکنش‌ها صریح و در لایه سرویس
}}
AUTH_PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]  # نیازمند argon2-cffi
LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_TZ = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {"user": "120/min", "anon": "20/min"},
}
