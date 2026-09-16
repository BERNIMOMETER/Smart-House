from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured


def env_flag(name, default=False):
    """Read a conventional boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]

BASE_DIR = Path(__file__).resolve().parent.parent
_DEVELOPMENT_SECRET_KEY = "change-me-before-production"
DEBUG = env_flag("DJANGO_DEBUG", default=True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _DEVELOPMENT_SECRET_KEY)
if not DEBUG and (not SECRET_KEY or SECRET_KEY == _DEVELOPMENT_SECRET_KEY):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=0.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=0.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("DJANGO_CSRF_TRUSTED_ORIGINS must be set when DJANGO_DEBUG=0.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "house",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "smarthouse.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "smarthouse.wsgi.application"
ASGI_APPLICATION = "smarthouse.asgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # The dashboard and independent MQTT bridge are separate processes.
        # A small timeout avoids transient lock errors at their low write rate.
        "OPTIONS": {"timeout": 20},
    }
}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The Cloudflare Tunnel is the only public ingress and forwards the original
# HTTPS scheme to Gunicorn on loopback.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = env_flag("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = False

# MQTT connection details are deliberately environment based: never commit
# broker credentials. Production defaults to HiveMQ Cloud's TLS listener.
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost" if DEBUG else "").strip()
if not DEBUG and not MQTT_HOST:
    raise ImproperlyConfigured("MQTT_HOST must be set when DJANGO_DEBUG=0.")
MQTT_TLS = env_flag("MQTT_TLS", default=not DEBUG)
if not DEBUG and not MQTT_TLS:
    raise ImproperlyConfigured("MQTT_TLS must be enabled when DJANGO_DEBUG=0.")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "8883" if MQTT_TLS else "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
if not DEBUG and (not MQTT_USERNAME or not MQTT_PASSWORD):
    raise ImproperlyConfigured("MQTT_USERNAME and MQTT_PASSWORD must be set when DJANGO_DEBUG=0.")
MQTT_TLS_CA_CERTS = os.environ.get("MQTT_TLS_CA_CERTS", "").strip() or None
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "smarthouse-django").strip()
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "smarthouse").strip().strip("/")
if not MQTT_CLIENT_ID:
    raise ImproperlyConfigured("MQTT_CLIENT_ID must not be empty.")
if not MQTT_TOPIC_PREFIX or any(part in {"+", "#"} for part in MQTT_TOPIC_PREFIX.split("/")):
    raise ImproperlyConfigured("MQTT_TOPIC_PREFIX must be a non-empty concrete MQTT topic prefix.")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "house.mqtt": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
