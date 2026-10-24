from PySide6 import QtWidgets

from GUI.Widgets.Help.Base.HelpPage import HelpPage


class ProductsHelp(HelpPage):
    def __init__(self):
        super().__init__(
            "Produkty",
            "Zarządzanie produktami znajdującymi się w aplikacji."
        )

        self.add_section(
            "Dodawanie produktu",
            "Aby utworzyć nowy produkt:"
        )

        self.add_step(1, "Kliknij przycisk „Dodaj produkt”.")
        self.add_step(2, "Wprowadź tytuł produktu.")
        self.add_step(3, "Wprowadź autora produktu.")
        self.add_step(4, "Zapisz produkt.")

        self.add_section(
            "Edycja produktu",
            "Dane produktu można zmienić bezpośrednio w tabeli produktów."
        )

        self.add_step(1, "Znajdź produkt na liście.")
        self.add_step(2, "Kliknij pole, które chcesz zmienić.")
        self.add_step(3, "Wprowadź nową wartość.")

        self.add_section(
            "Wyszukiwanie produktów",
            "W polu wyszukiwania możesz użyć zwykłego filtrowania lub przełącznika „Fuzzy search”."
        )
        self.add_step(1, "Wyłączony przełącznik = wyszukiwanie dokładne, literka po literce.")
        self.add_step(2, "Włączony przełącznik = aplikacja dopasowuje podobne słowa i fragmenty tekstu, np. „ildfns” może znaleźć „Ildefons Rozrabia”.")
        self.add_step(3, "To pomaga, gdy nie pamiętasz dokładnie tytułu, autora albo wydawcy.")

        self.add_section(
            "Usuwanie produktu",
            "Zaznacz produkt na liście i kliknij przycisk „Usuń”."
        )

        self.finish()