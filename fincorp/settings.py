import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROLE = os.getenv("FINCORP_ROLE", "control")
if ROLE not in ("control", "refunds"):
    raise RuntimeError("FINCORP_ROLE must be control or refunds")
SECRET_KEY = os.getenv("FINCORP_SECRET_KEY", "local-demo-only-change-for-nonlocal-use")
DEBUG = os.getenv("FINCORP_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    ROLE,
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
if ROLE == "refunds":
    MIDDLEWARE.insert(0, "refunds.middleware.ErrorCaptureMiddleware")
ROOT_URLCONF = "fincorp.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "fincorp.context.brand_context",
    ]},
}]
db_env = "FINCORP_CONTROL_DB" if ROLE == "control" else "FINCORP_REFUNDS_DB"
db_path = Path(os.getenv(db_env, BASE_DIR / ("control.sqlite3" if ROLE == "control" else "refunds.sqlite3")))
if not db_path.is_absolute():
    db_path = BASE_DIR / db_path
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(db_path), "OPTIONS": {"timeout": 15}}}
if ROLE == "refunds":
    DATABASES["default"]["TEST"] = {"NAME": str(BASE_DIR / ".runs/test_refunds.sqlite3")}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "SAMEORIGIN"
