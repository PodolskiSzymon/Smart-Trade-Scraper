import os
import hashlib
import re

def oblicz_hasz_pliku(pelna_sciezka):
    """Funkcja pomocnicza do bezpiecznego obliczania odcisku SHA-256 pliku."""
    hasz_pliku = hashlib.sha256()
    try:
        with open(pelna_sciezka, 'rb') as plik:
            for chunk in iter(lambda: plik.read(65536), b""):
                hasz_pliku.update(chunk)
        return hasz_pliku.hexdigest()
    except Exception as e:
        print(f"[BŁĄD] Nie można odczytać pliku {pelna_sciezka}: {e}")
        return None

def znajdz_najwyzszy_numer(sciezka):
    """Szuka plików w formacie zdj{X}.ext i zwraca najwyższą znalezioną liczbę X."""
    max_num = 0
    # Wzorzec: zaczyna się od "zdj", potem ma cyfry, a potem kropkę i rozszerzenie
    wzorzec = re.compile(r"^zdj(\d+)\.[a-zA-Z0-9]+$", re.IGNORECASE)
    
    for plik in os.listdir(sciezka):
        dopasowanie = wzorzec.match(plik)
        if dopasowanie:
            numer = int(dopasowanie.group(1))
            if numer > max_num:
                max_num = numer
    return max_num

def usun_duplikaty_i_zmien_nazwy(sciezka_bazowa, sciezka_do_oczyszczenia):
    # Upewniamy się, że oba foldery istnieją
    if not os.path.exists(sciezka_bazowa):
        print(f"[BŁĄD] Folder bazowy nie istnieje: {sciezka_bazowa}")
        return
    if not os.path.exists(sciezka_do_oczyszczenia):
        print(f"[BŁĄD] Folder do oczyszczenia nie istnieje: {sciezka_do_oczyszczenia}")
        return

    hasze_zbioru_bazowego = set()
    duplikaty_do_usuniecia = []

    print(f"--- ETAP 1: INDEKSOWANIE ZBIORU WYTRENOWANEGO ---")
    print(f"Skanowanie folderu: {sciezka_bazowa}")
    
    for nazwa_pliku in os.listdir(sciezka_bazowa):
        pelna_sciezka = os.path.join(sciezka_bazowa, nazwa_pliku)
        if os.path.isfile(pelna_sciezka):
            odcisk = oblicz_hasz_pliku(pelna_sciezka)
            if odcisk:
                hasze_zbioru_bazowego.add(odcisk)
                
    print(f"Zaindeksowano {len(hasze_zbioru_bazowego)} unikalnych plików w zbiorze bazowym.\n")

    print(f"--- ETAP 2: SPRAWDZANIE NOWYCH ZDJĘĆ ---")
    print(f"Skanowanie folderu: {sciezka_do_oczyszczenia}")
    
    for nazwa_pliku in os.listdir(sciezka_do_oczyszczenia):
        pelna_sciezka = os.path.join(sciezka_do_oczyszczenia, nazwa_pliku)
        
        if os.path.isfile(pelna_sciezka):
            odcisk = oblicz_hasz_pliku(pelna_sciezka)
            
            # Jeśli odcisk znajduje się już w naszym "zbiorze bazowym", to jest to duplikat
            if odcisk in hasze_zbioru_bazowego:
                print(f"Znaleziono duplikat: {nazwa_pliku} (znajduje się już w 'wytrenowane_zdjecia')")
                duplikaty_do_usuniecia.append(pelna_sciezka)

    print(f"\n--- ETAP 3: USUWANIE DUPLIKATÓW ---")
    if not duplikaty_do_usuniecia:
        print("Nie znaleziono żadnych duplikatów. Folder nowych zdjęć jest czysty.")
    else:
        for duplikat in duplikaty_do_usuniecia:
            try:
                os.remove(duplikat)
                print(f"Usunięto: {os.path.basename(duplikat)}")
            except Exception as e:
                print(f"Błąd podczas usuwania {duplikat}: {e}")
                
        print(f"Usunięto łącznie {len(duplikaty_do_usuniecia)} powielonych zdjęć.")

    print(f"\n--- ETAP 4: ZMIANA NAZW NOWYCH ZDJĘĆ ---")
    najwyzszy_bazowy = znajdz_najwyzszy_numer(sciezka_bazowa)
    licznik = najwyzszy_bazowy + 1
    
    print(f"Najwyższy znaleziony numer w '{os.path.basename(sciezka_bazowa)}' to: {najwyzszy_bazowy}")
    print(f"Rozpoczynam numerację nowych plików od: zdj{licznik}")

    # Pobieramy pliki, które przetrwały usuwanie
    pozostale_pliki = [p for p in os.listdir(sciezka_do_oczyszczenia) if os.path.isfile(os.path.join(sciezka_do_oczyszczenia, p))]
    
    zmieniono_nazw = 0
    for stara_nazwa in pozostale_pliki:
        stara_sciezka = os.path.join(sciezka_do_oczyszczenia, stara_nazwa)
        _, rozszerzenie = os.path.splitext(stara_nazwa)
        
        # Tworzymy nową nazwę zachowując oryginalne rozszerzenie (np. .png lub .jpg)
        oczekiwana_nazwa = f"zdj{licznik}{rozszerzenie.lower()}"
        nowa_sciezka = os.path.join(sciezka_do_oczyszczenia, oczekiwana_nazwa)
        
        # Pętla while zabezpiecza nas przed nadpisaniem plików, 
        # jeśli w nowym folderze jakimś cudem są już pliki typu "zdj15.png"
        while os.path.exists(nowa_sciezka) and stara_sciezka != nowa_sciezka:
            licznik += 1
            oczekiwana_nazwa = f"zdj{licznik}{rozszerzenie.lower()}"
            nowa_sciezka = os.path.join(sciezka_do_oczyszczenia, oczekiwana_nazwa)
        
        if stara_sciezka != nowa_sciezka:
            try:
                os.rename(stara_sciezka, nowa_sciezka)
                zmieniono_nazw += 1
            except Exception as e:
                print(f"Błąd podczas zmiany nazwy {stara_nazwa}: {e}")
        
        licznik += 1

    print(f"\n[GOTOWE] Zakończono! Zmieniono nazwy {zmieniono_nazw} plików.")
    print(f"Ostatni przypisany numer to: zdj{licznik - 1}")


# ==========================================
# UŻYCIE SKRYPTU
# ==========================================
if __name__ == "__main__":
    folder_wytrenowane = r"F:\WEBSCRAPER\wytrenowane_zdjecia" 
    folder_nowe = r"F:\WEBSCRAPER\zdjecia" 
    
    usun_duplikaty_i_zmien_nazwy(sciezka_bazowa=folder_wytrenowane, sciezka_do_oczyszczenia=folder_nowe)