from django.urls import path
from . import views as v
urlpatterns = [path("", v.plocha_home, name="dashboard"), path("zakazka/nova/", v.zakazka_nova, name="zakazka_nova"), path("zakazka/<int:pk>/stav/", v.stav_akce, name="stav_akce"), path("zarizeni/", v.zarizeni_prehled, name="zarizeni_prehled"),
    path("lookup/<slug:slug>/", v.lookup, name="lookup"), path("lookup/<slug:slug>/nove/", v.lookup_new, name="lookup_new"), path("dokumenty/", v.dokumenty, name="dokumenty"), path("kalendar/", v.kalendar, name="kalendar"),
    path("nastaveni/", v.nastaveni, name="nastaveni"), path("nastaveni/firma/", v.nastaveni_firma, name="nastaveni_firma"), path("nastaveni/zaloha/", v.nastaveni_zaloha, name="nastaveni_zaloha"),
    path("nabidka/z-zakazky/", v.nabidka_nova, name="nabidka_nova"), path("nabidka/nahled/", v.nabidka_nahled, name="nabidka_nahled"),
    path("plocha/", v.plocha_home, name="plocha_hledat"), path("plocha/<int:pk>/", v.plocha, name="plocha"),
    path("dokument/<str:typ>/<int:pk>/", v.dokument, name="dokument"),
    path("<slug:slug>/", v.lst, name="list"), path("<slug:slug>/novy/", v.edit, name="create"),
    path("<slug:slug>/<int:pk>/", v.detail, name="detail"), path("<slug:slug>/<int:pk>/upravit/", v.edit, name="edit"),
    path("<slug:slug>/<int:pk>/smazat/", v.delete, name="delete")]
