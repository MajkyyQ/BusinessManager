from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.contrib.auth import views as av
urlpatterns = [path("admin/", admin.site.urls),
    path("login/", av.LoginView.as_view(), name="login"), path("logout/", av.LogoutView.as_view(), name="logout"),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),  # soubory jen pro přihlášené
    path("", include("core.urls"))]
