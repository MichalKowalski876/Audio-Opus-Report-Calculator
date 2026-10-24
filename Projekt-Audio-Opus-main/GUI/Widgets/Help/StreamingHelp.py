from GUI.Widgets.Help.Base.HelpPage import HelpPage


class StreamingHelp(HelpPage):
    def __init__(self):
        super().__init__(
            "Platformy",
            (
                "Dodawanie plików sprzedażowych, konfigurowanie ich układu oraz "
                "przeliczanie raportów platform streamingowych. Dane trafiają do "
                "wspólnej bazy SQLite i nie są wpisywane pojedynczo ręcznie."
            ),
        )

        self.add_section(
            "Tutorial importu raportu",
            (
                "Obok przycisku pomocy znajduje się przełącznik „Kroki”. Po jego "
                "włączeniu aplikacja subtelnie podświetla najważniejsze czynności. "
                "Wszystkie kroki bieżącego widoku pozostają widoczne jednocześnie. "
                "Dymki pokazują numery, a po najechaniu na podświetlony element — "
                "krótki opis. Każdy widok ma własną numerację: główny ekran prowadzi "
                "przez dodanie platformy i wejście do raportów, lista raportów przez "
                "dodanie pliku, dopasowanie kolumn i przeliczenie, a konfigurator "
                "przez wybór nagłówków z Excela i zapis. Dymki znikają dopiero po "
                "zmianie widoku albo ponownym kliknięciu „Kroki”, które wyłącza "
                "cały tutorial."
            ),
        )

        self.add_section(
            "Główny widok",
            (
                "Po lewej stronie znajduje się lista platform, a po prawej "
                "miesięczne, kwartalne lub roczne podsumowania książek ze wszystkich "
                "platform. Przeciągając linię między tabelami, można zmienić "
                "szerokość obu części."
            ),
        )
        self.add_step(
            1,
            (
                "Przełącz widok przyciskami „Raporty miesięczne”, „Raporty "
                "kwartalne” i „Raporty roczne”. Widok kwartalny zachowuje dokładny "
                "zakres dat podany przez platformę."
            ),
        )
        self.add_step(
            2,
            (
                "Filtruj wyniki po nazwie książki, ISBN, okresie lub roku oraz "
                "kliencie. Lista zawęża się podczas pisania."
            ),
        )
        self.add_step(
            3,
            (
                "Dwukrotnie kliknij raport miesięczny, aby zobaczyć transakcje "
                "źródłowe. Jeżeli plik zawierał tylko gotowe podsumowanie "
                "miesięczne, aplikacja poinformuje o braku listy transakcji."
            ),
        )
        self.add_step(
            4,
            (
                "Dwukrotnie kliknij raport roczny, aby zobaczyć jego miesiące "
                "osobno dla każdej platformy. W oknach szczegółów można wybrać "
                "jedną platformę albo „Wszystkie platformy”."
            ),
        )

        self.add_section(
            "Platformy",
            "Przyciski nad lewą tabelą służą do zarządzania listą platform.",
        )
        self.add_step(1, "Kliknij „Dodaj platformę” i podaj jej nazwę.")
        self.add_step(
            2,
            (
                "Aby zmienić nazwę, zaznacz platformę i kliknij „Edytuj” albo "
                "dwukrotnie kliknij jej wiersz."
            ),
        )
        self.add_step(
            3,
            (
                "Przycisk „Usuń” usuwa platformę z aktywnej listy i przypisań "
                "książek. Wcześniej przeliczone dane pozostają w historii."
            ),
        )

        self.add_section(
            "Dodawanie pliku raportu",
            (
                "Kliknij „Przelicz Raporty”, a następnie „Dodaj raport”. W tym "
                "oknie wybierz „Załącz raport z pulpitu” albo „Załącz raport z "
                "maila”. Wybierz platformę i rok, którego dotyczą dane. Przy "
                "imporcie z poczty wybierz załącznik wiadomości, a aplikacja "
                "skopiuje raport do katalogu Raporty Platform właściwego roku."
            ),
        )
        self.add_step(
            1,
            (
                "Rok wybierz zgodnie z zawartością raportu. Ta wartość określa "
                "katalog pliku i zakres późniejszego przeliczania. Jeśli zapisane "
                "mapowanie pozwala odczytać daty, aplikacja porówna je z wybranym "
                "rokiem i zaproponuje automatyczną korektę."
            ),
        )
        self.add_step(
            2,
            (
                "Po dodaniu sprawdź status pliku na liście: zielony oznacza "
                "rozpoznany układ, a czerwony wymaga dopasowania kolumn albo "
                "poprawienia roku wskazanego w komunikacie."
            ),
        )

        self.add_section(
            "Dlaczego trzeba konfigurować kolumny?",
            (
                "Platformy używają różnych nazw i układów kolumn. Ten sam rodzaj "
                "danych może nazywać się na przykład „Tytuł”, „Nazwa produktu” "
                "albo jeszcze inaczej. Konfiguracja mówi aplikacji, która kolumna "
                "zawiera książkę, ISBN, okres i kwoty. Bez tego program nie może "
                "bezpiecznie przypisać danych i oznacza raport na czerwono."
            ),
        )
        self.add_section(
            "Co aplikacja zapamiętuje?",
            (
                "Mapowanie jest zapisywane dla konkretnej platformy i konkretnego "
                "układu nagłówków Excela. Następny plik tej platformy o takim samym "
                "układzie zostanie rozpoznany automatycznie. Jeżeli platforma zmieni "
                "nazwy kolumn albo ich układ, nowy wariant trzeba skonfigurować raz."
            ),
        )

        self.add_section(
            "Konfigurowanie raportu — krok po kroku",
            (
                "Konfigurację otwiera przycisk „Dopasuj kolumny” po zaznaczeniu "
                "pliku na liście raportów."
            ),
        )
        self.add_step(
            1,
            (
                "W polu „Rodzaj danych” wybierz „Pojedyncze transakcje”, gdy "
                "każdy wiersz opisuje jedną sprzedaż, „Raport miesięczny”, gdy "
                "wiersz jest gotowym podsumowaniem książki za miesiąc, albo "
                "„Raport kwartalny”, gdy platforma podaje nieregularny zakres dat."
            ),
        )
        self.add_step(
            2,
            (
                "Uzupełnij pola oznaczone gwiazdką: Nazwa książki, ISBN, Data / "
                "okres i Wynagrodzenie netto. Dla transakcji wskaż datę sprzedaży, "
                "dla raportu miesięcznego kolumnę z miesiącem, a dla kwartalnego "
                "kolumnę zawierającą pełny zakres dat od–do."
            ),
        )
        self.add_step(
            3,
            (
                "Jeżeli raport je zawiera, dopasuj pola opcjonalne: Autor, "
                "Wynagrodzenie brutto, VAT, Typ sprzedaży i Liczbę jednostek. "
                "Liczba jednostek jest szczególnie przydatna w rozliczeniach "
                "kwartalnych. Gdy nie ma kolumny brutto, ale jest stawka VAT, "
                "aplikacja może wyliczyć brutto z kwoty netto. Kolumna Autor "
                "pozwala automatycznie uzupełnić autora przy dopisywaniu nowych "
                "książek znalezionych w raporcie."
            ),
        )
        self.add_step(
            4,
            (
                "Nazwę nagłówka możesz wpisać dokładnie tak, jak widnieje w pliku, "
                "albo kliknąć ikonę Excela obok pola."
            ),
        )
        self.add_step(
            5,
            (
                "Po kliknięciu ikony wybierz arkusz zawierający tabelę i kliknij "
                "komórkę nagłówka danej kolumny — nie komórkę z danymi książki. "
                "Nazwa zostanie przeniesiona do konfiguratora automatycznie."
            ),
        )
        self.add_step(
            6,
            (
                "Powtórz wybór dla kolejnych pól. Wszystkie wskazane nagłówki "
                "muszą pochodzić z tego samego arkusza i tego samego wiersza. "
                "Każde pole musi wskazywać inną kolumnę."
            ),
        )
        self.add_step(
            7,
            (
                "Jeśli wybierzesz złą komórkę, ponownie kliknij ikonę przy tym "
                "polu i wskaż poprawną. Nie trzeba wychodzić z konfiguracji."
            ),
        )
        self.add_step(
            8,
            (
                "Kliknij „Zapisz konfigurację”. Dopiero wtedy aplikacja sprawdzi "
                "kompletność, powtórzone kolumny oraz zgodność arkusza i wiersza. "
                "Jeśli pojawi się komunikat, popraw wskazane pole i zapisz ponownie."
            ),
        )
        self.add_step(
            9,
            (
                "Po poprawnym zapisie wrócisz do listy. Raport powinien otrzymać "
                "zielony status i będzie gotowy do przeliczenia."
            ),
        )

        self.add_section(
            "Przeliczanie raportów",
            (
                "Kliknij „Przelicz raporty”, wybierz jeden rok albo zaznacz "
                "„Wszystkie lata”, wybierz platformy, a następnie zatwierdź. "
                "Program odczyta tylko rozpoznane pliki, dopasuje książki "
                "po ISBN i zapisze transakcje, miesięczne podsumowania oraz "
                "nieregularne rozliczenia kwartalne w osobnej tabeli SQLite. "
                "Po zakończeniu aplikacja pokaże listę raportów ze statusem "
                "przeliczenia i liczbą odczytanych pozycji. Przy nieprzeliczonym "
                "raporcie zobaczysz przyczynę oraz prostą podpowiedź, na przykład "
                "„Skonfiguruj kolumny raportu” albo „Przypisz raport do właściwego "
                "roku”. Błąd jednego pliku nie zatrzymuje poprawnych raportów: "
                "zostaną one zapisane, a wadliwy raport zostanie pominięty. Wyniki "
                "pojawią się w głównym widoku Platformy."
            ),
        )

        self.add_section(
            "Książki spoza bazy",
            (
                "Jeśli przeliczony raport zawiera książkę, której nie ma jeszcze "
                "w bazie, włączy się przycisk „Uzupełnij bazę”. Przeliczanie nie "
                "otwiera formularzy automatycznie. Kliknij ten przycisk, gdy chcesz "
                "przejrzeć wykryte braki. Tytuł, autor i ISBN są od razu "
                "wypełnione danymi z raportu."
            ),
        )
        self.add_step(1, "„Dodaj” zapisuje książkę do bazy.")
        self.add_step(
            2,
            (
                "„Pomiń i dalej” przechodzi do kolejnej nierozpoznanej książki "
                "bez zapisywania tej."
            ),
        )
        self.add_step(
            3,
            "„Zakończ” przerywa dodawanie pozostałych książek z tego przeliczenia.",
        )
        self.add_step(
            4,
            (
                "Jeśli pole Wydawnictwo zostanie puste, a Autor jest uzupełniony, "
                "autor automatycznie staje się klientem tej książki i pojawia się "
                "na liście w zakładce Klienci."
            ),
        )

        self.add_section(
            "Usuwanie raportów i kosz",
            (
                "Przycisk „Usuń” przenosi wybrany plik do kosza, skąd można go "
                "przywrócić. „Usuń trwale” kasuje plik oraz dane zaimportowane z "
                "tego konkretnego raportu w SQLite. Dane pochodzące z pozostałych "
                "raportów nie są usuwane. Jeśli w bazie są książki dopisane "
                "wyłącznie na podstawie usuwanego raportu, aplikacja zapyta, czy "
                "przenieść je też do kosza produktów."
            ),
        )

        self.finish()
