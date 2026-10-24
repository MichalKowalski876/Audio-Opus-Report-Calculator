from GUI.Widgets.Help.Base.HelpPage import HelpPage

class ClientsHelp(HelpPage):
    def __init__(self):
        super().__init__(
            "Klienci",
            "Zarządzanie klientami oraz przypisanymi do nich produktami."
        )

        self.add_section(
            "Dodawanie klienta",
            "Aby utworzyć nowego klienta:"
        )

        self.add_step(1, "Kliknij przycisk „Dodaj klienta”.")
        self.add_step(2, "Wprowadź nazwę klienta.")
        self.add_step(3, "Ustaw prowizję klienta.")
        self.add_step(4, "Wybierz przypisane produkty.")
        self.add_step(5, "Zapisz klienta.")

        self.add_section(
            "Usuwanie klienta",
            "Zaznacz klienta na liście i kliknij przycisk „Usuń”."
        )

        self.add_section(
            "Klienci dodawani automatycznie",
            (
                "Podczas dopisywania nowej książki znalezionej w raporcie "
                "platformy, jeśli zostawisz pole Wydawnictwo puste, a raport "
                "zawierał kolumnę Autor, aplikacja utworzy klienta o nazwie "
                "autora (lub kilku autorów rozdzielonych przecinkami, jeśli "
                "książka ma współautorów) i od razu przypisze mu tę książkę."
            ),
        )

        self.finish()