# Audio Opus - baza wiedzy asystenta

## Zasady odpowiedzi

Jestes asystentem aplikacji Audio Opus. Odpowiadaj po polsku, konkretnie i
krok po kroku. Uzywaj dokladnych nazw zakladek i przyciskow z aplikacji.
Odpowiadaj tylko na podstawie tej dokumentacji i informacji podanych przez
uzytkownika.

Nie wymyslaj funkcji, liczb, wynikow, przyciskow ani ustawien. Asystent nie ma
bezposredniego dostepu do biezacej bazy SQLite, aktualnych raportow, adresow
e-mail ani statusu wysylki. Gdy pytanie dotyczy takich danych, powiedz:
"Nie mam dostepu do biezacych danych w tej rozmowie. Sprawdz to w zakladce
Start, Platformy albo Raport." Nie udawaj, ze wykonal operacje w programie.

Jesli pytanie jest niejasne, zadaj jedno pytanie doprecyzowujace. Jesli temat
nie jest opisany tutaj, powiedz, ze nie masz potwierdzonej informacji, zamiast
zgadywac.

## Nawigacja

Glowne zakladki to: Start, Klienci, Produkty, Platformy, Raport i Asystent.
Debug jest widoczny tylko po wlaczeniu trybu debugowania w Ustawieniach.
Dostepne sa tez Ustawienia i Pomoc.

Okno startuje zmaksymalizowane. F11 wlacza lub wylacza pelny ekran, a Ctrl+M
minimalizuje okno.

## Start

Start pokazuje liczbe klientow, produktow, raportow miesiecznych, netto w
ostatnim roku i ostrzezen. Wykres Wyniki roczne netto porownuje sume netto dla
kazdego roku obecnego w danych. Sekcja Priorytety pokazuje brakujace adresy
e-mail, ISBN-y i przypisania produktow do platform. Sekcja Stan rozliczen i
aktywnosc pokazuje podsumowanie raportow, pozycje zrodlowe i ostatnie pliki.

Szybkie akcje na Start to: Dodaj klienta, Dodaj produkt, Importuj raport oraz
Utworz rozliczenie. Dane Start odswiezaja sie automatycznie.

## Klienci

Aby dodac klienta:

1. Otworz zakladke Klienci.
2. Kliknij Dodaj klienta.
3. Podaj nazwe i opcjonalnie adres e-mail.
4. Wybierz przypisane produkty.
5. Zapisz formularz.

Pusta nazwa klienta jest odrzucana. Brak e-maila nie blokuje zapisu, ale jest
pokazywany w Priorytetach i moze utrudnic wysylke raportu.

Aby edytowac klienta, zaznacz go i otworz edycje. Aby usunac klienta, zaznacz
go i kliknij Usun. Usunieci klienci trafiaja do Kosza, gdzie mozna ich
przywrocic albo usunac trwale.

Pole Szukaj klienta filtruje dane klienta i przypisane produkty.

## Produkty

Aby dodac produkt:

1. Otworz zakladke Produkty.
2. Kliknij Dodaj ksiazke.
3. Wprowadz Tytul i Autora.
4. Uzupelnij ISBN, Wydawnictwo, Procent, Typ Rozliczenia i prog, jesli jest
   wymagany.
5. Zapisz produkt.

Produkt edytuje sie przez dwuklik albo przycisk Edytuj, nie bezposrednio w
komorce tabeli. Aby usunac produkt, zaznacz go i kliknij Usun ksiazke.
Usuniety produkt trafia do Kosza.

Procent musi miescic sie w zakresie 0-100. Typy rozliczenia to instant i
threshold. Pole Prog dotyczy typu threshold i musi byc nieujemne.

Wydawnictwo mozna wybrac z listy klientow albo wpisac recznie. Fuzzy search
jest domyslnie wlaczony i pomaga znalezc tytul lub autora mimo literowek.
Brak ISBN-u jest pokazywany jako ostrzezenie na Start.

## Platformy i import raportu

Aby dodac platforme, wejdz w Platformy, kliknij Dodaj platforme i podaj nazwe.
Nazwa nie moze byc pusta ani powtorzona bez wzgledu na wielkosc liter. Edycja
nazwy aktualizuje przypisania, a usuniecie platformy usuwa jej przypisania,
ale nie usuwa zapisanych raportow.

Aby zaimportowac raport:

1. Otworz Platformy.
2. Kliknij Przelicz Raporty.
3. Kliknij Dodaj raport.
4. Wybierz platforme, rok i plik.
5. Sprawdz status pliku.

Dialog wyboru przyjmuje pliki .xlsx, .xls, .csv, .ods, .pdf i .zip. To, czy
plik da sie przeliczyc, zalezy od jego typu i poprawnego mapowania kolumn.
Jeden plik dotyczy jednego roku. Raport obejmujacy wiele lat moze zostac
odrzucony. Raport tej samej platformy i roku moze zastapic poprzedni plik.

Zielony status oznacza rozpoznany uklad, czerwony oznacza potrzebe dopasowania
kolumn albo poprawienia roku.

## Dopasowanie kolumn

Gdy raport jest nierozpoznany:

1. Zaznacz raport i kliknij Dopasuj kolumny.
2. Wybierz Pojedyncze transakcje, Raport miesieczny albo Raport kwartalny.
3. Wskaz wymagane pola: Nazwa ksiazki, ISBN, Data / okres i Wynagrodzenie
   netto.
4. Opcjonalnie wskaz Autora, Liczbe jednostek, Wynagrodzenie brutto, VAT i
   Typ sprzedazy.
5. Wszystkie wybrane naglowki musza byc z jednego wiersza i roznych kolumn.
6. Kliknij Zapisz konfiguracje.

Mapowanie jest zapamietywane dla platformy i ukladu naglowkow. Nastepny plik
o takim samym ukladzie moze zostac rozpoznany automatycznie.

Kliknij Przelicz raporty, wybierz rok i co najmniej jedna platforme. Program
zapisze podsumowania miesieczne, roczne i kwartalne. Nierozpoznane ksiazki
moga otworzyc okno Dodawanie ksiazki z opcjami Dodaj, Pomin i dalej oraz
Zakoncz.

## Raporty platform

Raporty miesieczne pokazuja ksiazke, ISBN, miesiac, klienta, platformy i kwoty.
Dwuklik raportu miesiecznego otwiera transakcje zrodlowe.

Raporty roczne grupuja dane calego roku dla ksiazki. Pokazuja wiecej danych
niz pojedynczy miesiac, dlatego uzyj filtra Rok, aby zawazyc widok, np. do
2026. Raporty kwartalne zachowuja dokladny zakres dat przekazany przez
platforme.

Kosz raportow pozwala raport przywrocic albo usunac trwale.

## Raport PDF i rozliczenie

Aby wygenerowac PDF:

1. Otworz Raport.
2. Kliknij Nowe rozliczenie (PDF).
3. Wybierz klienta i okres rozliczenia.
4. Dodaj produkty oraz platformy.
5. Uzupelnij kwoty netto, brutto i prowizje.
6. Kliknij Generuj raport PDF.

Numer rozliczenia ma format RRRR/MM/NNN. Pusty numer jest dozwolony, ale
uzycie istniejacego numeru wymaga potwierdzenia nadpisania. Wymagany jest
klient i co najmniej jedna kompletna pozycja. Kazda pozycja musi miec
platforme, liczbowe kwoty i prowizje 0-100%.

Dla produktu typu threshold rozliczenie uwzglednia prog. Prowizja moze
pochodzic z pozycji, produktu albo klienta, zalezne od konfiguracji.

## Wysylka e-mail

Aby wyslac raport:

1. Otworz Raport.
2. Kliknij Wybierz dane i wyslij raport.
3. Wygeneruj PDF albo wybierz istniejacy plik.
4. Wybierz odbiorcow.
5. Sprawdz potwierdzenie i wyslij.

Dostepne sa adresy klientow, wlasne adresy oraz pole Dodatkowe adresy.
Niepoprawny adres blokuje wysylke. Ustawienia SMTP znajduja sie w
Ustawienia -> E-mail. Transport korzysta z SSL, a haslo pochodzi ze zmiennej
SMTP_PASSWORD albo systemowego magazynu poswiadczen.

Historia wysylki pozwala filtrowac wpisy po adresie, pliku i statusie.

## Ustawienia i dane

Sekcje Ustawien to: Wyglad, E-mail, Dane, Debugowanie i Skroty klawiszowe.
Wyglad pozwala wybrac motyw jasny/ciemny i kolor przewodni.

Dane pozwalaja wykonac Eksportuj kopie bazy oraz Wczytaj kopie bazy. Import
sprawdza plik SQLite, wymaga potwierdzenia, nadpisuje dane i odswieza zakladki.
Przypomnienie o kopii pojawia sie po 28 dniach lub gdy kopii nie wykonano.

Skroty mozna zapisac przyciskiem Zapisz skroty albo przywrocic przez Przywroc
domyslne. Duplikaty skrotow sa odrzucane.

## Skróty

- Ctrl+N dodaje klienta.
- Ctrl+Shift+N dodaje produkt.
- Ctrl+F ustawia fokus wyszukiwania.
- Ctrl+E wysyla raport e-mail.
- Ctrl+K otwiera kalkulator.
- Ctrl+1 do Ctrl+4 przelacza zakladki Klienci, Produkty, Platformy i Raport.
- F11 wlacza pelny ekran.
- Ctrl+M minimalizuje okno.
- Ctrl i kolko myszy zmienia rozmiar tabeli tam, gdzie widget to obsluguje.

## Kalkulatory

Przycisk Kalkulatory otwiera narzedzia prowizji, progow, procentow, lektorow,
VAT i podsumowan netto/brutto. Nie podawaj wyniku bez danych wejsciowych.

## Pytania i odpowiedzi

### Jak dodac klienta?

Wejdz w Klienci, kliknij Dodaj klienta, podaj nazwe, opcjonalny e-mail,
wybierz produkty i zapisz.

### Jak dodac produkt?

Wejdz w Produkty, kliknij Dodaj ksiazke, uzupelnij tytul i autora oraz dane
rozliczeniowe, a potem zapisz.

### Jak zaimportowac raport?

Wejdz w Platformy, kliknij Przelicz Raporty, Dodaj raport, wybierz platforme,
rok i plik. Jezeli plik jest czerwony, uzyj Dopasuj kolumny.

### Co zrobic, gdy raport jest czerwony?

Zaznacz plik, kliknij Dopasuj kolumny, ustaw rodzaj danych, wskaz wymagane
kolumny i kliknij Zapisz konfiguracje.

### Jak zobaczyc transakcje zrodlowe?

W Platformy otworz widok Raporty miesieczne i dwukrotnie kliknij wybrany
wiersz.

### Dlaczego raport roczny ma wiecej wierszy?

Raport roczny obejmuje caly rok, a miesieczny tylko jeden miesiac. Uzyj filtra
Rok, aby ograniczyc liste.

### Jak wygenerowac PDF?

Wejdz w Raport, kliknij Nowe rozliczenie (PDF), wybierz klienta, dodaj kompletne
pozycje i kliknij Generuj raport PDF.

### Jak wyslac raport e-mailem?

W Raport kliknij Wybierz dane i wyslij raport, wybierz plik lub wygeneruj PDF,
wybierz odbiorcow i zaakceptuj potwierdzenie.

### Co zrobic, gdy e-mail nie wychodzi?

Sprawdz konfiguracje SMTP w Ustawienia -> E-mail, poprawny adres odbiorcy,
haslo w keyringu lub SMTP_PASSWORD oraz istnienie pliku smtp_config.json.

### Jak zrobic kopie bazy?

Wejdz w Ustawienia -> Dane i kliknij Eksportuj kopie bazy.

### Jak przywrocic kopie?

Wejdz w Ustawienia -> Dane, kliknij Wczytaj kopie bazy, wybierz poprawny plik
SQLite i potwierdz nadpisanie danych.

### Dlaczego asystent nie odpowiada?

Sprawdz, czy Ollama dziala lokalnie. W zakladce Asystent kliknij Przygotuj
asystenta. Model qwen2.5:1.5b moze potrzebowac chwili przy pierwszym pytaniu,
bo jest wtedy ladowany do pamieci.

### Czy asystent widzi aktualna baze?

Nie. Asystent zna dokumentacje aplikacji, ale nie ma dostepu do aktualnych
rekordow, kwot, adresow e-mail ani statusu wysylki. Takie informacje trzeba
sprawdzic bezposrednio w odpowiedniej zakladce.
