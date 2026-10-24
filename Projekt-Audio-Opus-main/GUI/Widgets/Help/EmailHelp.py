from GUI.Widgets.Help.Base.HelpPage import HelpPage

class EmailHelp(HelpPage):
    def __init__(self):
        super().__init__(
            "Raport e-mail",
            "Generowanie raportów i wysyłanie ich e-mailem do wybranych odbiorców."
        )

        self.add_section(
            "Wysyłanie raportu",
            "Aby przygotować i wysłać raport:"
        )

        self.add_step(1, "Wybierz klienta z listy.")
        self.add_step(2, "Wprowadź dane potrzebne do przygotowania rozliczenia.")
        self.add_step(3, "Sprawdź poprawność wprowadzonych informacji.")
        self.add_step(4, "Wygeneruj raport i załącz go do e-maila.")
        self.add_step(5, "W oknie wyboru odbiorców zaznacz maile, na które ma trafić raport, i wyślij.")

        self.add_section(
            "Wybór odbiorców",
            "Adres e-mail wybranego klienta jest od razu zaznaczony i wyróżniony na liście. "
            "Możesz jednak zaznaczyć dodatkowo inne adresy z listy (np. innych klientów lub "
            "własne) albo dopisać ręcznie dowolny adres w polu poniżej - raport trafi do "
            "wszystkich zaznaczonych odbiorców."
        )
        self.add_section(
            "Problemy z wysyłaniem",
            "Jeżeli wiadomość nie może zostać wysłana, sprawdź adres e-mail klienta oraz ustawienia poczty w aplikacji."
        )

        self.finish()
