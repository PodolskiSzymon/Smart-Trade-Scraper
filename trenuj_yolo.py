import os
import re
import datetime
import torch
from ultralytics import YOLO

# --- FUNKCJA DO AUTOMATYCZNEGO NAZEWNICTWA ---
def wyznacz_kolejna_nazwe(baza_nazwy="microsd_detektor_v", folder_zapisu=r"runs\detect"):
    """Skanuje folder i zwraca kolejną wolną nazwę z datą, np. microsd_detektor_v3_03-07"""
    data_dzisiaj = datetime.datetime.now().strftime("%d-%m")
    
    if not os.path.exists(folder_zapisu):
        return f"{baza_nazwy}2_{data_dzisiaj}"
        
    max_wersja = 1
    # Wzorzec szukający numeru wersji w nazwie folderu
    wzorzec = re.compile(rf"^{baza_nazwy}(\d+)_.*$")
    
    for folder in os.listdir(folder_zapisu):
        sciezka_pelna = os.path.join(folder_zapisu, folder)
        if os.path.isdir(sciezka_pelna):
            dopasowanie = wzorzec.match(folder)
            if dopasowanie:
                wersja = int(dopasowanie.group(1))
                if wersja > max_wersja:
                    max_wersja = wersja
                    
    return f"{baza_nazwy}{max_wersja + 1}_{data_dzisiaj}"


# --- BRAMKARZ DLA WINDOWSA ---
if __name__ == '__main__':
    # --- DIAGNOSTYKA GPU ---
    print("--- SPRAWDZANIE ŚRODOWISKA ---")
    if torch.cuda.is_available():
        nazwa_gpu = torch.cuda.get_device_name(0)
        print(f"[INFO] Sukces! Wykryto kartę graficzną: {nazwa_gpu}")
        urzadzenie = 0 
    else:
        print("[BŁĄD] PyTorch nie widzi karty graficznej (CUDA).")
        urzadzenie = 'cpu'
    print("------------------------------\n")

    # Wyznaczamy nową nazwę z datą
    nazwa_eksperymentu = wyznacz_kolejna_nazwe()
    print(f"[INFO] Ten trening zostanie zapisany jako: {nazwa_eksperymentu}")

    # 1. Pobieramy model bazowy
    model = YOLO('yolov8n-seg.pt')

    print("[INFO] Rozpoczynam trening modelu YOLOv8...")

    # 2. Uruchamiamy trening
    results = model.train(
        data='F:/WEBSCRAPER/dataset_yolo/data.yaml',
        epochs=200,            
        imgsz=640,             
        batch=16,              
        patience=30,           
        optimizer='AdamW',     
        name=nazwa_eksperymentu, 
        workers=4,             
        device=urzadzenie      
    )

    print(f"[INFO] Trening zakończony! Wyniki zapisano w: runs/detect/{nazwa_eksperymentu}")