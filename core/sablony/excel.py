"""Excelové šablony: analýza struktury, rozpoznání polí a vyplnění daty.

Šablona pracuje s oblastmi buněk (např. "C7:F7"), sloučená oblast je vždy jeden celek.
Pole lze do Excelu umístit dvěma způsoby:
  1) značkou přímo v buňce, např. {{dokument.cislo}} nebo "Faktura č. {{dokument.cislo}}"
  2) mapováním (automaticky rozpoznaným nebo ručně upraveným), uloženým v SablonaDokumentu.mapovani

Tabulka položek je jeden vzorový řádek, který se při generování zopakuje podle počtu položek.
"""
import re
import unicodedata
from copy import copy
from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter, column_index_from_string, range_boundaries
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

from .typy import formatuj

ZNACKA = re.compile(r"\{\{\s*([a-z_]+\.[a-z_]+)\s*\}\}")


# ---------------------------------------------------------------- pomocné
def oblast_bunky(ws, cell):
    """Oblast (CellRange), do které buňka patří – sloučená oblast, nebo jen buňka sama."""
    for mr in ws.merged_cells.ranges:
        if mr.min_row <= cell.row <= mr.max_row and mr.min_col <= cell.column <= mr.max_col:
            return CellRange(mr.coord)
    return CellRange(cell.coordinate)


def _slouceni(ws):
    """Mapa (řádek, sloupec) -> sloučená oblast, pro rychlé hledání."""
    m = {}
    for mr in ws.merged_cells.ranges:
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1): m[(r, c)] = mr
    return m


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[:*]", "", s)).strip(" .")


def _bunka_textu(v):
    return isinstance(v, str) and v.strip() and not v.startswith("=")


# ---------------------------------------------------------------- analýza
def analyzuj(cesta, typ_cls):
    """Načte Excel a vrátí jeho strukturu + navržené mapování (dict pro SablonaDokumentu.mapovani)."""
    wb = load_workbook(cesta)
    zname = typ_cls.pole_dict()
    listy, znacky, nezname = [], [], set()
    for ws in wb.worksheets:
        listy.append({"nazev": ws.title, "rozsah": ws.dimensions, "sloucene": [str(m) for m in ws.merged_cells.ranges],
                      "tiskova_oblast": ws.print_area or "", "obrazky": len(getattr(ws, "_images", []))})
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c, MergedCell) or not isinstance(c.value, str): continue
                for k in ZNACKA.findall(c.value):
                    (znacky if k in zname else []).append({"pole": k, "list": ws.title, "oblast": oblast_bunky(ws, c).coord})
                    if k not in zname: nezname.add(k)
    m = {"verze": 1, "listy": listy, "znacky": znacky, "nezname_znacky": sorted(nezname), "pole": [], "tabulky": []}
    if not znacky:  # bez značek -> pokusíme se pole rozpoznat podle popisků
        m["pole"], m["tabulky"] = rozpoznej(wb, typ_cls)
    return m


def rozpoznej(wb, typ_cls):
    """Návrh mapování podle textů v šabloně (popisek -> nejbližší volná oblast vpravo, případně pod ním)."""
    vsechna = typ_cls.pole()
    jednoducha = [p for p in vsechna if not p.klic.startswith("polozka.") and p.synonyma]
    polozkova = [p for p in vsechna if p.klic.startswith("polozka.")]
    pole, tabulky, pouzite = [], [], set()
    for ws in wb.worksheets:
        sl = _slouceni(ws)
        # 1) tabulka položek: řádek, kde alespoň 3 buňky odpovídají názvům sloupců položek
        hlavicka = None
        for row in ws.iter_rows():
            shody = {}
            for c in row:
                if isinstance(c, MergedCell) or not _bunka_textu(c.value): continue
                t = _norm(c.value)
                for p in polozkova:
                    if p.klic in shody.values(): continue
                    if any(t == _norm(s) for s in p.synonyma):
                        shody[c.column] = p.klic; break
            if len(shody) >= 3:
                hlavicka = (row[0].row, shody); break
        if hlavicka and not tabulky:
            r, shody = hlavicka; vr = r + 1
            while vr in [x.max_row for x in ws.merged_cells.ranges if x.min_row == r and x.max_row > r]: vr += 1
            shody = {c: k for c, k in shody.items() if not (isinstance(ws.cell(vr, c).value, str) and str(ws.cell(vr, c).value).startswith("="))} or shody
            cols = {get_column_letter(c): k for c, k in shody.items()}
            lo, hi = min(shody), max(shody)
            for c, mr in ((c, sl.get((r, c))) for c in shody):
                if mr: hi = max(hi, mr.max_col)
            tabulky.append({"list": ws.title, "radek": vr, "oblast": f"{get_column_letter(lo)}{vr}:{get_column_letter(hi)}{vr}", "sloupce": cols, "zdroj": "auto"})
        hl_radek = hlavicka[0] if hlavicka else None
        # 2) jednotlivá pole podle popisků
        kandidati = []
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c, MergedCell) or not _bunka_textu(c.value) or c.row == hl_radek: continue
                t = _norm(c.value)
                if len(t) > 40: continue
                for p in jednoducha:
                    for s in p.synonyma:
                        s2 = _norm(s)
                        if t == s2: kandidati.append((0, len(s2), c, p)); break
                        if t.startswith(s2 + " ") and len(t) - len(s2) < 12: kandidati.append((1, len(s2), c, p)); break
        kandidati.sort(key=lambda x: (x[0], -x[1], x[2].row, x[2].column))
        obsazene = set()
        for _, _, c, p in kandidati:
            if p.klic in pouzite or c.coordinate in obsazene: continue
            cil = _volna_oblast(ws, c, sl)
            if not cil or cil.coord in obsazene: continue
            pouzite.add(p.klic); obsazene.add(c.coordinate); obsazene.add(cil.coord)
            pole.append({"pole": p.klic, "list": ws.title, "oblast": cil.coord, "popisek": f"{c.coordinate} „{str(c.value).strip()[:40]}“", "zdroj": "auto"})
    return pole, tabulky


def _volna_oblast(ws, c, sl):
    """Nejbližší prázdná oblast vpravo od popisku (max. 6 sloupců), jinak pod popiskem."""
    vlastni = sl.get((c.row, c.column)); col = (vlastni.max_col if vlastni else c.column) + 1
    for _ in range(6):
        if col > max(ws.max_column, 1) + 3: break
        mr = sl.get((c.row, col)); v = ws.cell(c.row, col).value if not mr else ws.cell(mr.min_row, mr.min_col).value
        if mr and (mr.min_row, mr.min_col) != (c.row, col) and mr.min_row != c.row: break
        if v in (None, ""):
            return CellRange(mr.coord) if mr else CellRange(ws.cell(c.row, col).coordinate)
        if isinstance(v, str) and v.startswith("="): return None  # hodnotu počítá vzorec v šabloně -> nepřepisovat
        if _bunka_textu(v) and not str(v).strip().endswith(":"): break
        col = (mr.max_col if mr else col) + 1
    rr = (vlastni.max_row if vlastni else c.row) + 1
    mr = sl.get((rr, c.column))
    v = ws.cell(rr, c.column).value if not mr else ws.cell(mr.min_row, mr.min_col).value
    if v in (None, ""): return CellRange(mr.coord) if mr else CellRange(ws.cell(rr, c.column).coordinate)
    return None


# ---------------------------------------------------------------- vyplnění
FMT_DATUM = "D. M. YYYY"
FMT_PENIZE = '#,##0.00\\ "Kč"'
FMT_CISLO = "#,##0.###"


def _zapis(ws, cell, hodnota, druh, mena):
    """Zapíše hodnotu do buňky; čísla a data jako skutečné hodnoty (Excel je zformátuje a spočítá)."""
    if isinstance(hodnota, datetime): hodnota = hodnota.date()
    obecny = cell.number_format == "General"  # openpyxl při zápisu data formát sám přepíše, proto zjistit předem
    if isinstance(hodnota, date):
        cell.value = hodnota
        cell.number_format = FMT_DATUM if obecny else cell.number_format
    elif isinstance(hodnota, (Decimal, int, float)) and not isinstance(hodnota, bool):
        cell.value = float(hodnota)
        if obecny:
            cell.number_format = (FMT_PENIZE if mena in ("", "CZK") else f'#,##0.00\\ "{mena}"') if druh == "penize" else FMT_CISLO
    else:
        cell.value = "" if hodnota is None else str(hodnota)
        if "\n" in cell.value:
            al = copy(cell.alignment); al.wrap_text = True; cell.alignment = al


def _nahrad_znacky(ws, cell, data, pole_dict, mena):
    v = cell.value
    if not isinstance(v, str) or "{{" not in v: return
    m = ZNACKA.fullmatch(v.strip())
    if m:  # celá buňka = jedna značka -> zapíšeme typovanou hodnotu
        k = m.group(1); p = pole_dict.get(k)
        if p and p.druh == "obrazek":
            cell.value = None; _vloz_obrazek(ws, oblast_bunky(ws, cell), data.get(k)); return
        _zapis(ws, cell, data.get(k, ""), p.druh if p else "text", mena); return
    def rep(mm):
        k = mm.group(1); p = pole_dict.get(k)
        return formatuj(data.get(k, ""), p.druh if p else "text", mena)
    cell.value = ZNACKA.sub(rep, v)
    if "\n" in cell.value:
        al = copy(cell.alignment); al.wrap_text = True; cell.alignment = al


def _rozmer_oblasti(ws, cr):
    """Šířka a výška oblasti v pixelech (přibližně, jak je počítá Excel)."""
    w = sum((ws.column_dimensions[get_column_letter(c)].width or 8.43) * 7 + 5 for c in range(cr.min_col, cr.max_col + 1))
    h = sum((ws.row_dimensions[r].height or 15) * 96 / 72 for r in range(cr.min_row, cr.max_row + 1))
    return w, h


def _vloz_obrazek(ws, cr, cesta):
    if not cesta: return
    try:
        img = XLImage(cesta)
    except Exception:
        return
    w, h = _rozmer_oblasti(ws, cr); s = min(w / img.width, h / img.height, 1) if img.width and img.height else 1
    img.width, img.height = img.width * s, img.height * s
    ws.add_image(img, f"{get_column_letter(cr.min_col)}{cr.min_row}")


# ---- rozšíření tabulky položek (vložení řádků se zachováním vzhledu, sloučení a vzorců)
_TOK = re.compile(r"(?<![A-Za-z_\d!'\"$])(\$?[A-Z]{1,3}\$?)(\d+)(?::(\$?[A-Z]{1,3}\$?)(\d+))?(?![\d(A-Za-z_])")


def _posun_vzorec(f, r, k):
    """Upraví odkazy ve vzorci po vložení k řádků pod řádek r: odkazy pod r se posunou,
    oblasti končící na řádku r nebo za ním se prodlouží (např. SUM(F20:F20) -> SUM(F20:F22))."""
    def sub(m):
        a = int(m.group(2))
        if m.group(3) is None: return f"{m.group(1)}{a + k if a > r else a}"
        b = int(m.group(4))
        return f"{m.group(1)}{a + k if a > r else a}:{m.group(3)}{b + k if b >= r else b}"
    return _TOK.sub(sub, f)


def rozsir_radek(ws, r, n):
    """Řádek r je vzor tabulky položek. Zajistí n řádků (r .. r+n-1) se stejným vzhledem."""
    k = n - 1
    if k <= 0: return
    max_col = ws.max_column
    sl_radek = [CellRange(m.coord) for m in ws.merged_cells.ranges if m.min_row == m.max_row == r]
    rozsahy = list(ws.merged_cells.ranges)
    ws.insert_rows(r + 1, k)
    # sloučené oblasti pod vzorem posunout, oblasti přes vzor prodloužit
    nove = MultiCellRange()
    for mr in rozsahy:
        cr = CellRange(mr.coord)
        if cr.min_row > r: cr.shift(row_shift=k)
        elif cr.max_row > r: cr.expand(down=k)
        nove.add(cr)
    for i in range(1, k + 1):
        for cr in sl_radek:
            x = CellRange(cr.coord); x.shift(row_shift=i); nove.add(x)
    ws.merged_cells = MultiCellRange()
    for cr in nove.ranges: ws.merge_cells(cr.coord)
    # výšky řádků
    vysky = {i: d.height for i, d in ws.row_dimensions.items() if d.height is not None and i > r}
    for i in sorted(vysky, reverse=True): ws.row_dimensions[i + k].height = vysky[i]
    for i in range(r + 1, r + k + 1): ws.row_dimensions[i].height = ws.row_dimensions[r].height
    # styly a vzorce vzorového řádku do nových řádků
    for c in range(1, max_col + 1):
        src = ws.cell(r, c)
        if isinstance(src, MergedCell): continue
        for i in range(1, k + 1):
            dst = ws.cell(r + i, c)
            if isinstance(dst, MergedCell): continue
            if src.has_style: dst._style = copy(src._style)
            if isinstance(src.value, str) and src.value.startswith("="):
                dst.value = Translator(src.value, origin=src.coordinate).translate_formula(dst.coordinate)
            else:
                dst.value = src.value  # značky {{polozka.*}} se vyplní později
    # vzorce ve zbytku listu
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell, MergedCell): continue
            if r <= cell.row <= r + k: continue
            if isinstance(cell.value, str) and cell.value.startswith("="): cell.value = _posun_vzorec(cell.value, r, k)
    # obrázky pod tabulkou
    for img in getattr(ws, "_images", []):
        a = img.anchor
        fr = getattr(a, "_from", None)
        if fr is not None and fr.row >= r:  # anchor je 0-based
            fr.row += k
            to = getattr(a, "to", None)
            if to is not None: to.row += k
    # tisková oblast
    if ws.print_area:
        pa = ws.print_area if isinstance(ws.print_area, str) else ",".join(ws.print_area)
        ws.print_area = [_posun_vzorec(x.split("!")[-1].replace("$", ""), r, k) for x in pa.split(",")]


def _vypln_tabulku(ws, t, polozky, pole_dict, mena):
    r = int(t["radek"]); n = len(polozky)
    rozsir_radek(ws, r, max(n, 1))
    sloupce = t.get("sloupce") or {}
    for i in range(max(n, 1)):
        data = polozky[i] if i < n else {}
        rr = r + i
        for row in ws.iter_rows(min_row=rr, max_row=rr):
            for cell in row:
                if isinstance(cell, MergedCell): continue
                if isinstance(cell.value, str) and "{{" in cell.value:
                    if data: _nahrad_znacky(ws, cell, data, pole_dict, mena)
                    else: cell.value = None
        for col, k in sloupce.items():
            cell = ws.cell(rr, column_index_from_string(col))
            if isinstance(cell, MergedCell) or (isinstance(cell.value, str) and cell.value.startswith("=")): continue  # vzorec šablony má přednost
            p = pole_dict.get(k)
            _zapis(ws, cell, data.get(k, "") if data else "", p.druh if p else "text", mena)


def vypln(cesta, mapovani, data, typ_cls):
    """Vrátí vyplněný sešit (openpyxl Workbook). Původní soubor šablony se nemění."""
    wb = load_workbook(cesta)
    pole_dict = typ_cls.pole_dict(); hodnoty = data["pole"]; mena = hodnoty.get("soucty.mena", "CZK")
    mapovani = mapovani or {}
    tabulky = list(mapovani.get("tabulky") or [])
    # tabulky definované značkami {{polozka.*}} (první takový řádek na listu)
    for ws in wb.worksheets:
        if any(t["list"] == ws.title for t in tabulky): continue
        for row in ws.iter_rows():
            if any(isinstance(c.value, str) and "{{polozka." in c.value for c in row if not isinstance(c, MergedCell)):
                tabulky.append({"list": ws.title, "radek": row[0].row, "sloupce": {}}); break
    for t in tabulky:
        if t["list"] in wb.sheetnames: _vypln_tabulku(wb[t["list"]], t, data["polozky"], pole_dict, mena)
    posuny = {t["list"]: (int(t["radek"]), max(len(data["polozky"]), 1) - 1) for t in tabulky}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if not isinstance(cell, MergedCell): _nahrad_znacky(ws, cell, hodnoty, pole_dict, mena)
    for f in mapovani.get("pole") or []:
        if f.get("list") not in wb.sheetnames: continue
        ws = wb[f["list"]]; cr = CellRange(f["oblast"])
        r0, k = posuny.get(ws.title, (0, 0))
        if k and cr.min_row > r0: cr.shift(row_shift=k)
        p = pole_dict.get(f["pole"])
        if p and p.druh == "obrazek": _vloz_obrazek(ws, cr, hodnoty.get(f["pole"])); continue
        _zapis(ws, ws.cell(cr.min_row, cr.min_col), hodnoty.get(f["pole"], ""), p.druh if p else "text", mena)
    return wb


# ---------------------------------------------------------------- mřížka pro editor
def mrizka(cesta, max_rows=120, max_cols=30):
    """Zjednodušený popis listů pro zobrazení v editoru (HTML tabulka se sloučenými buňkami)."""
    wb = load_workbook(cesta)
    out = []
    for ws in wb.worksheets:
        sl = _slouceni(ws); nr = min(ws.max_row, max_rows); nc = min(ws.max_column, max_cols)
        cols = [round((ws.column_dimensions[get_column_letter(c)].width or 8.43) * 7 + 5) for c in range(1, nc + 1)]
        rows = []
        for r in range(1, nr + 1):
            cells = []
            for c in range(1, nc + 1):
                mr = sl.get((r, c))
                if mr and (mr.min_row, mr.min_col) != (r, c): continue
                cell = ws.cell(r, c); v = cell.value
                st = []
                if cell.font is not None:
                    if cell.font.b: st.append("font-weight:bold")
                    if cell.font.sz: st.append(f"font-size:{min(float(cell.font.sz), 20) * 1.15:.0f}px")
                if cell.alignment is not None and cell.alignment.horizontal in ("center", "right"): st.append(f"text-align:{cell.alignment.horizontal}")
                fill = getattr(cell.fill, "fgColor", None)
                if cell.fill is not None and cell.fill.fill_type == "solid" and fill is not None and isinstance(fill.rgb, str) and len(fill.rgb) == 8 and fill.rgb != "00000000":
                    st.append(f"background:#{fill.rgb[2:]}")
                b = cell.border
                for side, nm in ((b.top, "top"), (b.bottom, "bottom"), (b.left, "left"), (b.right, "right")):
                    if side is not None and side.style: st.append(f"border-{nm}:1px solid #555")
                cells.append({"c": c, "a": (mr.coord if mr else cell.coordinate), "rs": (mr.max_row - mr.min_row + 1) if mr else 1,
                              "cs": (min(mr.max_col, nc) - mr.min_col + 1) if mr else 1,
                              "v": "" if v is None else (formatuj(v) if not isinstance(v, str) else v), "s": ";".join(st)})
            rows.append({"r": r, "h": round((ws.row_dimensions[r].height or 15) * 96 / 72), "cells": cells})
        out.append({"nazev": ws.title, "cols": cols, "rows": rows})
    return out
