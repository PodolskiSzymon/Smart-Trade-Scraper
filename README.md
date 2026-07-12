Disclaimer: Ten projekt został stworzony wyłącznie w celach edukacyjnych i akademickich, jako pole do nauki trenowania modeli sztucznej inteligencji (YOLO) oraz inżynierii danych. Projekt nie jest używany w celach komercyjnych, nie obciąża serwerów platformy docelowej (rate limiting) i nie gromadzi danych osobowych użytkowników.

## ⚙️ Wymagania i Instalacja

Projekt do prawidłowego działania wymaga środowiska Python (wersja 3.8+) oraz relacyjnej bazy danych PostgreSQL (wykorzystywanej jako bufor kołowy zapobiegający duplikatom).

### 1. Zależności Pythona
Pobierz repozytorium, otwórz terminal w folderze projektu i zainstaluj niezbędne biblioteki zewnętrzne:

```bash
# Dla systemu Windows:
pip install requests psycopg2-binary playwright

# Dla systemu Linux (Debian/Ubuntu):
pip3 install requests psycopg2-binary playwright

Konfiguracja Playwright:
Moduł cookies_management.py wykorzystuje bibliotekę Playwright do symulowania rzeczywistej przeglądarki i automatycznego odświeżania wygasłych ciasteczek (omijanie zabezpieczeń Datadome/Cloudflare). Po instalacji samej biblioteki, musisz pobrać silnik Chromium. Wpisz w terminalu:
Konfiguracja Playwright:
Moduł cookies_management.py wykorzystuje bibliotekę Playwright do symulowania rzeczywistej przeglądarki i automatycznego odświeżania wygasłych ciasteczek (omijanie zabezpieczeń Datadome/Cloudflare). Po instalacji samej biblioteki, musisz pobrać silnik Chromium. Wpisz w terminalu:
playwright install chromium

    2. Konfiguracja Bazy Danych (PostgreSQL)
Skrypty opierają się na zapisywaniu "punktów stopu", dzięki czemu przy każdym cyklu pobierają wyłącznie nowe oferty, chroniąc Twoje IP przed zablokowaniem i oszczędzając transfer danych.

Zainstaluj serwer PostgreSQL (na Windowsie z oficjalnego instalatora, na systemach z rodziny Debian użyj sudo apt update && sudo apt install postgresql postgresql-contrib).

Otwórz konsolę psql lub pgAdmin i utwórz bazę danych o nazwie Postgre_Trade_Scraper.

Przełącz się na nową bazę i wykonaj poniższe komendy SQL, aby przygotować tabele:
-- Utworzenie tabeli bufora dla Vinted
CREATE TABLE punkty_stopu (
    id SERIAL PRIMARY KEY,
    vinted_id BIGINT UNIQUE NOT NULL,
    data_dodania TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Utworzenie tabeli bufora dla OLX
CREATE TABLE olx_punkty_stopu (
    id SERIAL PRIMARY KEY,
    kategoria VARCHAR(100) NOT NULL,
    olx_id BIGINT NOT NULL,
    data_dodania TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kategoria, olx_id)
);