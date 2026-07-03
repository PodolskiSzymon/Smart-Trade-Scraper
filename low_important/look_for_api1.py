import requests
import time
import random

# Konfiguracja
base_url = "https://www.vinted.pl/api/v2/items/8540661190/plugins/"
wordlist_file = "f:/WEBSCRAPER/wordlist.txt" # Upewnij się, że ścieżka jest poprawna

# Sesja z Twoim User-Agentem i ciasteczkami (żeby przechodzić przez zabezpieczenia)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def start_fuzzing():
    try:
        with open(wordlist_file, 'r', encoding='utf-8') as f:
            endpoints = f.read().splitlines()
            
        print(f"Załadowano {len(endpoints)} endpointów do sprawdzenia.\n")
        
        for endpoint in endpoints:
            # Pomiń puste linie
            if not endpoint.strip():
                continue
                
            url = f"{base_url}{endpoint.strip()}"
            
            try:
                response = session.get(url, allow_redirects=False, timeout=5)
                
                # Reagujemy na różne kody statusu
                if response.status_code == 200:
                    print(f"[!!!] ZNALEZIONO 200: {url}")
                elif response.status_code == 400:
                    print(f"--- [400] {endpoint} (Istnieje, brak parametrów)")
                elif response.status_code == 403:
                    print(f"--- [403] {endpoint} (Zablokowane)")
                
                # Losowe opóźnienie (pomiędzy 0.5 a 1.5 sekundy)
                # To najważniejszy parametr chroniący Twoje konto przed banem
                time.sleep(random.uniform(0.5, 1.5))
                
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] Błąd połączenia z {endpoint}: {e}")
                
    except FileNotFoundError:
        print(f"Błąd: Nie znaleziono pliku {wordlist_file}")

if __name__ == "__main__":
    start_fuzzing()