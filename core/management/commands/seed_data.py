"""Testovací data: 20 zákazníků, 50 zařízení, 50 zakázek, 4 zaměstnanci, úkony a materiál.

Spuštění:  python manage.py seed_data
Nic nemaže, jen přidává. Druhé spuštění se zastaví (kontrola podle IČO první firmy).
Nabídky, objednávky, faktury, platby, fotky a přílohy se nevytváří.
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (Material, PouzityMaterial, ProvedenyUkon, Role, StavZakazky, TypUkonu,
                         Zakaznik, Zakazka, Zamestnanec, Zarizeni)

FIRMY = [  # firma, kontaktní osoba, adresa, telefon, email, IČO
    ("Stavby Novák s.r.o.", "Jiří Novák", "Průmyslová 1428/12, 370 01 České Budějovice", "602 314 785", "info@stavbynovak.cz", "27384519"),
    ("Truhlářství Dvořák a syn s.r.o.", "Pavel Dvořák", "Na Pískách 56, 397 01 Písek", "721 458 963", "dvorak@truhlarstvi-dvorak.cz", "25619870"),
    ("Elektro Svoboda s.r.o.", "Martin Svoboda", "Husova 812, 386 01 Strakonice", "777 125 846", "obchod@elektrosvoboda.cz", "28947151"),
    ("Zahradnické služby Zelený s.r.o.", "Tomáš Zelený", "Lidická 2210/4, 390 02 Tábor", "731 652 418", "zeleny@zahrady-zeleny.cz", "06125476"),
    ("Autoservis Kučera s.r.o.", "Lukáš Kučera", "Pražská 1543, 377 01 Jindřichův Hradec", "608 947 231", "servis@autoservis-kucera.cz", "26874539"),
]
OSOBY = [  # jméno, adresa, telefon, email
    ("Jan Procházka", "Komenského 15, 370 05 České Budějovice", "604 851 237", "jan.prochazka@seznam.cz"),
    ("Petra Veselá", "Budovatelská 1172, 397 01 Písek", "736 412 598", "petra.vesela@email.cz"),
    ("Karel Černý", "Zámecká 8, 384 01 Prachatice", "605 247 963", "karel.cerny@gmail.com"),
    ("Marie Horáková", "Nádražní 341, 386 01 Strakonice", "722 963 154", "horakova.marie@seznam.cz"),
    ("Josef Marek", "U Hřiště 27, 373 41 Hluboká nad Vltavou", "608 314 752", "josef.marek@centrum.cz"),
    ("Lenka Pospíšilová", "Kpt. Jaroše 1903, 390 03 Tábor", "775 846 231", "lenka.pospisilova@gmail.com"),
    ("Miroslav Hájek", "Na Výsluní 112, 382 41 Kaplice", "603 528 147", "mirek.hajek@seznam.cz"),
    ("Eva Králová", "Mánesova 22, 370 01 České Budějovice", "739 147 852", "eva.kralova@email.cz"),
    ("František Beneš", "Riegrova 9, 381 01 Český Krumlov", "602 785 413", "fbenes@volny.cz"),
    ("Jana Fialová", "Sokolská 476, 392 01 Soběslav", "731 258 964", "jana.fialova@seznam.cz"),
    ("Václav Sedláček", "Jiráskova 1350, 377 01 Jindřichův Hradec", "606 412 879", "vaclav.sedlacek@gmail.com"),
    ("Hana Doležalová", "Lipová 31, 374 01 Trhové Sviny", "724 693 518", "hana.dolezalova@centrum.cz"),
    ("Roman Kolář", "Školní 205, 398 11 Protivín", "607 351 864", "roman.kolar@seznam.cz"),
    ("Zdeňka Němcová", "Palackého 47, 383 01 Prachatice", "733 821 465", "z.nemcova@email.cz"),
    ("David Urban", "Třebízského 1101, 390 01 Tábor", "777 468 213", "david.urban@gmail.com"),
]
ZAMESTNANCI = [  # jméno, příjmení, telefon, email, pozice, role
    ("Tomáš", "Bláha", "604 112 358", "blaha@servis.cz", "Technik", "Technik"),
    ("Ondřej", "Růžička", "721 132 134", "ruzicka@servis.cz", "Technik", "Technik"),
    ("Michal", "Kříž", "736 558 914", "kriz@servis.cz", "Technik", "Technik"),
    ("Kateřina", "Malá", "608 233 377", "mala@servis.cz", "Administrativní pracovník", "Administrativa"),
]
# výrobce, typ, popis, typická závada
ZARIZENI = [
    ("Makita", "HR2470", "Vrtací kladivo SDS-Plus", "Kladivo nepříklepává, jen vrtá."),
    ("Makita", "GA5030R", "Úhlová bruska 125 mm", "Jiskří u uhlíků, ztrácí výkon."),
    ("Makita", "DHP482", "Aku příklepová vrtačka 18 V", "Nefunguje spínač, občas se nerozběhne."),
    ("Bosch", "GBH 2-26 DRE", "Vrtací kladivo", "Hlučný chod převodovky."),
    ("Bosch", "GWS 7-125", "Úhlová bruska", "Po zapnutí vyhodí jistič."),
    ("Bosch", "GSR 18V-55", "Aku vrtačka", "Nedrží nabití, baterie se rychle vybíjí."),
    ("Bosch", "PST 700 E", "Přímočará pila", "Pila vibruje a list se kroutí."),
    ("DeWalt", "D25133K", "Vrtací kladivo", "Vypadává sklíčidlo, vůle v uložení."),
    ("DeWalt", "DWE4157", "Úhlová bruska", "Nejde zapnout."),
    ("DeWalt", "DCD796", "Aku příklepový šroubovák", "Přeskakuje spojka."),
    ("Hilti", "TE 30-A36", "Aku kombinované kladivo", "Chybové hlášení na displeji, nevrtá."),
    ("Hilti", "DD 150-U", "Jádrová vrtačka", "Kape voda z vodního nástavce, slabý chod."),
    ("Metabo", "W 9-125", "Úhlová bruska", "Silně se zahřívá, zápach spáleniny."),
    ("Metabo", "KGS 254 M", "Pokosová pila", "Motor se rozbíhá ztěžka."),
    ("Festool", "ETS 150/3 EQ", "Excentrická bruska", "Nefunguje odsávání, brusný talíř se nedotáčí."),
    ("Festool", "TS 55 FEBQ", "Ponorná pila", "Pila se po spuštění zastavuje."),
    ("Stihl", "MS 251", "Motorová pila", "Nejde nastartovat."),
    ("Stihl", "FS 131", "Křovinořez", "Motor zhasíná při plném plynu."),
    ("Stihl", "BG 86", "Fukar", "Slabý výkon, kouří."),
    ("Husqvarna", "435 II", "Motorová pila", "Řetěz se netočí, prokluzuje spojka."),
    ("Husqvarna", "LC 247", "Sekačka na trávu", "Nesbírá trávu do koše, vibrace nože."),
    ("Kärcher", "K 5 Premium", "Vysokotlaký čistič", "Netlačí, pumpa se zapíná a vypíná."),
    ("Kärcher", "WD 6 P", "Průmyslový vysavač", "Slabý sací výkon."),
    ("Kärcher", "HDS 6/14 C", "Horkovodní vysokotlaký čistič", "Neohřívá vodu."),
    ("Güde", "GBK 300", "Pásová bruska", "Pás sjíždí do strany."),
    ("Einhell", "TE-CD 18/2", "Aku vrtačka", "Nabíječka nenabíjí."),
    ("Einhell", "TC-AC 190/24/8", "Kompresor", "Nedotlakuje, uniká vzduch."),
    ("Narex", "EV 13-2K", "Příklepová vrtačka", "Utržený přívodní kabel."),
    ("Narex", "EBU 230-24", "Úhlová bruska 230 mm", "Nefunguje rozběhová elektronika."),
    ("Narex", "CHP 21-2", "Elektrický hoblík", "Hoblík trhá materiál, tupé nože."),
    ("Ryobi", "RCS1935", "Elektrická řetězová pila", "Nemaže řetěz."),
    ("Fein", "MultiMaster FMM 350", "Oscilační nářadí", "Vůle hřídele, hlučný chod."),
    ("Milwaukee", "M18 FPD2", "Aku příklepová vrtačka", "Po chvíli práce se vypne."),
    ("Milwaukee", "K 545 S", "Bourací kladivo", "Únik oleje, slabý úder."),
    ("Black+Decker", "KR504CRESK", "Příklepová vrtačka", "Zadřené sklíčidlo."),
    ("Scheppach", "HS 105", "Stolní kotoučová pila", "Motor bručí, ale netočí se."),
    ("Worx", "WG779E", "Aku sekačka", "Nespustí se, bliká kontrolka."),
    ("Honda", "HRX 476 C", "Benzínová sekačka", "Špatně startuje, nepravidelný chod."),
    ("Makita", "UC4041A", "Elektrická řetězová pila", "Řetězová brzda nepovoluje."),
    ("Bosch", "GKS 190", "Okružní pila", "Při zatížení se zastavuje."),
    ("DeWalt", "DW713", "Pokosová pila", "Ulomený kryt kotouče."),
    ("Metabo", "SBE 650", "Příklepová vrtačka", "Nefunguje příklep."),
    ("Hitachi", "H60MC", "Bourací kladivo", "Kladivo netluče."),
    ("Kärcher", "K 4 Compact", "Vysokotlaký čistič", "Teče voda z pumpy."),
    ("Stihl", "HSA 56", "Aku nůžky na živý plot", "Nože se zasekávají."),
    ("Bosch", "AdvancedCut 18", "Aku pila ocaska", "Nedrží pilový list."),
    ("Makita", "9558HNRG", "Úhlová bruska", "Uvolněná hlava převodovky."),
    ("Festool", "CTL 26 E", "Mobilní vysavač", "Nespouští se při zapnutí nářadí."),
    ("Narex", "ESP 200 ES", "Šavlová pila", "Prasklý kryt motoru."),
    ("Einhell", "GE-CM 43 Li", "Aku sekačka", "Motor se točí, nůž ne."),
]
UKONY = {  # název: (popis, cena od, cena do)
    "Diagnostika": ("Prověření funkčnosti a zjištění závady", 250, 450),
    "Oprava": ("Oprava závady", 400, 1500),
    "Výměna dílu": ("Demontáž vadného a montáž nového dílu", 300, 900),
    "Čištění a údržba": ("Vyčištění, promazání, kontrola", 250, 600),
    "Výměna ložisek": ("Výměna ložisek motoru / převodovky", 450, 900),
    "Převinutí motoru": ("Převinutí rotoru nebo statoru", 1200, 2500),
    "Revize elektro": ("Revize elektrického nářadí dle ČSN 33 1600", 150, 250),
    "Seřízení": ("Seřízení a nastavení", 200, 500),
}
# název, jednotka, cena
MATERIAL = [
    ("Ložisko 6201 2RS", "ks", 65), ("Ložisko 607 2RS", "ks", 45), ("Ložisko 6000 2Z", "ks", 55),
    ("Uhlíky motoru (pár) 6×10 mm", "pár", 120), ("Uhlíky motoru (pár) 5×8 mm", "pár", 95),
    ("Spínač s regulací otáček", "ks", 380), ("Spínač ON/OFF", "ks", 190),
    ("Přívodní kabel H07RN-F 3×1,5 – 4 m", "ks", 260), ("Odlehčovací průchodka kabelu", "ks", 35),
    ("Kotva (rotor)", "ks", 1450), ("Stator", "ks", 1180), ("Ozubené kolo převodovky", "ks", 320),
    ("Mazivo na převodovky", "g", 0.9), ("Těsnicí kroužek (O-kroužek)", "ks", 18), ("Sada těsnění pumpy", "sada", 340),
    ("Sklíčidlo 13 mm rychloupínací", "ks", 420), ("Zapalovací svíčka", "ks", 110), ("Vzduchový filtr", "ks", 145),
    ("Palivový filtr", "ks", 85), ("Membrána karburátoru", "sada", 230), ("Startovací lanko", "m", 25),
    ("Řetěz 3/8\" 1,3 mm 50 čl.", "ks", 390), ("Spojka odstředivá", "ks", 560), ("Klínový řemen", "ks", 210),
    ("Brusný pás 75×457 mm", "ks", 45), ("Nože do hoblíku (pár)", "pár", 280), ("Šrouby a drobný spojovací materiál", "sada", 30),
    ("Kondenzátor odrušovací", "ks", 75), ("Elektronika rozběhu", "ks", 650), ("Akumulátor 18 V 2,0 Ah", "ks", 1290),
    ("Topná spirála", "ks", 1650), ("Tlakový spínač", "ks", 480), ("Zpětný ventil", "ks", 160),
]
# Úmyslné případy: stejný materiál na dvou různých zakázkách (index zakázky, název, množství, cena)
STEJNY_MATERIAL = [
    # stejná cena
    (3, "Ložisko 6201 2RS", 2, 65), (7, "Ložisko 6201 2RS", 2, 65),               # dvě vrtací kladiva
    (5, "Spínač s regulací otáček", 1, 380), (41, "Spínač s regulací otáček", 1, 380),  # dvě vrtačky
    # jiná cena (zdražení / sleva)
    (4, "Uhlíky motoru (pár) 6×10 mm", 1, 110), (39, "Uhlíky motoru (pár) 6×10 mm", 1, 120),
    (16, "Zapalovací svíčka", 1, 99), (37, "Zapalovací svíčka", 1, 110),
    (21, "Sada těsnění pumpy", 1, 320), (23, "Sada těsnění pumpy", 1, 340),
    (27, "Přívodní kabel H07RN-F 3×1,5 – 4 m", 1, 240), (30, "Přívodní kabel H07RN-F 3×1,5 – 4 m", 1, 260),
]
# Materiál podle typu zařízení (klíčová slova v popisu)
MAT_PODLE_TYPU = {  # pořadí: specifičtější klíče první
    "aku sekačka": ["Spínač ON/OFF", "Akumulátor 18 V 2,0 Ah"],
    "motorová": ["Zapalovací svíčka", "Vzduchový filtr", "Palivový filtr", "Membrána karburátoru", "Spojka odstředivá", "Řetěz 3/8\" 1,3 mm 50 čl."],
    "kladivo": ["Ložisko 607 2RS", "Těsnicí kroužek (O-kroužek)", "Mazivo na převodovky", "Ozubené kolo převodovky"],
    "bruska": ["Uhlíky motoru (pár) 5×8 mm", "Ložisko 6000 2Z", "Spínač ON/OFF", "Kotva (rotor)"],
    "vrtačka": ["Sklíčidlo 13 mm rychloupínací", "Spínač s regulací otáček", "Uhlíky motoru (pár) 5×8 mm"],
    "šroubovák": ["Spínač s regulací otáček", "Akumulátor 18 V 2,0 Ah"],
    "pila": ["Ložisko 6000 2Z", "Klínový řemen", "Uhlíky motoru (pár) 6×10 mm", "Stator"],
    "křovinořez": ["Zapalovací svíčka", "Vzduchový filtr", "Startovací lanko"],
    "fukar": ["Zapalovací svíčka", "Vzduchový filtr", "Palivový filtr"],
    "sekačka": ["Zapalovací svíčka", "Vzduchový filtr", "Klínový řemen", "Spínač ON/OFF"],
    "čistič": ["Sada těsnění pumpy", "Zpětný ventil", "Tlakový spínač", "Těsnicí kroužek (O-kroužek)"],
    "vysavač": ["Kondenzátor odrušovací", "Spínač ON/OFF", "Kotva (rotor)"],
    "kompresor": ["Tlakový spínač", "Zpětný ventil", "Těsnicí kroužek (O-kroužek)"],
    "hoblík": ["Nože do hoblíku (pár)", "Klínový řemen"],
}


def _dt(d): return timezone.make_aware(d)


class Command(BaseCommand):
    help = "Naplní databázi testovacími daty (zákazníci, zařízení, zakázky, zaměstnanci, úkony, materiál)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Spustit i když už testovací data v DB jsou.")

    @transaction.atomic
    def handle(self, *a, force=False, **k):
        if Zakaznik.objects.filter(ico=FIRMY[0][5]).exists() and not force:
            self.stdout.write(self.style.WARNING("Testovací data už v databázi jsou (spusťte s --force pro další sadu)."))
            return
        rnd = random.Random(2026)

        # Zaměstnanci
        tech, zam = [], []
        for jm, pr, tel, em, poz, role in ZAMESTNANCI:
            z = Zamestnanec.objects.create(jmeno=jm, prijmeni=pr, telefon=tel, email=em, pracovni_pozice=poz)
            r = Role.objects.filter(nazev=role).first() if role else None
            if r: z.role.add(r)
            zam.append(z)
            if poz == "Technik": tech.append(z)

        # Zákazníci
        zakaznici = []
        for firma, jm, adr, tel, em, ico in FIRMY:
            zakaznici.append(Zakaznik.objects.create(typ_zakaznika="Firma", firma=firma, jmeno=jm, adresa=adr,
                                                     telefon=tel, email=em, ico=ico, dic=f"CZ{ico}"))
        for jm, adr, tel, em in OSOBY:
            zakaznici.append(Zakaznik.objects.create(typ_zakaznika="Soukromá osoba", jmeno=jm, adresa=adr, telefon=tel, email=em))

        # Zařízení: firmy mají víc kusů (5 × 5 = 25), osoby 1–2 (25)
        vlastnici = [c for c in zakaznici[:5] for _ in range(5)] + zakaznici[5:] + zakaznici[5:15]
        zarizeni = []
        for i, ((vyr, typ, popis, zavada), vl) in enumerate(zip(ZARIZENI, vlastnici)):
            sn = f"{vyr[:2].upper()}{rnd.randint(100000, 999999)}"
            zarizeni.append((Zarizeni.objects.create(zakaznik=vl, vyrobce=vyr, typ=typ, seriove_cislo=sn, popis=popis), zavada))

        # Typy úkonů a materiál (existující se použijí, nic se nepřepisuje)
        typy = {}
        for n, (p, lo, hi) in UKONY.items():
            typy[n] = TypUkonu.objects.get_or_create(nazev=n, defaults={"popis": p})[0]
        mats = {}
        for n, j, c in MATERIAL:
            mats[n] = Material.objects.get_or_create(nazev=n, defaults={"jednotka": j, "posledni_cena": Decimal(str(c))})[0]

        stavy = {s.nazev: s for s in StavZakazky.objects.all()}
        def stav_pro(i):  # starší zakázky jsou vydané, nejnovější rozpracované
            if i in (12, 33): return "Zrušeno"
            if i < 30: return "Vydáno"
            return ["Připraveno k vyzvednutí", "Opraveno", "Čeká na díl", "Rozpracováno",
                    "Čeká na schválení", "Diagnostika", "Nová"][min((i - 30) // 3, 6)]

        stejny = {}
        for idx, n, q, c in STEJNY_MATERIAL: stejny.setdefault(idx, []).append((n, q, c))

        # Zakázky: 1 zakázka = 1 zařízení, přijetí rozložené od ledna do 21. 10. 2026
        start = datetime(2026, 1, 7, 8, 0)
        krok = (datetime(2026, 10, 20, 15, 0) - start) / 49
        n_ukon = n_mat = 0
        for i, (zr, zavada) in enumerate(zarizeni):
            prijeti = start + krok * i + timedelta(minutes=rnd.randint(0, 300))
            prijeti = prijeti.replace(hour=rnd.randint(7, 16), minute=rnd.choice([0, 10, 15, 20, 30, 40, 45, 50]), second=0, microsecond=0)
            sn = stav_pro(i)
            stav = stavy.get(sn) or stavy.get("Nová")
            vydani = _dt(prijeti + timedelta(days=rnd.randint(3, 14), hours=2)) if sn == "Vydáno" else None
            z = Zakazka.objects.create(zakaznik=zr.zakaznik, stav=stav, datum_prijeti=_dt(prijeti), datum_vydani=vydani,
                                       identifikacni_cislo=f"{prijeti:%y%m%d}{i + 1:02d}", popis_zavady=zavada,
                                       sekundarni_cislo=f"OBJ-{rnd.randint(1000, 9999)}" if zr.zakaznik.typ_zakaznika == "Firma" else "",
                                       poznamka="Zákazník zakázku zrušil po diagnostice." if sn == "Zrušeno" else "")
            Zakazka.objects.filter(pk=z.pk).update(datum_vytvoreni=_dt(prijeti))
            z.zarizeni.add(zr)
            t = tech[i % 3]
            z.zamestnanci.add(t)
            if sn in ("Nová",): continue

            # Provedené práce
            def ukon(nazev, poznamka=""):
                p, lo, hi = UKONY[nazev]
                u = ProvedenyUkon.objects.create(zakazka=z, typ_ukonu=typy[nazev], cena=Decimal(rnd.randrange(lo, hi + 1, 50)),
                                                 sazba_dph=Decimal(21), poznamka=poznamka)
                u.zamestnanci.add(t)
                ProvedenyUkon.objects.filter(pk=u.pk).update(datum_vytvoreni=_dt(prijeti + timedelta(days=1)))
                return u
            ukon("Diagnostika", "Prověření funkčnosti")
            n_ukon += 1
            if sn in ("Diagnostika", "Čeká na schválení", "Zrušeno"): continue
            hlavni = rnd.choice(["Oprava", "Výměna dílu", "Výměna ložisek", "Čištění a údržba", "Seřízení"])
            if i % 11 == 7: hlavni = "Převinutí motoru"
            ukon(hlavni, zavada.split(",")[0].rstrip(".")); n_ukon += 1
            if rnd.random() < 0.3: ukon("Revize elektro" if "motorová" not in zr.popis.lower() else "Seřízení"); n_ukon += 1

            # Materiál
            pouzit = list(stejny.get(i, []))
            if not pouzit:
                klic = next((kk for kk in MAT_PODLE_TYPU if kk in zr.popis.lower()), None)
                moznosti = MAT_PODLE_TYPU.get(klic, ["Spínač ON/OFF", "Kondenzátor odrušovací"])
                for n in rnd.sample(moznosti, k=min(len(moznosti), rnd.randint(1, 2))):
                    c = next(c for nn, j, c in MATERIAL if nn == n)
                    q = rnd.choice([30, 50, 80]) if mats[n].jednotka == "g" else (rnd.choice([1, 2]) if mats[n].jednotka == "ks" else 1)
                    pouzit.append((n, q, c))
            if rnd.random() < 0.4: pouzit.append(("Šrouby a drobný spojovací materiál", 1, 30))
            for n, q, c in pouzit:
                PouzityMaterial.objects.create(zakazka=z, material=mats[n], mnozstvi=Decimal(str(q)),
                                               jednotkova_cena=Decimal(str(c)), sazba_dph=Decimal(21))
                n_mat += 1

        self.stdout.write(self.style.SUCCESS(
            f"Hotovo: {len(zakaznici)} zákazníků, {len(zarizeni)} zařízení, 50 zakázek, {len(zam)} zaměstnanci, "
            f"{len(typy)} typů úkonů, {len(mats)} materiálů, {n_ukon} provedených úkonů, {n_mat} položek materiálu."))
