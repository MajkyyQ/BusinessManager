from django.contrib import admin
from django.urls import path, include, re_path
from core.soubory import media
from django.conf import settings
from django.contrib.auth import views as av
from core.prihlaseni import PrihlaseniForm
urlpatterns = [path("admin/", admin.site.urls),
    path("login/", av.LoginView.as_view(authentication_form=PrihlaseniForm), name="login"), path("logout/", av.LogoutView.as_view(), name="logout"),
    re_path(r"^media/(?P<path>.*)$", media),  # soubory jen pro přihlášené, s bezpečnostními hlavičkami (core/soubory.py)
    *[path(f"moduly/{m}/", include(f"moduly.{m}.urls")) for m in settings.MODULY if (settings.BASE_DIR / "moduly" / m / "urls.py").exists()],  # volitelné moduly
    path("", include("core.urls"))]
