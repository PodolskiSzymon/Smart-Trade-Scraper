import os
import hashlib

def generuj_hash_pliku(sciezka_do_pliku, rozmiar_chunka=8192):
    """
    Czyta plik w małych porcjach i generuje jego cyfrowy odcisk palca (MD5).
    Porcjowanie (chunking) chroni RAM przed zapchaniem przy gigantycznych plikach.
    """
    hasher = hashlib.md5()
    try:
        with open(sciezka_do_pliku, 'rb') as f:
            # Czytamy plik porcjami aż do końca (b"")
            for chunk in iter(lambda: f.read(rozmiar_chunka), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"[BŁĄD] Nie można wygenerować hasha dla {sciezka_do_pliku}: {e}")
        return None

def usun_duplikaty_zdjec(folder_docelowy):
    if not os.path.exists(folder_docelowy):
        print(f"[BŁĄD] Folder {folder_docelowy} nie istnieje.")
        return

    # Słownik, w którym będziemy trzymać unikalne hashe. 
    # Format: {'wygenerowany_hash': 'pierwsza_nazwa_pliku.png'}
    znalezione_hashe = {}
    licznik_usunietych = 0
    rozmiar_zwolniony = 0

    pliki = [f for f in os.listdir(folder_docelowy) if os.path.isfile(os.path.join(folder_docelowy, f))]
    
    # Filtrujemy, żeby skanować tylko grafikę
    rozszerzenia = ('.png', '.jpg', '.jpeg', '.webp')
    zdjecia = [f for f in pliki if f.lower().endswith(rozszerzenia)]

    print(f"Rozpoczynam skanowanie {len(zdjecia)} zdjęć w poszukiwaniu duplikatów...")

    for nazwa_pliku in zdjecia:
        sciezka = os.path.join(folder_docelowy, nazwa_pliku)
        hash_pliku = generuj_hash_pliku(sciezka)

        if not hash_pliku:
            continue

        # Jeśli taki hash już jest w naszym słowniku, to znaczy, że mamy duplikat
        if hash_pliku in znalezione_hashe:
            oryginalny_plik = znalezione_hashe[hash_pliku]
            rozmiar = os.path.getsize(sciezka)
            
            print(f"[KOSZ] Usuwam {nazwa_pliku} (jest dokładną kopią {oryginalny_plik})")
            
            # Bezpowrotne usunięcie pliku
            os.remove(sciezka)
            
            licznik_usunietych += 1
            rozmiar_zwolniony += rozmiar
        else:
            # Jeśli hasha nie było, zapisujemy go w pamięci jako "oryginał"
            znalezione_hashe[hash_pliku] = nazwa_pliku

    mb_zwolnione = rozmiar_zwolniony / (1024 * 1024)
    print("\n=== PODSUMOWANIE CZYSZCZENIA ===")
    print(f"Usuniętych duplikatów: {licznik_usunietych}")
    print(f"Odzyskane miejsce na dysku: {mb_zwolnione:.2f} MB")
    print(f"Pozostało unikalnych zdjęć: {len(znalezione_hashe)}")
def zmien_nazwy_zdjec(folder_docelowy, wartosc_startowa):
    # Sprawdzamy czy podany folder w ogóle istnieje
    if not os.path.exists(folder_docelowy):
        print(f"[BŁĄD] Folder {folder_docelowy} nie istnieje.")
        return

    # Pobieramy listę wszystkich plików w folderze
    pliki = [f for f in os.listdir(folder_docelowy) if os.path.isfile(os.path.join(folder_docelowy, f))]

    # Zabezpieczenie: filtrujemy tylko pliki graficzne
    rozszerzenia = ('.png', '.jpg', '.jpeg', '.webp')
    zdjecia = [f for f in pliki if f.lower().endswith(rozszerzenia)]

    if not zdjecia:
        print("[INFO] W podanym folderze nie ma żadnych zdjęć.")
        return

    print(f"Znaleziono {len(zdjecia)} zdjęć. Rozpoczynam zmianę nazw...")

    aktualny_numer = wartosc_startowa

    for stara_nazwa in zdjecia:
        stara_sciezka = os.path.join(folder_docelowy, stara_nazwa)
        
        # Wyciągamy oryginalne rozszerzenie pliku (np. .png)
        _, rozszerzenie = os.path.splitext(stara_nazwa)
        
        # Tworzymy nową nazwę
        nowa_nazwa = f"zdj{aktualny_numer}{rozszerzenie}"
        nowa_sciezka = os.path.join(folder_docelowy, nowa_nazwa)

        # Zabezpieczenie: jeśli z jakiegoś powodu plik o nowej nazwie już istnieje, 
        # program zapyta system o wolną ścieżkę, żeby niczego nie nadpisać
        if os.path.exists(nowa_sciezka):
            print(f"[!] Plik {nowa_nazwa} już istnieje! Pomijam {stara_nazwa}, żeby nie utracić danych.")
        else:
            try:
                os.rename(stara_sciezka, nowa_sciezka)
                print(f"Zmieniono: {stara_nazwa} -> {nowa_nazwa}")
            except Exception as e:
                print(f"[BŁĄD] Nie udało się zmienić nazwy {stara_nazwa}: {e}")

        aktualny_numer += 1

    print("\n=== GOTOWE! ===")
    print(f"Ostatni użyty numer to: {aktualny_numer - 1}")
# ==========================================
# URUCHOMIENIE
# ==========================================
if __name__ == "__main__":
    folder = r"F:\WEBSCRAPER\zdjecia_olx\microsd"
    usun_duplikaty_zdjec(folder)
    zmien_nazwy_zdjec(folder, 633   )