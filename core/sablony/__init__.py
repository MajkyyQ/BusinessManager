"""Systém šablon výstupních dokumentů.

Tři oddělené vrstvy:
  typy.py      – typy dokumentů: katalog polí a sestavení dat z databáze (zdroj pravdy)
  renderery.py – formáty šablon (Excel, HTML): z šablony a dat vyrobí náhled a PDF
  models.SablonaDokumentu – uložená šablona (soubor + mapování), nikdy nemění data
"""
