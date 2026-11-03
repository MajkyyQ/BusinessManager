# Přibalené knihovny třetích stran

Soubory jsou součástí aplikace, aby fungovala i bez připojení k internetu (např. jen v místní síti firmy).

| Soubor | Knihovna | Verze | Licence |
|---|---|---|---|
| `bootstrap.min.css` | Bootstrap (https://getbootstrap.com/) | 5.3.3 | MIT |
| `htmx.min.js` | htmx (https://htmx.org/) | 2.0.3 | 0BSD |

Staženo z registru npm (`npm pack bootstrap@5.3.3 htmx.org@2.0.3`), soubory nejsou upravené
(jen z `bootstrap.min.css` je odstraněn odkaz na neexistující `.map` soubor).
Při aktualizaci verze nahraďte oba soubory a upravte tuto tabulku.
