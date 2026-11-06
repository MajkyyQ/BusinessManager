"""Vygeneruje docs/databaze-tabulky.md (přehled všech tabulek, sloupců a integritních omezení) přímo z modelů.

Spuštění z kořenové složky projektu:  python docs/generuj_prehled_databaze.py
Po každé změně v core/models.py stačí skript spustit znovu, aby dokumentace odpovídala databázi.
"""
import os, sys
from pathlib import Path
KOREN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOREN)); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.apps import apps
from django.db import models
TYP = {"CharField": "text ({n})", "TextField": "dlouhý text", "BooleanField": "logická hodnota", "DateTimeField": "datum a čas", "DateField": "datum",
       "DecimalField": "desetinné ({d},{p})", "BigAutoField": "celé číslo, PK", "IntegerField": "celé číslo", "PositiveIntegerField": "celé kladné číslo",
       "BigIntegerField": "velké celé číslo", "EmailField": "e-mail ({n})", "ImageField": "obrázek (cesta)", "FileField": "soubor (cesta)", "JSONField": "JSON"}
ms = list(apps.get_app_config("core").get_models())
o = ["# Referenční přehled tabulek a sloupců", "",
     "> Tento soubor je vygenerovaný přímo z modelů v `core/models.py` skriptem `docs/generuj_prehled_databaze.py`, takže přesně odpovídá aktuální databázi. Význam tabulek a vazeb vysvětluje [Databáze](07-databaze.md).", "",
     "Zkratky: **PK** primární klíč, **FK** cizí klíč, **M:N** vazba přes vazební tabulku. Sloupec *Povinné* říká, zda databáze dovolí prázdnou hodnotu.", "", "## Obsah", ""]
o += [f"- [{m.__name__}](#{m.__name__.lower()}) – {m._meta.verbose_name}" for m in ms]
m2m = []
for m in ms:
    o += ["", f"## {m.__name__}", "", f"Tabulka `{m._meta.db_table}` – {m._meta.verbose_name}.", "", "| Sloupec | Datový typ | Povinné | Popis |", "|:--|:--|:--|:--|"]
    for f in m._meta.get_fields():
        if f.auto_created and not f.concrete: continue
        if f.many_to_many:
            m2m.append((f.m2m_db_table(), m.__name__, f.related_model.__name__)); continue
        t = f.get_internal_type()
        if f.is_relation:
            tgt = f.related_model.__name__ if f.related_model._meta.app_label == "core" else "auth_user"
            od = f.remote_field.on_delete.__name__
            typ = f"FK → {tgt} ({od})" if not f.one_to_one else f"1:1 → {tgt} ({od})"; col = f.column
        else:
            typ = TYP.get(t, t).format(n=getattr(f, "max_length", ""), d=getattr(f, "max_digits", ""), p=getattr(f, "decimal_places", "")); col = f.column
            if f.unique and not f.primary_key: typ += ", unikátní"
            if f.db_index and not f.unique: typ += ", index"
            if f.choices: typ += "; hodnoty: " + ", ".join(f"„{c[0]}“" for c in f.choices)
        req = "ano" if (not f.null and not getattr(f, "blank", False)) or f.primary_key else "ne"
        popis = str(getattr(f, "verbose_name", "") or "")
        if popis.replace(" ", "_") == f.name or popis == "ID": popis = ""
        if getattr(f, "help_text", ""): popis += (" – " if popis else "") + str(f.help_text)
        if getattr(f, "has_default", lambda: False)() and not callable(f.default) and f.default not in ("", None): popis += " (výchozí " + ({True: "ano", False: "ne"}.get(f.default, str(f.default)) if isinstance(f.default, bool) else str(f.default)) + ")"
        o.append(f"| `{col}` | {typ} | {req} | {popis} |")
    cs = m._meta.constraints
    if cs:
        o += ["", "**Integritní omezení:**", ""]
        for c in cs:
            if isinstance(c, models.UniqueConstraint): o.append(f"- `{c.name}` – UNIQUE ({', '.join(c.fields)})")
            else:
                from django.db import connection
                from django.db.models.sql import Query
                q = Query(model=m, alias_cols=False); w = q.build_where(c.condition); comp = q.get_compiler(connection=connection)
                sql, params = w.as_sql(comp, connection)
                with connection.schema_editor() as se: sql = sql % tuple(se.quote_value(x) for x in params)
                o.append(f"- `{c.name}` – CHECK `{sql}`")
o += ["", "## Vazební tabulky (M:N)", "", "| Tabulka | Propojuje |", "|:--|:--|"]
o += [f"| `{t}` | {a} ↔ {b} |" for t, a, b in m2m]
(KOREN / "docs" / "databaze-tabulky.md").write_text("\n".join(o) + "\n", encoding="utf-8")
print(f"Hotovo: {len(ms)} tabulek, {len(m2m)} vazebních tabulek.")
