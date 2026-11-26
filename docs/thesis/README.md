# Bakalářská práce

*Návrh a implementace systému pro evidenci servisních zakázek a automatizovanou tvorbu faktur*
Univerzita Jana Evangelisty Purkyně v Ústí nad Labem, Přírodovědecká fakulta, Aplikovaná informatika, 2026.

**Hotové PDF: [ki-thesis.pdf](ki-thesis.pdf)**

## Obsah složky

| Cesta | Co obsahuje |
|:--|:--|
| `ki-thesis.tex` | hlavní soubor práce (načítá kapitoly a přílohy) |
| `kapitoly/` | text jednotlivých kapitol (`dokumentace/`, `navrh/`, `reserse/` jsou vložené podkapitoly) |
| `prilohy/` | přílohy práce |
| `obrazky/` | obrázky a snímky obrazovek použité v práci |
| `er-diagram/` | ER diagramy databáze (PDF a PNG) |
| `reserse/` | podklady k rešerši existujících systémů a bibliografie rešerše (`reserse.bib`) |
| `thesis.bib` | bibliografie práce |
| `kitheses.cls`, `LOGO_PRF_*.jpg`, `LICENSE` | šablona KI UJEP pro závěrečné práce (šablona je pod licencí GPL-3.0, viz `LICENSE`) |
| `monotypář.pdf` | ukázka neproporcionálních písem ze šablony |

## Sestavení PDF

Potřeba je TeX Live nebo MiKTeX s `latexmk` a `biber`:

    latexmk -pdf ki-thesis.tex

Pomocné soubory LaTeXu (`.aux`, `.log`, `.bbl`, …) se do repozitáře neukládají (viz `.gitignore`).
