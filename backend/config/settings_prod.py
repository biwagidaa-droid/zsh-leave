from .settings_base import *  # noqa F401,F403

DEBUG = False
SECRET_KEY = env("ZSH_SECRET_KEY", required=True)
if env("ZSH_INVITATION_EXPOSE_DEV_LINKS", "0").lower() in {"1", "true", "yes", "on"}:
    raise RuntimeError("Development invitation links cannot be exposed in production.")
if (
    env("ZSH_EMAIL_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
    and not env("ZSH_PUBLIC_BASE_URL", "").startswith("https://")
):
    raise RuntimeError("ZSH_PUBLIC_BASE_URL must use HTTPS when invitation email is enabled.")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
ALLOWED_HOSTS = [host.strip() for host in env("ZSH_ALLOWED_HOSTS", "").split(",") if host.strip()]

if not ALLOWED_HOSTS:
    raise RuntimeError("ZSH_ALLOWED_HOSTS must be set in production.")

if len(SECRET_KEY) < 50:
    raise RuntimeError("ZSH_SECRET_KEY must contain at least 50 characters in production.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("ZSH_DB_NAME", "zsh"),
        "USER": env("ZSH_DB_USER", "postgres"),
        "PASSWORD": env("ZSH_DB_PASSWORD", required=True),
        "HOST": env("ZSH_DB_HOST", "db"),
        "PORT": env("ZSH_DB_PORT", "5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "zsh_cache",
    }
}
