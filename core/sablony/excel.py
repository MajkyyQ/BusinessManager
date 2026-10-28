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
    from .typy import SEZNAMY
    jednoducha = [p for p in vsechna if p.klic.split(".")[0] not in SEZNAMY and p.synonyma]
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


def vloz_radky(ws, r, za, k):
    """Vloží k řádků pod řádek `za` se vzhledem vzorového řádku r (sloučení, výška, styly, vzorce).
    Vše pod nimi se posune: sloučené oblasti, výšky řádků, vzorce, obrázky i tisková oblast."""
    if k <= 0: return
    max_col = ws.max_column
    sl_radek = [CellRange(m.coord) for m in ws.merged_cells.ranges if m.min_row == m.max_row == r]
    rozsahy = list(ws.merged_cells.ranges)
    ws.insert_rows(za + 1, k)
    nove = MultiCellRange()
    for mr in rozsahy:
        cr = CellRange(mr.coord)
        if cr.min_row > za: cr.shift(row_shift=k)
        elif cr.max_row > za: cr.expand(down=k)
        nove.add(cr)
    for i in range(1, k + 1):
        for cr in sl_radek:
            x = CellRange(cr.coord); x.shift(row_shift=za + i - r); nove.add(x)
    ws.merged_cells = MultiCellRange()
    for cr in nove.ranges: ws.merge_cells(cr.coord)
    for i in range(ws.max_row - k, za, -1):  # výšky řádků posunout (včetně výchozích) – insert_rows to nedělá
        ws.row_dimensions[i + k].height = ws.row_dimensions[i].height if i in ws.row_dimensions else None
    for i in range(za + 1, za + k + 1): ws.row_dimensions[i].height = ws.row_dimensions[r].height
    for c in range(1, max_col + 1):
        src = ws.cell(r, c)
        if isinstance(src, MergedCell): continue
        for i in range(za + 1, za + k + 1):
            dst = ws.cell(i, c)
            if isinstance(dst, MergedCell): continue
            if src.has_style: dst._style = copy(src._style)
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell, MergedCell) or za < cell.row <= za + k: continue
            if isinstance(cell.value, str) and cell.value.startswith("="): cell.value = _posun_vzorec(cell.value, za, k)
    for img in getattr(ws, "_images", []):
        fr = getattr(img.anchor, "_from", None)
        if fr is not None and fr.row >= za:  # anchor je 0-based
            fr.row += k
            to = getattr(img.anchor, "to", None)
            if to is not None: to.row += k
    if ws.print_area:
        pa = ws.print_area if isinstance(ws.print_area, str) else ",".join(ws.print_area)
        ws.print_area = [_posun_vzorec(x.split("!")[-1].replace("$", ""), za, k) for x in pa.split(",")]


def _sloupce_tabulky(ws, t, predpona):
    """Rozsah sloupců vzorového řádku (podle značek a namapovaných sloupců, včetně sloučení)."""
    r = int(t["radek"]); cols = {column_index_from_string(c) for c in (t.get("sloupce") or {})}
    for c in ws[r]:
        if not isinstance(c, MergedCell) and isinstance(c.value, str) and "{{" + predpona + "." in c.value: cols.add(c.column)
    if not cols: return 1, ws.max_column
    lo, hi = min(cols), max(cols)
    for m in ws.merged_cells.ranges:
        if m.min_row <= r <= m.max_row and m.max_col >= lo and m.min_col <= hi: lo, hi = min(lo, m.min_col), max(hi, m.max_col)
    return lo, hi


def _kapacita(ws, r, lo, hi):
    """Kolik řádků tabulka v šabloně už má: vzorový řádek + navazující prázdné řádky s rámečkem (předkreslené řádky)."""
    n = 1
    while n < 200:
        rr = r + n
        if rr > ws.max_row: break
        cells = [ws.cell(rr, c) for c in range(lo, hi + 1)]
        if any(not isinstance(c, MergedCell) and c.value not in (None, "") for c in ws[rr]): break  # v řádku už je jiný obsah
        if not any(c.border and any(getattr(c.border, x).style for x in ("top", "bottom", "left", "right")) for c in cells): break
        n += 1
    return n


def _vypln_tabulku(ws, t, radky, pole_dict, mena):
    """Vyplní opakující se řádek. Vrátí (za, k) = pod kterým řádkem a kolik řádků se vložilo."""
    predpona = t.get("predpona", "polozka")
    r = int(t["radek"]); n = len(radky); lo, hi = _sloupce_tabulky(ws, t, predpona)
    kap = _kapacita(ws, r, lo, hi)
    za, k = r + kap - 1, max(n - kap, 0)
    vloz_radky(ws, r, za, k)
    sloupce = t.get("sloupce") or {}
    for rr in range(r + 1, r + n):  # další řádky přebírají značky a vzorce ze vzorového řádku (a vzhled, pokud vlastní nemají)
        for c in range(1, ws.max_column + 1):
            src, dst = ws.cell(r, c), ws.cell(rr, c)
            if isinstance(src, MergedCell) or isinstance(dst, MergedCell): continue
            if not dst.has_style and src.has_style: dst._style = copy(src._style)
            if dst.value in (None, "") and isinstance(src.value, str):
                if src.value.startswith("="): dst.value = Translator(src.value, origin=src.coordinate).translate_formula(dst.coordinate)
                elif "{{" + predpona + "." in src.value: dst.value = src.value  # jiný text v řádku (popisky) se neopakuje
    for i in range(max(n, 1)):
        data = radky[i] if i < n else {}
        rr = r + i
        for c in range(lo, hi + 1):
            cell = ws.cell(rr, c)
            if isinstance(cell, MergedCell) or not (isinstance(cell.value, str) and "{{" in cell.value): continue
            if data: _nahrad_znacky(ws, cell, data, pole_dict, mena)
            else: cell.value = None
        for col, key in sloupce.items():
            cell = ws.cell(rr, column_index_from_string(col))
            if isinstance(cell, MergedCell) or (isinstance(cell.value, str) and cell.value.startswith("=")): continue  # vzorec šablony má přednost
            p = pole_dict.get(key)
            _zapis(ws, cell, data.get(key, "") if data else "", p.druh if p else "text", mena)
    return za, k


def najdi_tabulky(wb, mapovani):
    """Tabulky z mapování + tabulky definované značkami ({{polozka.*}}, {{material.*}}, {{prace.*}})."""
    from .typy import SEZNAMY
    tabulky = [dict(t, predpona=t.get("predpona", "polozka")) for t in (mapovani.get("tabulky") or [])]
    for ws in wb.worksheets:
        for pred in SEZNAMY:
            if any(t["list"] == ws.title and t["predpona"] == pred for t in tabulky): continue
            for row in ws.iter_rows():  # každý řádek se značkami je samostatná tabulka (např. práce ve dvou místech listu)
                if any(isinstance(c.value, str) and "{{" + pred + "." in c.value for c in row if not isinstance(c, MergedCell)):
                    tabulky.append({"list": ws.title, "radek": row[0].row, "sloupce": {}, "predpona": pred})
    return tabulky


def vypln(cesta, mapovani, data, typ_cls):
    """Vrátí vyplněný sešit (openpyxl Workbook). Původní soubor šablony se nemění.
    Atribut wb._bm_posuny = {list: [(za, k), ...]} popisuje vložené řádky (pro posun kreseb)."""
    from .typy import SEZNAMY
    wb = load_workbook(cesta)
    pole_dict = typ_cls.pole_dict(); hodnoty = data["pole"]; mena = hodnoty.get("soucty.mena", "CZK")
    mapovani = mapovani or {}
    posuny = {}
    # odspodu nahoru, aby vložené řádky neposunuly tabulky nad sebou
    for t in sorted(najdi_tabulky(wb, mapovani), key=lambda t: -int(t["radek"])):
        if t["list"] not in wb.sheetnames: continue
        za, k = _vypln_tabulku(wb[t["list"]], t, data.get(SEZNAMY.get(t["predpona"], "polozky"), []), pole_dict, mena)
        if k: posuny.setdefault(t["list"], []).append((za, k))
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if not isinstance(cell, MergedCell): _nahrad_znacky(ws, cell, hodnoty, pole_dict, mena)
    for f in mapovani.get("pole") or []:
        if f.get("list") not in wb.sheetnames: continue
        ws = wb[f["list"]]; cr = CellRange(f["oblast"])
        posun = sum(k for za, k in posuny.get(ws.title, []) if cr.min_row > za)
        if posun: cr.shift(row_shift=posun)
        p = pole_dict.get(f["pole"])
        if p and p.druh == "obrazek": _vloz_obrazek(ws, cr, hodnoty.get(f["pole"])); continue
        _zapis(ws, ws.cell(cr.min_row, cr.min_col), hodnoty.get(f["pole"], ""), p.druh if p else "text", mena)
    wb._bm_posuny = posuny
    return wb


# ---------------------------------------------------------------- mřížka pro editor
def _text_bunky(v):
    """Hodnota buňky jako text pro úpravu (vzorec včetně =, datum česky)."""
    if v is None: return ""
    if isinstance(v, (datetime, date)): return v.strftime("%d.%m.%Y")
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)


def mrizka(cesta, max_rows=200, max_cols=40):
    """Popis listů pro zobrazení v editoru (HTML tabulka se sloučenými buňkami).
    Každá buňka: c = sloupec, a = adresa nebo sloučená oblast, rs/cs = rozpětí, v = zobrazený text, f = text k úpravě, s = CSS."""
    wb = load_workbook(cesta)
    out = []
    for ws in wb.worksheets:
        sl = _slouceni(ws); nr = min(ws.max_row, max_rows); nc = min(ws.max_column, max_cols)
        cols = [0 if ws.column_dimensions[get_column_letter(c)].hidden else round((ws.column_dimensions[get_column_letter(c)].width or 8.43) * 7 + 5)
                for c in range(1, nc + 1)]
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
                    if cell.font.i: st.append("font-style:italic")
                    if cell.font.sz: st.append(f"font-size:{min(float(cell.font.sz), 20) * 1.15:.0f}px")
                al = cell.alignment
                if al is not None:
                    if al.horizontal in ("center", "right", "centerContinuous"): st.append(f"text-align:{'center' if al.horizontal != 'right' else 'right'}")
                    if al.vertical in ("top", "center"): st.append(f"vertical-align:{'middle' if al.vertical == 'center' else 'top'}")
                    if al.wrap_text: st.append("white-space:pre-wrap")
                fill = getattr(cell.fill, "fgColor", None)
                if cell.fill is not None and cell.fill.fill_type == "solid" and fill is not None and isinstance(fill.rgb, str) and len(fill.rgb) == 8 and fill.rgb != "00000000":
                    st.append(f"background:#{fill.rgb[2:]}")
                b = cell.border
                if mr:  # okraje sloučené oblasti jsou uložené na krajních buňkách
                    b_dole = ws.cell(mr.max_row, mr.min_col).border; b_vpravo = ws.cell(mr.min_row, mr.max_col).border
                    strany = ((b.top, "top"), (b_dole.bottom, "bottom"), (b.left, "left"), (b_vpravo.right, "right"))
                else:
                    strany = ((b.top, "top"), (b.bottom, "bottom"), (b.left, "left"), (b.right, "right"))
                for side, nm in strany:
                    if side is not None and side.style: st.append(f"border-{nm}:1px solid #555")
                if isinstance(v, str) and v.startswith("="): zobraz = v
                elif isinstance(v, str): zobraz = v
                else: zobraz = "" if v is None else formatuj(v)
                cells.append({"c": c, "a": (mr.coord if mr else cell.coordinate),
                              "rs": (min(mr.max_row, nr) - mr.min_row + 1) if mr else 1,
                              "cs": (min(mr.max_col, nc) - mr.min_col + 1) if mr else 1,
                              "v": zobraz, "f": _text_bunky(v), "s": ";".join(st)})
            rows.append({"r": r, "h": 0 if ws.row_dimensions[r].hidden else round((ws.row_dimensions[r].height or 15) * 96 / 72), "cells": cells})
        out.append({"nazev": ws.title, "cols": cols, "rows": rows})
    return out


_CISLO = re.compile(r"-?(0|[1-9]\d*)([.,]\d+)?")


def _hodnota_z_textu(t):
    """Text z editoru -> hodnota buňky (čísla jako čísla, prázdné jako nic)."""
    if t is None: return None
    t = str(t)
    if not t.strip(): return None
    if _CISLO.fullmatch(t.strip()):
        x = t.strip().replace(",", ".")
        return float(x) if "." in x else int(x)
    return t


def uprav(cesta, zmeny=(), slouceni=(), rozdeleni=()):
    """Úpravy šablony z editoru. Vrací bytes nového .xlsx (tvary a obrázky zůstávají).
    zmeny: [{list, bunka, hodnota}], slouceni / rozdeleni: [{list, oblast}]."""
    import io
    from . import kresby
    wb = load_workbook(cesta)
    def list_(n):
        if n not in wb.sheetnames: raise ValueError(f"List „{n}“ v šabloně není.")
        return wb[n]
    for o in rozdeleni:
        ws = list_(o["list"]); cr = CellRange(o["oblast"])
        for mr in list(ws.merged_cells.ranges):
            if mr.coord == cr.coord or not mr.isdisjoint(cr): ws.unmerge_cells(mr.coord)
    for o in slouceni:
        ws = list_(o["list"]); cr = CellRange(o["oblast"])
        if cr.size["rows"] * cr.size["columns"] < 2: continue
        for mr in list(ws.merged_cells.ranges):  # překrývající se sloučení nejdřív zrušit
            if not mr.isdisjoint(cr): ws.unmerge_cells(mr.coord)
        prvni = ws.cell(cr.min_row, cr.min_col)
        if prvni.value is None:  # Excel ponechá hodnotu levé horní buňky; když je prázdná, vezmeme první neprázdnou
            for row in ws.iter_rows(min_row=cr.min_row, max_row=cr.max_row, min_col=cr.min_col, max_col=cr.max_col):
                for c in row:
                    if c.value is not None: prvni.value = c.value; break
                if prvni.value is not None: break
        ws.merge_cells(cr.coord)
    for z in zmeny:
        ws = list_(z["list"]); cr = CellRange(z["bunka"])
        cell = ws.cell(cr.min_row, cr.min_col)
        if isinstance(cell, MergedCell):
            cell = ws.cell(*(lambda o: (o.min_row, o.min_col))(oblast_bunky(ws, cell)))
        cell.value = _hodnota_z_textu(z.get("hodnota"))
        if isinstance(cell.value, str) and "\n" in cell.value:
            al = copy(cell.alignment); al.wrap_text = True; cell.alignment = al
    b = io.BytesIO(); wb.save(b); n = len(wb.worksheets)
    try:
        return kresby.zachovej(cesta, b.getvalue(), [[] for _ in range(n)], [0] * n)
    except Exception:
        return b.getvalue()
