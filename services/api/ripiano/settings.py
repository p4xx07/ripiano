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
    "archive.api_tokens.ApiTokenMiddleware",
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
RIPIANO_CONVERTER_URL = os.environ.get("RIPIANO_CONVERTER_URL", "")
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
# Shared cache (sign-in throttling) in the same Valkey as the queue when the stack provides it.
if os.environ.get("RIPIANO_BROKER_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                          "LOCATION": os.environ["RIPIANO_BROKER_URL"].rsplit("/", 1)[0] + "/1", "KEY_PREFIX": "ripiano"}}
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 3600
CELERY_TIMEZONE = "Europe/Rome"
CELERY_TASK_DEFAULT_QUEUE = "celery"
CELERY_TASK_ROUTES = {
    "archive.tasks.reclassify_owner": {"queue": "maintenance"},
    "archive.tasks.train_filing_model": {"queue": "maintenance"},
    "archive.tasks.train_filing_models": {"queue": "maintenance"},
    "archive.tasks.reclassify_filing_candidates": {"queue": "maintenance"},
    "archive.tasks.reclassify_tag_candidates": {"queue": "maintenance"},
    "archive.tasks.backup_archive": {"queue": "maintenance"},
    "archive.tasks.build_browse_export": {"queue": "maintenance"},
    "archive.tasks.reconcile_browse_exports": {"queue": "maintenance"},
    "archive.tasks.purge_document": {"queue": "maintenance"},
    "archive.tasks.reconcile_purge_jobs": {"queue": "maintenance"},
    "archive.tasks.purge_expired_trash": {"queue": "maintenance"},
    "archive.tasks.poll_mail_accounts": {"queue": "maintenance"},
    "archive.tasks.send_workflow_notifications": {"queue": "maintenance"},
    "archive.tasks.send_document_email": {"queue": "maintenance"},
    "archive.tasks.build_share_bundle": {"queue": "maintenance"},
    "archive.tasks.expire_share_bundles": {"queue": "maintenance"},
    "archive.tasks.run_scheduled_workflows": {"queue": "maintenance"},
    "archive.tasks.poll_mail_account": {"queue": "maintenance"},
}

RIPIANO_BACKUP_ROOT = Path(os.environ.get("RIPIANO_BACKUP_ROOT", "/backup"))
RIPIANO_BROWSE_RETENTION = max(1, int(os.environ.get("RIPIANO_BROWSE_RETENTION", "2")))
RIPIANO_BACKUP_HOUR = int(os.environ.get("RIPIANO_BACKUP_HOUR", "2"))
RIPIANO_BACKUP_MINUTE = int(os.environ.get("RIPIANO_BACKUP_MINUTE", "0"))
RIPIANO_BACKUP_RETENTION = max(1, int(os.environ.get("RIPIANO_BACKUP_RETENTION", "7")))
if not 0 <= RIPIANO_BACKUP_HOUR <= 23 or not 0 <= RIPIANO_BACKUP_MINUTE <= 59:
    raise RuntimeError("Backup hour and minute must be valid local times")

RIPIANO_MAX_UPLOAD_BYTES = int(os.environ.get("RIPIANO_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
# Optional Fernet key for stored mailbox secrets; otherwise derived from RIPIANO_SECRET_KEY.
RIPIANO_MAIL_KEY = os.environ.get("RIPIANO_MAIL_KEY", "")
RIPIANO_MAIL_OAUTH = {
    "gmail": (os.environ.get("RIPIANO_GMAIL_OAUTH_CLIENT_ID", ""), os.environ.get("RIPIANO_GMAIL_OAUTH_CLIENT_SECRET", "")),
    "outlook": (os.environ.get("RIPIANO_OUTLOOK_OAUTH_CLIENT_ID", ""), os.environ.get("RIPIANO_OUTLOOK_OAUTH_CLIENT_SECRET", "")),
}
RIPIANO_MAIL_POLL_MINUTES = max(1, int(os.environ.get("RIPIANO_MAIL_POLL_MINUTES", "5")))
# Paper workflows: separator sheets split scans, ASN labels number documents, TAG: codes add tags.
RIPIANO_BARCODES = os.environ.get("RIPIANO_BARCODES", "1") == "1"
RIPIANO_BARCODE_SEPARATOR = os.environ.get("RIPIANO_BARCODE_SEPARATOR", "PATCHT")
RIPIANO_BARCODE_ASN_PREFIX = os.environ.get("RIPIANO_BARCODE_ASN_PREFIX", "ASN")
RIPIANO_BARCODE_TAG_PREFIX = os.environ.get("RIPIANO_BARCODE_TAG_PREFIX", "TAG:")
RIPIANO_BARCODE_MAX_PAGES = max(1, int(os.environ.get("RIPIANO_BARCODE_MAX_PAGES", "100")))
RIPIANO_BARCODE_DPI = max(72, int(os.environ.get("RIPIANO_BARCODE_DPI", "200")))
# Optional outgoing mail for workflow emails.
EMAIL_HOST = os.environ.get("RIPIANO_SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("RIPIANO_SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("RIPIANO_SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("RIPIANO_SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("RIPIANO_SMTP_SECURITY", "starttls") == "starttls"
EMAIL_USE_SSL = os.environ.get("RIPIANO_SMTP_SECURITY", "starttls") == "ssl"
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = os.environ.get("RIPIANO_SMTP_FROM", "ripiano@localhost")
# Webhooks to LAN services (e.g. home automation) must be allowed explicitly.
RIPIANO_WEBHOOK_ALLOW_PRIVATE = os.environ.get("RIPIANO_WEBHOOK_ALLOW_PRIVATE", "0") == "1"
# Emailing documents from the app is off unless the operator turns it on (SMTP alone is not enough).
RIPIANO_DOCUMENT_EMAIL = os.environ.get("RIPIANO_DOCUMENT_EMAIL", "0") == "1"
RIPIANO_EMAIL_ATTACH_MAX_BYTES = int(os.environ.get("RIPIANO_EMAIL_ATTACH_MAX_BYTES", str(10 * 1024 * 1024)))
RIPIANO_OCR_LANGUAGES = os.environ.get("RIPIANO_OCR_LANGUAGES", "eng+ita")
