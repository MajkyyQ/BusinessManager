"""Zachování tvarů (rámečky, čáry, textová pole) z původního Excelu.

openpyxl při ukládání zahodí kresby, které nejsou obrázky. Tady se po vyplnění vezmou
kresby z původního souboru, posunou se podle vložených řádků a vrátí se do výsledku.
"""
import io
import posixpath
import zipfile

from lxml import etree

NS = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
      "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
      "ct": "http://schemas.openxmlformats.org/package/2006/content-types"}
T_DRAWING = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
CT_DRAWING = "application/vnd.openxmlformats-officedocument.drawing+xml"
TVARY = ("sp", "cxnSp", "grpSp", "graphicFrame")


def _rels_path(part):
    d, f = posixpath.split(part); return posixpath.join(d, "_rels", f + ".rels")


def _rels(z, part):
    p = _rels_path(part)
    if p not in z.namelist(): return None, {}
    x = etree.fromstring(z.read(p))
    return x, {r.get("Id"): r for r in x.findall("pr:Relationship", NS)}


def _cil(part, target):
    if target.startswith("/"): return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def _listy(z):
    wbx = etree.fromstring(z.read("xl/workbook.xml")); _, rels = _rels(z, "xl/workbook.xml")
    return [_cil("xl/workbook.xml", rels[s.get("{%s}id" % NS["r"])].get("Target")) for s in wbx.find("m:sheets", NS)]


def _kresba(z, sheet):
    _, rels = _rels(z, sheet)
    for r in rels.values():
        if r.get("Type") == T_DRAWING: return _cil(sheet, r.get("Target"))
    return None


def zachovej(original, vystup, posuny_listu, nove_obrazky):
    """original: cesta k šabloně; vystup: bytes vyplněného xlsx; posuny_listu: [ [(za, k), ...] pro každý list ];
    nove_obrazky: [počet obrázků přidaných při vyplnění pro každý list]. Vrací bytes."""
    try:
        zo = zipfile.ZipFile(original)
    except zipfile.BadZipFile:
        return vystup
    zv = zipfile.ZipFile(io.BytesIO(vystup))
    soubory = {n: zv.read(n) for n in zv.namelist()}
    zmena = False
    for i, (so, sv) in enumerate(zip(_listy(zo), _listy(zv))):
        dko = _kresba(zo, so)
        if not dko: continue
        dx = etree.fromstring(zo.read(dko))
        kotvy = list(dx)
        if not any(k.find(f"xdr:{t}", NS) is not None for k in kotvy for t in TVARY): continue  # jen obrázky -> openpyxl je zachoval
        # posun kotev podle vložených řádků (řádky v kresbě jsou od 0)
        for k in kotvy:
            for tag in ("xdr:from", "xdr:to"):
                e = k.find(tag, NS)
                if e is None: continue
                row = e.find("xdr:row", NS); r0 = int(row.text)
                row.text = str(r0 + sum(n for za, n in (posuny_listu[i] if i < len(posuny_listu) else []) if r0 >= za))
        # vztahy původní kresby (obrázky v ní) zkopírovat pod novými jmény
        jmeno = f"xl/drawings/bm_tvary{i + 1}.xml"
        _, drels = _rels(zo, dko)
        nove_rels = etree.Element("{%s}Relationships" % NS["pr"], nsmap={None: NS["pr"]})
        for rid, r in drels.items():
            if r.get("TargetMode") == "External":
                nove_rels.append(r); continue
            src = _cil(dko, r.get("Target")); dst = f"xl/media/bm_{i + 1}_{posixpath.basename(src)}"
            soubory[dst] = zo.read(src)
            etree.SubElement(nove_rels, "{%s}Relationship" % NS["pr"], Id=rid, Type=r.get("Type"), Target="../media/" + posixpath.basename(dst))
        # obrázky přidané při vyplnění (např. logo) přenést z kresby, kterou vytvořil openpyxl
        dkv = _kresba(zv, sv); n_new = nove_obrazky[i] if i < len(nove_obrazky) else 0
        if dkv and n_new:
            vx = etree.fromstring(soubory[dkv]); _, vrels = _rels(zv, dkv)
            for j, k in enumerate(list(vx)[-n_new:]):
                for blip in k.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
                    old = blip.get("{%s}embed" % NS["r"]); r = vrels.get(old)
                    if r is None: continue
                    nid = f"rIdBm{j}"; src = _cil(dkv, r.get("Target"))
                    etree.SubElement(nove_rels, "{%s}Relationship" % NS["pr"], Id=nid, Type=r.get("Type"), Target="../media/" + posixpath.basename(src))
                    blip.set("{%s}embed" % NS["r"], nid)
                dx.append(k)
        soubory[jmeno] = etree.tostring(dx, xml_declaration=True, encoding="UTF-8", standalone=True)
        soubory[_rels_path(jmeno)] = etree.tostring(nove_rels, xml_declaration=True, encoding="UTF-8", standalone=True)
        # list: odkaz na novou kresbu (případnou kresbu z openpyxl nahradí)
        srels_p = _rels_path(sv)
        if srels_p in soubory:
            srels = etree.fromstring(soubory[srels_p])
        else:
            srels = etree.Element("{%s}Relationships" % NS["pr"], nsmap={None: NS["pr"]})
        for r in list(srels):
            if r.get("Type") == T_DRAWING: srels.remove(r)
        etree.SubElement(srels, "{%s}Relationship" % NS["pr"], Id="rIdBmTvary", Type=T_DRAWING, Target="../drawings/" + posixpath.basename(jmeno))
        soubory[srels_p] = etree.tostring(srels, xml_declaration=True, encoding="UTF-8", standalone=True)
        sx = etree.fromstring(soubory[sv])
        for d in sx.findall("m:drawing", NS): sx.remove(d)
        el = etree.Element("{%s}drawing" % NS["m"]); el.set("{%s}id" % NS["r"], "rIdBmTvary")
        po = None  # <drawing> musí stát před legacyDrawing / tableParts / extLst
        for tag in ("legacyDrawing", "legacyDrawingHF", "picture", "oleObjects", "controls", "webPublishItems", "tableParts", "extLst"):
            po = sx.find(f"m:{tag}", NS)
            if po is not None: break
        if po is not None: po.addprevious(el)
        else: sx.append(el)
        soubory[sv] = etree.tostring(sx, xml_declaration=True, encoding="UTF-8", standalone=True)
        ct = etree.fromstring(soubory["[Content_Types].xml"])
        etree.SubElement(ct, "{%s}Override" % NS["ct"], PartName="/" + jmeno, ContentType=CT_DRAWING)
        if not any(d.get("Extension") == "png" for d in ct.findall("ct:Default", NS)):
            for ext, typ in (("png", "image/png"), ("jpeg", "image/jpeg"), ("jpg", "image/jpeg"), ("gif", "image/gif"), ("emf", "image/x-emf"), ("wmf", "image/x-wmf")):
                if not any(d.get("Extension") == ext for d in ct.findall("ct:Default", NS)):
                    etree.SubElement(ct, "{%s}Default" % NS["ct"], Extension=ext, ContentType=typ)
        soubory["[Content_Types].xml"] = etree.tostring(ct, xml_declaration=True, encoding="UTF-8", standalone=True)
        zmena = True
    if not zmena: return vystup
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in soubory.items(): z.writestr(n, d)
    return b.getvalue()
