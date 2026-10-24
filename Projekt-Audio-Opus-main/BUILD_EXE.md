# Budowanie Audio Opus do pliku EXE

## Wymagania

- Windows 10 lub Windows 11,
- Python 3.11 lub nowszy dostępny jako `py` albo `python`,
- połączenie z internetem podczas pierwszego budowania.

## Budowanie

W PowerShell, w katalogu projektu:

```powershell
.\build_exe.ps1
```

Skrypt tworzy oddzielne środowisko `.build-env`, instaluje zależności i buduje:

```text
dist\Audio Opus.exe
```

Przy kolejnych buildach można pominąć instalowanie zależności:

```powershell
.\build_exe.ps1 -SkipDependencyInstall
```

## Dane aplikacji

Kod, style i grafiki są częścią pliku EXE. Dane zmieniane podczas pracy są
przechowywane trwale w:

```text
%APPDATA%\Audio Opus
```

Znajdują się tam katalogi `Databases` i `Reports`. Dzięki temu aktualizacja
pliku EXE nie usuwa bazy klientów, produktów, ustawień ani raportów.

Przy pierwszym uruchomieniu aplikacja skopiuje aktualną bazę startową
`Databases/db.sqlite` do katalogu danych użytkownika. Jeżeli użytkownik ma już
własną bazę, nie zostanie ona nadpisana podczas aktualizacji programu.
Do pierwszego uruchomienia dołączane są również raporty znajdujące się w
`Reports`.

Konfiguracja SMTP wbudowana w program nie zawiera adresu ani hasła. Hasło
jest zapisywane przez aplikację w systemowym magazynie poświadczeń Windows.

Konfiguracja klienta Google OAuth nie jest dołączana do EXE ani zapisywana
w repozytorium. Po instalacji należy umieścić własny plik:

```text
%APPDATA%\Audio Opus\Integrations\Gmail\Config\credentials.json
```

W trybie deweloperskim odpowiada temu ścieżka
`Integrations\Gmail\Config\credentials.json` w katalogu projektu. Wzór pliku
znajduje się w `credentials.example.json`; nie wolno wpisywać do niego
prawdziwych kluczy. `token.json` również nie jest dołączany do EXE: powstaje
dopiero po zalogowaniu i jest zapisywany w:

```text
%APPDATA%\Audio Opus\Integrations\Gmail\Config\token.json
```

Plików `credentials.json` i `token.json` nie należy commitować ani dołączać do
archiwów dystrybucyjnych.

Katalog danych można zmienić zmienną środowiskową `AUDIO_OPUS_DATA_DIR`.
Przy pierwszym uruchomieniu kopiowane są również dołączone raporty. Kolejne
wersje programu nie nadpisują bazy, konfiguracji ani raportów użytkownika.

## Dystrybucja

Plik EXE nie jest podpisany cyfrowo. Przy pobieraniu go na inny komputer
Windows SmartScreen może wyświetlić ostrzeżenie o nieznanym wydawcy. Usunięcie
tego ostrzeżenia wymaga zakupienia certyfikatu do podpisywania kodu i podpisania
gotowego pliku przed dystrybucją.
