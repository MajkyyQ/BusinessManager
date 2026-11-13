import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "dev-zmen-v-produkci")
DEBUG = os.getenv("DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "core", "django.forms"]
# Volitelné moduly: každá podsložka moduly/<kod>/ s apps.py se načte jako další aplikace (viz core/moduly.py a docs/11-moduly.md).
# MODULY_VYPNUTE=email,... v .env modul vypne bez smazání složky.
from core.moduly import najdi_moduly
MODULY = najdi_moduly(BASE_DIR, os.getenv("MODULY_VYPNUTE", ""))
INSTALLED_APPS += [f"moduly.{m}" for m in MODULY]
# Vlastní šablony formulářových prvků (core/templates/django/forms/...) mají přednost před vestavěnými.
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "core.pruvodce.PrvniSpusteniMiddleware", "django.contrib.auth.middleware.LoginRequiredMiddleware", "core.prava.PravaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "core.navigace.StopaMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "core.prava.kontext"]}}]
WSGI_APPLICATION = "config.wsgi.application"
# Výchozí SQLite (nic neinstalovat). PostgreSQL: nastavte DB_ENGINE=postgres (viz README)
if os.getenv("DB_ENGINE") == "postgres":
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("DB_NAME", "businessmanager"),
        "USER": os.getenv("DB_USER", "businessmanager"), "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"), "PORT": os.getenv("DB_PORT", "5432")}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
LANGUAGE_CODE = "cs"; TIME_ZONE = "Europe/Prague"; USE_I18N = True; USE_TZ = True
STATIC_URL = "static/"; STATIC_ROOT = BASE_DIR / "staticfiles"; MEDIA_URL = "media/"; MEDIA_ROOT = BASE_DIR / "media"
X_FRAME_OPTIONS = "SAMEORIGIN"  # PDF a dokumenty v pracovní ploše (iframe)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"; LOGIN_REDIRECT_URL = "/"; LOGOUT_REDIRECT_URL = "login"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
