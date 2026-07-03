import os
import hashlib

def usun_duplikaty_i_zmien_nazwy(sciezka_do_folderu, numer_startowy=1):
    # Upewniamy się, że ścieżka istnieje
    if not os.path.exists(sciezka_do_folderu):
        print(f"[BŁĄD] Podana ścieżka nie istnieje: {sciezka_do_folderu}")
        return

    unikalne_hasze = {}
    duplikaty_do_usuniecia = []

    print(f"--- ETAP 1: SZUKANIE I USUWANIE DUPLIKATÓW ---")
    
    for nazwa_pliku in os.listdir(sciezka_do_folderu):
        pelna_sciezka = os.path.join(sciezka_do_folderu, nazwa_pliku)
        
        if os.path.isfile(pelna_sciezka):
            hasz_pliku = hashlib.sha256()
            try:
                with open(pelna_sciezka, 'rb') as plik:
                    for chunk in iter(lambda: plik.read(65536), b""):
                        hasz_pliku.update(chunk)
                
                odcisk = hasz_pliku.hexdigest()
                
                if odcisk in unikalne_hasze:
                    print(f"Znaleziono duplikat: {nazwa_pliku} (taki sam jak {unikalne_hasze[odcisk]})")
                    duplikaty_do_usuniecia.append(pelna_sciezka)
                else:
                    unikalne_hasze[odcisk] = nazwa_pliku
                    
            except Exception as e:
                print(f"Nie można odczytać pliku {nazwa_pliku}: {e}")

    for duplikat in duplikaty_do_usuniecia:
        try:
            os.remove(duplikat)
            print(f"Usunięto: {os.path.basename(duplikat)}")
        except Exception as e:
            print(f"Błąd podczas usuwania {duplikat}: {e}")

    print(f"\n--- ETAP 2: ZMIANA NAZW PLIKÓW (START OD: zdj{numer_startowy}) ---")
    
    pozostale_pliki = [p for p in os.listdir(sciezka_do_folderu) if os.path.isfile(os.path.join(sciezka_do_folderu, p))]
    
    # Ustawiamy licznik na wartość podaną przez Ciebie
    licznik = numer_startowy
    
    for stara_nazwa in pozostale_pliki:
        stara_sciezka = os.path.join(sciezka_do_folderu, stara_nazwa)
        _, rozszerzenie = os.path.splitext(stara_nazwa)
        
        oczekiwana_nazwa = f"zdj{licznik}{rozszerzenie.lower()}"
        
        if stara_nazwa != oczekiwana_nazwa:
            nowa_sciezka = os.path.join(sciezka_do_folderu, oczekiwana_nazwa)
            
            while os.path.exists(nowa_sciezka):
                licznik += 1
                nowa_sciezka = os.path.join(sciezka_do_folderu, f"zdj{licznik}{rozszerzenie.lower()}")
                
            try:
                os.rename(stara_sciezka, nowa_sciezka)
            except Exception as e:
                print(f"Błąd podczas zmiany nazwy {stara_nazwa}: {e}")
                
        licznik += 1

    print(f"\n[GOTOWE] Zakończono! Zostało {len(pozostale_pliki)} unikalnych zdjęć. Ostatni numer to zdj{licznik - 1}.")


# ==========================================
# UŻYCIE SKRYPTU
# ==========================================
if __name__ == "__main__":
    folder_ze_zdjeciami = r"F://WEBSCRAPER//zdjecia" 
    
    # Podajesz numer, od którego skrypt ma zacząć numerację
    poczatkowy_numer = 1
    
    usun_duplikaty_i_zmien_nazwy(folder_ze_zdjeciami, numer_startowy=poczatkowy_numer)