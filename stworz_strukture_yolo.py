import os
import random
import shutil

def stworz_strukture_yolo(folder_zdjec, folder_etykiet, folder_docelowy, split_ratio=0.8):
    # 1. BEZWZGLĘDNE CZYSZCZENIE STAREGO ZBIORU
    if os.path.exists(folder_docelowy):
        print(f"[INFO] Wykryto stary zbiór danych. Trwa usuwanie folderu: {folder_docelowy}...")
        shutil.rmtree(folder_docelowy)
        print("[INFO] Stary zbiór usunięty.")

    # 2. Tworzenie czystych ścieżek
    dirs_to_make = [
        os.path.join(folder_docelowy, 'images', 'train'),
        os.path.join(folder_docelowy, 'images', 'val'),
        os.path.join(folder_docelowy, 'labels', 'train'),
        os.path.join(folder_docelowy, 'labels', 'val')
    ]
    
    for d in dirs_to_make:
        os.makedirs(d, exist_ok=True)

    # 3. Pobranie wszystkich zdjęć
    pliki_zdjec = [f for f in os.listdir(folder_zdjec) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    # Mieszanie (tasowanie) zdjęć, aby zbiory były różnorodne
    random.shuffle(pliki_zdjec)

    # Obliczanie punktu podziału
    split_index = int(len(pliki_zdjec) * split_ratio)
    train_zdjecia = pliki_zdjec[:split_index]
    val_zdjecia = pliki_zdjec[split_index:]

    print(f"\n[INFO] Rozpoczynam kopiowanie {len(pliki_zdjec)} plików do nowej struktury...")

    def kopiuj_paczke(lista_plikow, folder_przeznaczenia):
        skopiowane = 0
        pominiete = 0
        
        for plik_img in lista_plikow:
            nazwa_bez_rozszerzenia = os.path.splitext(plik_img)[0]
            plik_txt = f"{nazwa_bez_rozszerzenia}.txt"

            sciezka_img_src = os.path.join(folder_zdjec, plik_img)
            sciezka_txt_src = os.path.join(folder_etykiet, plik_txt)

            # Kopiujemy TYLKO jeśli etykieta istnieje (puste pliki dla negative samples też się liczą)
            if os.path.exists(sciezka_txt_src):
                shutil.copy(sciezka_img_src, os.path.join(folder_docelowy, 'images', folder_przeznaczenia, plik_img))
                shutil.copy(sciezka_txt_src, os.path.join(folder_docelowy, 'labels', folder_przeznaczenia, plik_txt))
                skopiowane += 1
            else:
                pominiete += 1
                
        return skopiowane, pominiete

    skop_train, pom_train = kopiuj_paczke(train_zdjecia, 'train')
    skop_val, pom_val = kopiuj_paczke(val_zdjecia, 'val')

    # 4. Automatyczne generowanie pliku data.yaml
    sciezka_yaml = os.path.join(folder_docelowy, 'data.yaml')
    with open(sciezka_yaml, 'w') as f:
        # Używamy forward slashy, bo YOLO woli taki format w plikach konfiguracyjnych
        f.write(f"train: {os.path.join(folder_docelowy, 'images', 'train').replace(os.sep, '/')}\n")
        f.write(f"val: {os.path.join(folder_docelowy, 'images', 'val').replace(os.sep, '/')}\n\n")
        f.write("nc: 1\n")
        f.write("names: ['microsd']\n")

    print(f"\n[SUKCES] Zbudowano nowy, czysty zbiór danych w: {folder_docelowy}")
    print(f"-> Trening: {skop_train} par (pominięto {pom_train} zdjęć bez etykiet)")
    print(f"-> Walidacja: {skop_val} par (pominięto {pom_val} zdjęć bez etykiet)")
    print(f"-> Wygenerowano plik: {sciezka_yaml}")

if __name__ == "__main__":
    ZDJECIA = r"F:\WEBSCRAPER\wytrenowane_zdjecia"
    ETYKIETY = r"F:\WEBSCRAPER\etykiety_surowe"
    DOCELOWY = r"F:\WEBSCRAPER\dataset_yolo"
    
    stworz_strukture_yolo(ZDJECIA, ETYKIETY, DOCELOWY)