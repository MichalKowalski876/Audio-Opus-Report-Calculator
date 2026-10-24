"""Logika aplikacji Audio Opus (dane, rozliczenia, e-mail, konfiguracja).

Moduły w tym pakiecie nie zależą od GUI (poza `report_generator`, który
używa Qt do renderowania PDF) - można je testować i importować niezależnie
od `GUI`, `Integrations` czy `platforms`. Punkt wejścia aplikacji (`main.py`)
zostaje w katalogu głównym repo, poza tym pakietem.
"""
