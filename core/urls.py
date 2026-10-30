from django.urls import path
from . import views as v
from . import views_sablony as vs
urlpatterns = [path("", v.plocha_home, name="dashboard"), path("zakazka/nova/", v.zakazka_nova, name="zakazka_nova"), path("zakazka/<int:pk>/stav/", v.stav_akce, name="stav_akce"), path("zarizeni/", v.zarizeni_prehled, name="zarizeni_prehled"),
    path("lookup/<slug:slug>/", v.lookup, name="lookup"), path("lookup/<slug:slug>/nove/", v.lookup_new, name="lookup_new"), path("dokumenty/", v.dokumenty, name="dokumenty"), path("kalendar/", v.kalendar, name="kalendar"),
    path("nastaveni/", v.nastaveni, name="nastaveni"), path("nastaveni/firma/", v.nastaveni_firma, name="nastaveni_firma"), path("nastaveni/zaloha/", v.nastaveni_zaloha, name="nastaveni_zaloha"),
    path("nabidka/z-zakazky/", v.nabidka_nova, name="nabidka_nova"), path("nabidka/nahled/", v.nabidka_nahled, name="nabidka_nahled"),
    path("faktura/z-zakazky/", v.faktura_nova, name="faktura_nova"),
    path("plocha/", v.plocha_home, name="plocha_hledat"), path("plocha/<int:pk>/", v.plocha, name="plocha"),
    path("nastaveni/sablony/", vs.sablony_seznam, name="sablony"), path("nastaveni/sablony/nova/", vs.sablona_edit, name="sablona_nova"),
    path("nastaveni/sablony/znacky/", vs.sablony_znacky, name="sablony_znacky"), path("nastaveni/sablony/<int:pk>/", vs.sablona_detail, name="sablona_detail"),
    path("nastaveni/sablony/<int:pk>/upravit/", vs.sablona_edit, name="sablona_edit"), path("nastaveni/sablony/<int:pk>/akce/<slug:akce>/", vs.sablona_akce, name="sablona_akce"),
    path("nastaveni/sablony/<int:pk>/miniatura.png", vs.sablona_miniatura, name="sablona_miniatura"), path("nastaveni/sablony/<int:pk>/ukazka/", vs.sablona_ukazka, name="sablona_ukazka"),
    path("nastaveni/sablony/<int:pk>/soubor/", vs.sablona_stahnout, name="sablona_stahnout"),
    path("nastaveni/sablony/<int:pk>/editor/", vs.sablona_editor, name="sablona_editor"),
    path("dokument/<slug:typ>/<int:pk>/", vs.dokument, name="dokument"), path("dokument/<slug:typ>/<int:pk>/obsah/", vs.dokument_obsah, name="dokument_obsah"),
    path("dokument/<slug:typ>/<int:pk>/pdf/", vs.dokument_pdf, name="dokument_pdf"), path("dokument/<slug:typ>/<int:pk>/isdoc/", vs.dokument_isdoc, name="dokument_isdoc"), path("dokument/<slug:typ>/<int:pk>/sablony/", vs.dokument_sablony, name="dokument_sablony"),
    path("<slug:slug>/", v.lst, name="list"), path("<slug:slug>/novy/", v.edit, name="create"),
    path("<slug:slug>/<int:pk>/", v.detail, name="detail"), path("<slug:slug>/<int:pk>/upravit/", v.edit, name="edit"),
    path("<slug:slug>/<int:pk>/smazat/", v.delete, name="delete")]
