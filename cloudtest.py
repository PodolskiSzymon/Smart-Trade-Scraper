from google.cloud import storage

def wyslij_do_chmury(nazwa_bucketa, sciezka_lokalna, nazwa_docelowa):
    # Tworzymy klienta, który automatycznie znajdzie token logowania z terminala
    klient = storage.Client()
    
    # Łączymy się z Twoim wiaderkiem
    wiaderko = klient.bucket(nazwa_bucketa)
    
    # Przygotowujemy "puste miejsce" w chmurze
    plik_w_chmurze = wiaderko.blob(nazwa_docelowa)
    
    # Wysyłamy plik
    print(f"Wysyłam plik z {sciezka_lokalna}...")
    plik_w_chmurze.upload_from_filename(sciezka_lokalna)
    print("Sukces! Zdjęcie jest już na serwerach Google.")

if __name__ == "__main__":
    # Nazwa Twojego zasobnika utworzonego przed chwilą
    NAZWA_ZASOBNIKA = "smart-trade-scraper"
    
    # ZMIEŃ TO: ścieżka do jakiegoś fizycznego zdjęcia na dysku F:
    PLIK_Z_DYSKU = r"F:\WEBSCRAPER\jakies_zdjecie.jpg" 
    
    # Gdzie to ma trafić (od razu tworzymy wirtualny folder 01_landing_zone)
    MIEJSCE_W_CHMURZE = "01_landing_zone/moje_pierwsze_zdjecie.jpg"
    
    wyslij_do_chmury(NAZWA_ZASOBNIKA, PLIK_Z_DYSKU, MIEJSCE_W_CHMURZE)