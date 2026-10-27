"""Vygeneruje vestavěné Excelové šablony (core/sablony/vzory/*.xlsx).

Šablony slouží zároveň jako ukázka značek {{...}}: kdo chce vlastní Excel, může si vzít tento
a upravit vzhled. Spuštění: python manage.py vytvor_vzory_sablon
"""
from django.core.management.base import BaseCommand
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from core.sablony.renderery import VZORY

TENKA = Side(style="thin", color="999999"); SILNA = Side(style="medium", color="333333")
SEDA = PatternFill("solid", fgColor="EEEEEE")


def _vzor(kod):
    wb = Workbook(); ws = wb.active
    ws.title = {"faktura": "Faktura", "nabidka": "Nabídka", "zakazkovy_list": "Zakázkový list"}[kod]
    for col, w in zip("ABCDEFGHI", (1.5, 4, 32, 9, 6, 11, 7, 12, 13)): ws.column_dimensions[col].width = w
    def put(rng, v, b=False, sz=10, al="left", va="center", wrap=False, fill=None, box=False, color=None):
        ws.merge_cells(rng) if ":" in rng else None
        c = ws[rng.split(":")[0]]; c.value = v
        c.font = Font(name="Arial", bold=b, size=sz, color=color); c.alignment = Alignment(horizontal=al, vertical=va, wrap_text=wrap)
        if fill: c.fill = fill
        if box:
            from openpyxl.utils import range_boundaries
            c1, r1, c2, r2 = range_boundaries(rng if ":" in rng else f"{rng}:{rng}")
            for r in range(r1, r2 + 1):
                for cc in range(c1, c2 + 1):
                    x = ws.cell(r, cc)
                    x.border = Border(left=TENKA if cc == c1 else None, right=TENKA if cc == c2 else None, top=TENKA if r == r1 else None, bottom=TENKA if r == r2 else None)
    nazev = {"faktura": "FAKTURA – daňový doklad", "nabidka": "CENOVÁ NABÍDKA", "zakazkovy_list": "ZAKÁZKOVÝ LIST"}[kod]
    for r, h in ((1, 22), (2, 20), (3, 18)): ws.row_dimensions[r].height = h
    put("B1:D3", "{{firma.logo}}")
    put("E1:I1", nazev, b=True, sz=16, al="right")
    put("E2:I2", "č. {{dokument.cislo}}", b=True, sz=13, al="right")
    r = 5
    put(f"B{r}:D{r}", "Dodavatel" if kod != "zakazkovy_list" else "Servis", b=True, sz=8, color="666666")
    put(f"F{r}:I{r}", "Odběratel" if kod != "zakazkovy_list" else "Zákazník", b=True, sz=8, color="666666")
    put("B6:D6", "{{firma.nazev}}", b=True, sz=11); put("F6:I6", "{{zakaznik.nazev}}", b=True, sz=11)
    ws.row_dimensions[7].height = 30
    put("B7:D7", "{{firma.adresa}}", va="top", wrap=True); put("F7:I7", "{{zakaznik.adresa}}", va="top", wrap=True)
    put("B8:D8", "IČO: {{firma.ico}}   DIČ: {{firma.dic}}"); put("F8:I8", "IČO: {{zakaznik.ico}}   DIČ: {{zakaznik.dic}}")
    put("B9:D9", "{{firma.telefon}}  {{firma.email}}"); put("F9:I9", "{{zakaznik.telefon}}  {{zakaznik.email}}")
    r = 11
    if kod == "faktura":
        put("B11:C11", "Datum vystavení:"); put("D11:E11", "{{dokument.datum_vystaveni}}", al="left")
        put("F11:G11", "Datum splatnosti:", b=True); put("H11:I11", "{{dokument.datum_splatnosti}}", b=True, al="left")
        put("B12:C12", "DUZP:"); put("D12:E12", "{{dokument.duzp}}", al="left")
        put("F12:G12", "Zakázka:"); put("H12:I12", "{{zakazka.cislo}}", al="left")
        r = 14
    elif kod == "nabidka":
        put("B11:C11", "Datum vystavení:"); put("D11:E11", "{{dokument.datum_vystaveni}}", al="left")
        put("F11:G11", "Vypracoval:"); put("H11:I11", "{{dokument.vystavil}}", al="left")
        put("B12:C12", "Zakázka:"); put("D12:E12", "{{zakazka.cislo}}", al="left")
        r = 14
    else:
        put("B11:C11", "Datum přijetí:"); put("D11:E11", "{{zakazka.datum_prijeti}}", al="left")
        put("F11:G11", "Datum vydání:"); put("H11:I11", "{{zakazka.datum_vydani}}", al="left")
        put("B12:C12", "Ident. číslo:"); put("D12:E12", "{{zakazka.identifikacni_cislo}}", al="left")
        put("F12:G12", "Stav:"); put("H12:I12", "{{zakazka.stav}}", al="left")
        put("B14:I14", "Zařízení", b=True, sz=8, color="666666")
        ws.row_dimensions[15].height = 30; put("B15:I15", "{{zarizeni.vse}}", va="top", wrap=True, box=True)
        put("B17:I17", "Popis závady", b=True, sz=8, color="666666")
        ws.row_dimensions[18].height = 45; put("B18:I18", "{{zakazka.popis_zavady}}", va="top", wrap=True, box=True)
        put("B20:I20", "Provedené práce a materiál", b=True, sz=8, color="666666")
        r = 21
    hl = ("#", "Popis", "Množství", "MJ", "Cena/j.", "DPH %", "Bez DPH", "S DPH")
    zn = ("{{polozka.poradi}}", "{{polozka.popis}}", "{{polozka.mnozstvi}}", "{{polozka.jednotka}}", "{{polozka.jednotkova_cena}}",
          "{{polozka.sazba_dph}}", "{{polozka.cena_bez_dph}}", "{{polozka.cena_s_dph}}")
    for i, (h, z) in enumerate(zip(hl, zn)):
        col = "BCDEFGHI"[i]; al = "left" if i < 2 or i == 3 else "right"
        c = ws[f"{col}{r}"]; c.value = h; c.font = Font(name="Arial", bold=True, size=9); c.fill = SEDA
        c.alignment = Alignment(horizontal=al, vertical="center"); c.border = Border(bottom=TENKA, top=TENKA)
        c = ws[f"{col}{r + 1}"]; c.value = z; c.font = Font(name="Arial", size=9)
        c.alignment = Alignment(horizontal=al, vertical="top", wrap_text=(i == 1)); c.border = Border(bottom=Side(style="hair", color="BBBBBB"))
    r += 3
    put(f"F{r}:H{r}", "Celkem bez DPH", al="right"); put(f"I{r}", "{{soucty.bez_dph}}", al="right")
    put(f"F{r + 1}:H{r + 1}", "DPH", al="right"); put(f"I{r + 1}", "{{soucty.dph}}", al="right")
    put(f"F{r + 2}:H{r + 2}", "Celkem k úhradě" if kod == "faktura" else "Celkem s DPH", b=True, sz=12, al="right")
    put(f"I{r + 2}", "{{soucty.s_dph}}", b=True, sz=12, al="right")
    for col in "FGHI": ws[f"{col}{r + 2}"].border = Border(top=SILNA)
    r += 4
    if kod != "zakazkovy_list":
        ws.row_dimensions[r].height = 30
        put(f"B{r}:I{r}", "{{dokument.poznamka}}", va="top", wrap=True); r += 2
    else:
        r += 2
        for rng, t in ((f"B{r}:D{r}", "Převzal (zákazník)"), (f"F{r}:I{r}", "Za servis: {{zakazka.zamestnanci}}")):
            put(rng, t, al="center", sz=9)
            from openpyxl.utils import range_boundaries
            c1, r1, c2, _ = range_boundaries(rng)
            for cc in range(c1, c2 + 1): ws.cell(r1, cc).border = Border(top=TENKA)
    ws.print_area = f"A1:I{r}"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4; ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0; ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = ws.page_margins.right = 0.5; ws.page_margins.top = ws.page_margins.bottom = 0.6
    ws.sheet_view.showGridLines = False
    return wb


class Command(BaseCommand):
    help = "Vygeneruje vestavěné Excelové šablony dokumentů"

    def handle(self, *a, **k):
        VZORY.mkdir(exist_ok=True)
        for kod in ("faktura", "nabidka", "zakazkovy_list"):
            p = VZORY / f"{kod}_standardni.xlsx"; _vzor(kod).save(p); self.stdout.write(f"✓ {p}")
