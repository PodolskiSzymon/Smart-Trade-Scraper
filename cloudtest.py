from google.cloud import storage

def wyslij_do_chmury(nazwa_bucketa, sciezka_lokalna, nazwa_docelowa, id_projektu):
    # TERAZ KLIENT WIE, DO JAKIEGO PROJEKTU SIĘ PODŁĄCZYĆ
    klient = storage.Client(project=id_projektu)
    
    wiaderko = klient.bucket(nazwa_bucketa)
    plik_w_chmurze = wiaderko.blob(nazwa_docelowa)
    
    print(f"Wysyłam plik z {sciezka_lokalna}...")
    plik_w_chmurze.upload_from_filename(sciezka_lokalna)
    print("Sukces! Zdjęcie jest już na serwerach Google.")

if __name__ == "__main__":
    # Identyfikator Twojego projektu (skopiowany z Twojej konsoli)
    MOJ_PROJEKT = "project-6ffdf12f-c10d-4003-8bf"
    
    NAZWA_ZASOBNIKA = "smart_trade_scraper"
    
    # Upewnij się, że podajesz prawdziwą ścieżkę do pliku, np.:
    PLIK_Z_DYSKU = r"F:\WEBSCRAPER\dataset_yolo\images\train\zdj1.png" 
    
    MIEJSCE_W_CHMURZE = "01_landing_zone/moje_pierwsze_zdjecie.jpg"
    
    wyslij_do_chmury(NAZWA_ZASOBNIKA, PLIK_Z_DYSKU, MIEJSCE_W_CHMURZE, MOJ_PROJEKT)