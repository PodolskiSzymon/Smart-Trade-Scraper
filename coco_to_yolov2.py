import json
import os

def coco_do_yolo_z_folderu(plik_coco_json, folder_zdjec, folder_wyjsciowy):
    # Wczytujemy pobrany plik COCO
    with open(plik_coco_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    os.makedirs(folder_wyjsciowy, exist_ok=True)

    # 1. Tworzymy "notatki" z JSONa (tylko o tych zdjęciach, które tam są)
    # img_id -> file_name (oraz wymiary do normalizacji)
    info_o_zdjeciach = {img['id']: img for img in data.get('images', [])}
    
    # file_name -> lista sformatowanych linii YOLO
    adnotacje_dla_pliku = {}
    
    for ann in data.get('annotations', []):
        img_id = ann['image_id']
        if img_id not in info_o_zdjeciach:
            continue
            
        img_info = info_o_zdjeciach[img_id]
        nazwa_pliku = img_info['file_name']
        
        # Konwersja COCO -> YOLO
        x, y, w, h = ann['bbox']
        img_w, img_h = img_info['width'], img_info['height']

        srodek_x = (x + (w / 2)) / img_w
        srodek_y = (y + (h / 2)) / img_h
        norm_w = w / img_w
        norm_h = h / img_h

        kategoria_id = 0 # Masz tylko jedną klasę: microsd, więc ID to 0
        linia_yolo = f"{kategoria_id} {srodek_x:.6f} {srodek_y:.6f} {norm_w:.6f} {norm_h:.6f}\n"
        
        if nazwa_pliku not in adnotacje_dla_pliku:
            adnotacje_dla_pliku[nazwa_pliku] = []
        adnotacje_dla_pliku[nazwa_pliku].append(linia_yolo)


    # 2. Skanujemy FIZYCZNY folder ze zdjęciami (to jest nasze główne źródło prawdy)
    fizyczne_zdjecia = [f for f in os.listdir(folder_zdjec) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    zapisane_ramki = 0
    puste_pliki = 0
    
    print(f"[INFO] Odczytano {len(fizyczne_zdjecia)} zdjęć bezpośrednio z folderu wejściowego.")
    print("Generuję pliki .txt (w tym próbki negatywne)...")
    
    for plik_img in fizyczne_zdjecia:
        nazwa_bez_rozszerzenia = os.path.splitext(plik_img)[0]
        plik_txt = f"{nazwa_bez_rozszerzenia}.txt"
        sciezka_zapisu = os.path.join(folder_wyjsciowy, plik_txt)
        
        # Zawsze otwieramy plik w trybie 'w' (nadpisuje stary lub tworzy nowy)
        with open(sciezka_zapisu, 'w') as f:
            
            # Jeśli MakeSense miało to zdjęcie w adnotacjach, wpisujemy je
            if plik_img in adnotacje_dla_pliku:
                for linia in adnotacje_dla_pliku[plik_img]:
                    f.write(linia)
                    zapisane_ramki += 1
            else:
                # Jeśli MakeSense pominęło to zdjęcie, plik zostaje całkowicie pusty (0 bajtów)
                puste_pliki += 1
                
    print(f"\n[SUKCES] Wygenerowano etykiety w folderze: {folder_wyjsciowy}")
    print(f"-> Zapisano ramek: {zapisane_ramki}")
    print(f"-> Wygenerowano pustych plików (Negative Samples): {puste_pliki}")

if __name__ == "__main__":
    # UWAGA: Doszedł nowy parametr - musisz wskazać, gdzie fizycznie leżą zdjęcia
    PLIK_JSON = r"F:\WEBSCRAPER\my_labels.json" 
    FOLDER_ZDJEC = r"F:\WEBSCRAPER\wytrenowane_zdjecia" # Zmień na swój właściwy folder ze zdjęciami
    FOLDER_DOCELOWY = r"F:\WEBSCRAPER\etykiety_surowe"
    
    coco_do_yolo_z_folderu(PLIK_JSON, FOLDER_ZDJEC, FOLDER_DOCELOWY)