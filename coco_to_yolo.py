import json
import os

def coco_do_yolo_seg_z_folderu(plik_coco_json, folder_zdjec, folder_wyjsciowy):
    # Wczytujemy pobrany plik COCO
    with open(plik_coco_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    os.makedirs(folder_wyjsciowy, exist_ok=True)

    # 1. Tworzymy "notatki" z JSONa 
    info_o_zdjeciach = {img['id']: img for img in data.get('images', [])}
    
    # file_name -> lista sformatowanych linii YOLO dla segmentacji
    adnotacje_dla_pliku = {}
    
    for ann in data.get('annotations', []):
        img_id = ann['image_id']
        if img_id not in info_o_zdjeciach:
            continue
            
        img_info = info_o_zdjeciach[img_id]
        nazwa_pliku = img_info['file_name']
        
        # Kluczowa zmiana: sprawdzamy czy istnieje poligon segmentacji
        if 'segmentation' not in ann or not ann['segmentation']:
            continue
            
        # Pobieramy pierwszą tablicę z punktami poligonu [x1, y1, x2, y2, ...]
        poligon = ann['segmentation'][0]
        img_w, img_h = img_info['width'], img_info['height']
        
        znormalizowane_punkty = []
        
        # Iterujemy co 2 (najpierw bierzemy x, a zaraz potem przypisanego do niego y)
        for i in range(0, len(poligon), 2):
            x_norm = poligon[i] / img_w
            y_norm = poligon[i+1] / img_h
            # Zapisujemy do 6 miejsc po przecinku
            znormalizowane_punkty.append(f"{x_norm:.6f} {y_norm:.6f}")

        kategoria_id = 0 # Wciąż mamy tylko jedną klasę
        
        # Tworzymy długą linię tekstu: 0 x1 y1 x2 y2 x3 y3...
        linia_yolo = f"{kategoria_id} " + " ".join(znormalizowane_punkty) + "\n"
        
        if nazwa_pliku not in adnotacje_dla_pliku:
            adnotacje_dla_pliku[nazwa_pliku] = []
        adnotacje_dla_pliku[nazwa_pliku].append(linia_yolo)

    # 2. Skanujemy FIZYCZNY folder ze zdjęciami
    fizyczne_zdjecia = [f for f in os.listdir(folder_zdjec) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    zapisane_ramki = 0
    puste_pliki = 0
    
    print(f"[INFO] Odczytano {len(fizyczne_zdjecia)} zdjęć bezpośrednio z folderu wejściowego.")
    print("Generuję pliki poligonów .txt dla segmentacji (w tym próbki negatywne)...")
    
    for plik_img in fizyczne_zdjecia:
        nazwa_bez_rozszerzenia = os.path.splitext(plik_img)[0]
        plik_txt = f"{nazwa_bez_rozszerzenia}.txt"
        sciezka_zapisu = os.path.join(folder_wyjsciowy, plik_txt)
        
        with open(sciezka_zapisu, 'w') as f:
            if plik_img in adnotacje_dla_pliku:
                for linia in adnotacje_dla_pliku[plik_img]:
                    f.write(linia)
                    zapisane_ramki += 1
            else:
                puste_pliki += 1
                
    print(f"\n[SUKCES] Wygenerowano etykiety segmentacyjne w folderze: {folder_wyjsciowy}")
    print(f"-> Zapisano poligonów: {zapisane_ramki}")
    print(f"-> Wygenerowano pustych plików (Negative Samples): {puste_pliki}")

if __name__ == "__main__":
    PLIK_JSON = r"labels_my-project-name_2026-07-04-08-36-54.json" 
    FOLDER_ZDJEC = r"F:\WEBSCRAPER\wytrenowane_zdjecia" 
    FOLDER_DOCELOWY = r"F:\WEBSCRAPER\etykiety_surowe"
    
    coco_do_yolo_seg_z_folderu(PLIK_JSON, FOLDER_ZDJEC, FOLDER_DOCELOWY)