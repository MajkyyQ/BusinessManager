import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent


def _nacti_env(soubor):
    """Soubor .env (KLÍČ=hodnota) i při spuštění bez Dockeru. Proměnné prostředí mají přednost, Docker je předává sám."""
    try: data = soubor.read_bytes()
    except OSError: return
    radky = data.decode("utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig", errors="replace").splitlines()  # PowerShell „echo > .env“ ukládá UTF-16
    for r in radky:
        k, rovna, v = r.strip().partition("=")
        if rovna and k and not k.startswith("#"): os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _tajny_klic():
    """SECRET_KEY z .env; bez něj náhodný klíč uložený v souboru .secret_key (nikdy pevný klíč známý z repozitáře)."""
    if os.getenv("SECRET_KEY"): return os.environ["SECRET_KEY"]
    soubor = BASE_DIR / ".secret_key"
    try: return soubor.read_text(encoding="utf-8").strip()
    except OSError: pass
    import secrets
    klic = secrets.token_urlsafe(50)
    try: soubor.write_text(klic, encoding="utf-8")
    except OSError: pass  # složka jen pro čtení: klíč platí do restartu (přihlášení se pak obnoví)
    return klic


if os.getenv("BM_NENACITAT_ENV") != "1": _nacti_env(BASE_DIR / ".env")
SECRET_KEY = _tajny_klic()
DEBUG = os.getenv("DEBUG", "0") == "1"  # ladicí režim jen výslovně (DEBUG=1 v .env), jinak by chyba ukázala technické detaily
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
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "core.soubory.LimitNahravaniMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
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
# Omezení pokusů o přihlášení (core/prihlaseni.py): blokace se kontroluje před ověřením hesla
AUTHENTICATION_BACKENDS = ["core.prihlaseni.BlokacePrihlaseniBackend", "django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "login"; LOGIN_REDIRECT_URL = "/"; LOGOUT_REDIRECT_URL = "login"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
# Limit nahrávaných souborů v MB: jeden soubor a celé nahrání najednou (např. víc fotek), viz core/soubory.py
MAX_VELIKOST_SOUBORU_MB = int(os.getenv("MAX_VELIKOST_SOUBORU_MB", "50"))
MAX_VELIKOST_NAHRAVANI_MB = int(os.getenv("MAX_VELIKOST_NAHRAVANI_MB", "500"))
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
WHITENOISE_USE_FINDERS = True  # styly a skripty fungují i bez collectstatic (spuštění bez Dockeru s DEBUG=0)
# HTTPS=1 v .env, když aplikace běží za HTTPS (např. Caddy nebo nginx před ní): cookies jen přes šifrované spojení
if os.getenv("HTTPS") == "1":
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
