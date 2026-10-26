from pathlib import Path
import os
import sys

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,platform"
    ).split(",")
    if host.strip()
]

if not DEBUG and SECRET_KEY in {"", "dev-only-change-me"}:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a non-default value when DEBUG=False."
    )

# erp = API produit (8001). platform = console SaaS (8002), image Docker distincte.
APP_ROLE = os.getenv("APP_ROLE", "erp")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "apps.identity",
    "apps.tenancy",
    "apps.audit",
    "apps.ledger",
    "apps.platform",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.identity.middleware.SessionPolicyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.tenancy.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.platform_urls" if APP_ROLE == "platform" else "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# migrate / test / bootstrap : rôle propriétaire (superuser, BYPASSRLS).
# ERP runtime : muhimu_app (NOBYPASSRLS).
# Console platform : muhimu_platform (BYPASSRLS, NOSUPERUSER) — pas de GUC bypass.
_privileged = bool(
    {
        "migrate",
        "makemigrations",
        "flush",
        "showmigrations",
        "dbshell",
        "test",
        "bootstrap_demo",
        "collectstatic",
    }
    & set(sys.argv)
)
_db_user = os.getenv("POSTGRES_USER", "muhimu")
_db_password = os.getenv("POSTGRES_PASSWORD", "muhimu")
if not _privileged:
    if APP_ROLE == "platform":
        _db_user = os.getenv("POSTGRES_PLATFORM_USER", "muhimu_platform")
        _db_password = os.getenv(
            "POSTGRES_PLATFORM_PASSWORD",
            os.getenv("POSTGRES_APP_PASSWORD", _db_password),
        )
    else:
        _db_user = os.getenv("POSTGRES_APP_USER", _db_user)
        _db_password = os.getenv("POSTGRES_APP_PASSWORD", _db_password)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "muhimu"),
        "USER": _db_user,
        "PASSWORD": _db_password,
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        # RLS session vars must not leak across pooled connections.
        "CONN_MAX_AGE": 0,
        "ATOMIC_REQUESTS": False,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

AUTH_USER_MODEL = "identity.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Cookies distincts : une session ERP ne doit jamais ouvrir la console, et inversement.
if APP_ROLE == "platform":
    SESSION_COOKIE_NAME = "muhimu_platform_session"
    CSRF_COOKIE_NAME = "muhimu_platform_csrf"
else:
    SESSION_COOKIE_NAME = "muhimu_session"
    CSRF_COOKIE_NAME = "muhimu_csrf"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", not DEBUG)
# Durée absolue de session (défaut 12 h). Le cookie ne prolonge pas au-delà (SEC-SESSION-01).
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 12)) or str(60 * 60 * 12))
SESSION_EXPIRE_AT_BROWSER_CLOSE = _env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", True)
SESSION_SAVE_EVERY_REQUEST = _env_bool("SESSION_SAVE_EVERY_REQUEST", False)
# SEC-SESSION-01 — inactivité + plafond absolu (contrôle serveur, indépendant du sliding cookie).
SESSION_POLICY_ENABLED = _env_bool("SESSION_POLICY_ENABLED", True)
SESSION_IDLE_TIMEOUT_SECONDS = int(
    os.getenv("SESSION_IDLE_TIMEOUT_SECONDS", str(30 * 60)) or str(30 * 60)
)
SESSION_ABSOLUTE_TIMEOUT_SECONDS = int(
    os.getenv("SESSION_ABSOLUTE_TIMEOUT_SECONDS", str(SESSION_COOKIE_AGE)) or str(SESSION_COOKIE_AGE)
)
SESSION_IDLE_WARN_BEFORE_SECONDS = int(
    os.getenv("SESSION_IDLE_WARN_BEFORE_SECONDS", str(5 * 60)) or str(5 * 60)
)
SESSION_IDLE_NO_TOUCH_PREFIXES = (
    "/api/auth/me",
    "/api/auth/session",
    "/api/csrf",
    "/api/health",
)
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_AGE = 60 * 60 * 24 * 7
CSRF_FAILURE_VIEW = "config.csrf.csrf_failure"

# --- SEC-P0-01 : rate-limit login (Redis, fail-closed) ---
AUTH_LOGIN_RATE_LIMIT_ENABLED = _env_bool("AUTH_LOGIN_RATE_LIMIT_ENABLED", True)
# memory = tests isolés ; redis = runtime (défaut). Sous `manage.py test` → memory.
_default_throttle_backend = "memory" if "test" in sys.argv else "redis"
AUTH_LOGIN_THROTTLE_BACKEND = (
    os.getenv("AUTH_LOGIN_THROTTLE_BACKEND", _default_throttle_backend).strip().lower()
    or _default_throttle_backend
)
AUTH_LOGIN_MAX_ATTEMPTS_EMAIL = int(os.getenv("AUTH_LOGIN_MAX_ATTEMPTS_EMAIL", "5") or "5")
AUTH_LOGIN_MAX_ATTEMPTS_IP = int(os.getenv("AUTH_LOGIN_MAX_ATTEMPTS_IP", "40") or "40")
AUTH_LOGIN_WINDOW_SECONDS = int(os.getenv("AUTH_LOGIN_WINDOW_SECONDS", "600") or "600")
AUTH_LOGIN_LOCKOUT_SECONDS = int(os.getenv("AUTH_LOGIN_LOCKOUT_SECONDS", "900") or "900")
# Ne faire confiance à X-Real-IP / X-Forwarded-For que derrière un reverse proxy.
AUTH_TRUST_PROXY = _env_bool("AUTH_TRUST_PROXY", False)
AUTH_TRUSTED_PROXIES = os.getenv("AUTH_TRUSTED_PROXIES", "")


# HTTPS derrière reverse proxy (bêta / staging).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = _env_bool("DJANGO_USE_X_FORWARDED_HOST", True)
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000") or "0")
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

_frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3001,http://127.0.0.1:3001,"
    "http://localhost:3002,http://127.0.0.1:3002",
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _frontend_origins.split(",") if o.strip()]
# Origines localhost : développement uniquement (pas en bêta DEBUG=False).
if DEBUG:
    for _origin in (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ):
        if _origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(_origin)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-csrftoken",
    "x-organization-slug",
    "x-company-id",
]
CORS_EXPOSE_HEADERS = ["Content-Disposition"]
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO" if not DEBUG else "DEBUG"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "gunicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Namecheap Private Email : mail.privateemail.com, port 465 SSL ou 587 STARTTLS.
EMAIL_HOST = _env_str("EMAIL_HOST", "mail.privateemail.com")
EMAIL_PORT = int(_env_str("EMAIL_PORT", "465") or "465")
EMAIL_HOST_USER = _env_str("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _env_str("EMAIL_HOST_PASSWORD")
EMAIL_TIMEOUT = int(_env_str("EMAIL_TIMEOUT", "20") or "20")
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", EMAIL_PORT == 465)
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", EMAIL_PORT == 587)
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = _env_str(
    "DEFAULT_FROM_EMAIL",
    f"Muhimu <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else (
        "Muhimu <noreply@muhimu.local>" if DEBUG else "Muhimu <jp@muhimu.tech>"
    ),
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Comptes @muhimu.local : local uniquement. En production : STAFF_EMAIL (jp@muhimu.tech).
BOOTSTRAP_LOCAL_ACCOUNTS = _env_bool("BOOTSTRAP_LOCAL_ACCOUNTS", DEBUG)
STAFF_EMAIL = _env_str("STAFF_EMAIL")
STAFF_FULL_NAME = _env_str("STAFF_FULL_NAME", "Muhimu")
STAFF_PASSWORD = _env_str("STAFF_PASSWORD")
_email_backend = _env_str("EMAIL_BACKEND")
if _email_backend:
    EMAIL_BACKEND = _email_backend
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
ERP_PUBLIC_URL = os.getenv("ERP_PUBLIC_URL", "http://127.0.0.1:3001")
CONSOLE_PUBLIC_URL = os.getenv("CONSOLE_PUBLIC_URL", "http://127.0.0.1:3002")

# BETA-SCOPE-01 — restrictions périmètre bêta (sécurisé si DEBUG=0 sauf override explicite).
BETA_SCOPE_RESTRICT = _env_bool("BETA_SCOPE_RESTRICT", default=not DEBUG)


def _beta_feature_enabled(env_name: str) -> bool:
    raw = os.getenv(env_name)
    if raw is not None:
        return _env_bool(env_name, False)
    if BETA_SCOPE_RESTRICT:
        return False
    return True


BETA_FEATURES = {
    "consolidation": _beta_feature_enabled("BETA_FEATURES_CONSOLIDATION"),
    "class9_cage": _beta_feature_enabled("BETA_FEATURES_CLASS9_CAGE"),
    "esg": _beta_feature_enabled("BETA_FEATURES_ESG"),
    "escompte": _beta_feature_enabled("BETA_FEATURES_ESCOMPTE"),
}
