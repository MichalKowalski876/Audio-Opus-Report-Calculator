# Audio Opus

Aplikacja desktopowa (PySide6/Qt) do rozliczania tantiem wydawnictwa
audiobooków z klientami (wydawnictwa/autorzy) na podstawie sprzedaży na
platformach streamingowych (Legimi, Storytel, Voices, Audioteka i inne).
Generuje brandowane raporty rozliczeniowe w PDF i wysyła je e-mailem.

## Wymagania

- Python 3.12 lub 3.13 (3.14 działa, ale to środowisko deweloperskie - CI
  dopuszcza na nim błędy, dopóki na Linuksie nie ma stabilnych wheeli
  PySide6 dla cp314),
- Windows - aplikacja jest rozwijana i dystrybuowana głównie na Windows
  (integracja z systemowym magazynem poświadczeń, budowanie `.exe`), ale
  działa też na macOS/Linux w trybie deweloperskim.

## Uruchomienie w trybie deweloperskim na Windows
 
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python3 main.py
```
## Uruchomienie w trybie deweloperskim na Linux
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```
## Wyjście z wirtualnego środowiska (Linux/Windows)
```bash
deactivate                  
```

Pusta baza startowa (`Databases/db.sqlite`) i niesekretna konfiguracja są w
repozytorium. Aplikacja uruchomiona ze źródeł czyta i zapisuje bezpośrednio do
katalogu projektu (patrz [`core/paths.py`](core/paths.py)). Bazy zawierającej
rzeczywiste dane oraz kopii `*.sqlite` nie wolno commitować.

### Poczta (SMTP)

Wysyłka raportów e-mailem wymaga danych logowania SMTP. Hasło **nigdy** nie
jest trzymane w pliku - aplikacja czyta je ze zmiennej środowiskowej
`SMTP_PASSWORD` albo z systemowego magazynu poświadczeń (`keyring`, usługa
`Audio Opus SMTP`). Adres nadawcy i serwer konfiguruje się w zakładce
Ustawienia -> E-mail, albo ręcznie w `Databases/smtp_config.json` (wzór:
[`Databases/smtp_config.example.json`](Databases/smtp_config.example.json) -
ten plik jest gitignorowany, nigdy nie commituj do niego prawdziwego hasła).

### Gmail (podgląd poczty w zakładce Debug)

Opcjonalne, tylko do odczytu. Wymaga własnego klienta OAuth z Google Cloud
Console. W trybie deweloperskim jego plik należy zapisać jako
`Integrations/Gmail/Config/credentials.json` (gitignorowany; wzór:
`credentials.example.json`). W wersji EXE plik należy umieścić w
`%APPDATA%\Audio Opus\Integrations\Gmail\Config\credentials.json`. Klucze nie
są wbudowywane w EXE. Integracja nie jest potrzebna do generowania i wysyłki
rozliczeń.

## Testy

```bash
pip install -r requirements-dev.txt
pytest -q
```

CI (`.github/workflows/tests.yml`) odpala ten sam zestaw na Python
3.12/3.13/3.14 (Ubuntu, Qt w trybie `offscreen`) przy każdym pushu/PR do
`main`.

## Struktura repozytorium

```
core/            logika aplikacji niezależna od GUI - baza (SQLite), generator
                 PDF, wysyłka e-mail, kalkulatory prowizji/arkuszy, ścieżki
GUI/             interfejs PySide6 - okna, zakładki, dialogi, style (qss)
Integrations/    integracja z Gmail API (tylko podgląd skrzynki, opcjonalne)
platforms/       import i przeliczanie raportów platform streamingowych
                 (parsowanie Excela, dopasowanie książek po ISBN/tytule)
tests/           pytest - lustrzana struktura względem katalogów powyżej
Databases/       dane aplikacji: db.sqlite (klienci/produkty/rozliczenia)
                 + pliki konfiguracyjne JSON
Reports/         wygenerowane raporty PDF/xlsx (w całości gitignorowane)
Assets/          logo, ikony
Installer/       domyślne dane do zaszycia w budowanym .exe
```

`main.py` to punkt wejścia aplikacji i zostaje poza pakietem `core/` -
tak samo referuje go [`AudioOpus.spec`](AudioOpus.spec).

## Budowanie pliku EXE (Windows)

Zobacz [`BUILD_EXE.md`](BUILD_EXE.md) - w skrócie: `.\build_exe.ps1` buduje
`dist\Audio Opus.exe` przez PyInstaller, korzystając z
[`AudioOpus.spec`](AudioOpus.spec).
