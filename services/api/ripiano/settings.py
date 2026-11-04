import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("RIPIANO_SECRET_KEY", "development-only-change-me")
RIPIANO_SETUP_KEY = os.environ.get("RIPIANO_SETUP_KEY", "")
DEBUG = os.environ.get("RIPIANO_DEBUG") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("RIPIANO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]
PUBLIC_ORIGIN = os.environ.get("RIPIANO_PUBLIC_ORIGIN", "http://localhost:8000")
parsed_origin = urlparse(PUBLIC_ORIGIN)
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]

if not DEBUG:
    if SECRET_KEY == "development-only-change-me" or len(SECRET_KEY) < 32:
        raise RuntimeError("Set a strong RIPIANO_SECRET_KEY before production startup")
    if parsed_origin.scheme != "https":
        raise RuntimeError("RIPIANO_PUBLIC_ORIGIN must use HTTPS in production")
    if len(RIPIANO_SETUP_KEY) < 24:
        raise RuntimeError("Set a RIPIANO_SETUP_KEY of at least 24 characters before production startup")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "archive",
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
ROOT_URLCONF = "ripiano.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "ripiano.wsgi.application"

if os.environ.get("RIPIANO_DB_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("RIPIANO_DB_NAME", "ripiano"),
        "USER": os.environ.get("RIPIANO_DB_USER", "ripiano"),
        "PASSWORD": os.environ.get("RIPIANO_DB_PASSWORD", ""),
        "HOST": os.environ["RIPIANO_DB_HOST"],
        "PORT": os.environ.get("RIPIANO_DB_PORT", "5432"),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"]}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = Path(os.environ.get("RIPIANO_MEDIA_ROOT", BASE_DIR / "data"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CELERY_BROKER_URL = os.environ.get("RIPIANO_BROKER_URL", "redis://localhost:6379/0")
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 3600

RIPIANO_MAX_UPLOAD_BYTES = int(os.environ.get("RIPIANO_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
RIPIANO_OCR_LANGUAGES = os.environ.get("RIPIANO_OCR_LANGUAGES", "eng+ita")
