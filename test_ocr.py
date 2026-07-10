import easyocr
import re
import os

# Inicjalizacja sieci neuronowej. 
# Robimy to raz na zewnątrz funkcji, żeby model załadował się do RAM/VRAM tylko przy starcie programu.
# 'en' wystarczy, bo interesują nas głównie techniczne, uniwersalne oznaczenia.
reader = easyocr.Reader(['en']) 

def wyciagnij_parametry_z_karty(sciezka_do_zdjecia):
    """
    Czyta tekst ze zdjęcia za pomocą sieci neuronowej i wyciąga specyfikację techniczną.
    """
    # 1. Sieć neuronowa skanuje obraz i zwraca listę odczytanych fragmentów
    wyniki = reader.readtext(sciezka_do_zdjecia, detail=0)
    
    # Łączymy wszystko w jeden duży ciąg znaków i zamieniamy na wielkie litery dla ułatwienia
    caly_tekst = " ".join(wyniki).upper()
    print(f"[OCR] Odczytano z obrazu: {caly_tekst}")
    
    # 2. Filtracja danych (Wyrażenia Regularne)
    
    # Szukamy pojemności (np. 128GB, 64 GB, 1TB)
    pojemnosc_match = re.search(r'(\d+)\s*(GB|TB|MB)', caly_tekst)
    
    # Szukamy klasy prędkości wideo (V10, V30, V60, V90)
    klasa_v_match = re.search(r'(V\d{2})', caly_tekst)
    
    # Szukamy klasy aplikacji (A1, A2)
    klasa_a_match = re.search(r'(A[12])', caly_tekst)
    
    # Proste sprawdzenie marki (możesz tu rozbudować listę o Samsung, Lexar, Kingston)
    marka = None
    if "SANDISK" in caly_tekst:
        marka = "SanDisk"
    elif "SAMSUNG" in caly_tekst:
        marka = "Samsung"
        
    # 3. Zwracamy czysty, sformatowany słownik danych
    return {
        "pojemnosc": pojemnosc_match.group(0) if pojemnosc_match else None,
        "marka": marka,
        "klasa_video": klasa_v_match.group(0) if klasa_v_match else None,
        "klasa_aplikacji": klasa_a_match.group(0) if klasa_a_match else None,
    }

# Przykład użycia po zapisaniu pliku na dysku:
for en, photo in enumerate(os.listdir(r"F:\WEBSCRAPER\do_wytrenowania")):
        photo_lockal_path= f"F:/WEBSCRAPER/do_wytrenowania/{photo}"
        dane = wyciagnij_parametry_z_karty(photo_lockal_path)
        print(en, 'zdjecie o id: ', photo, 'ma dane: ', dane, "\n\n")
