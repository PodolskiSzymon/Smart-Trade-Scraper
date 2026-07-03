import os
import cv2
import shutil  # <--- DODANE (do kopiowania plików)
from ultralytics import YOLO

# 1. Ładujemy model
model = YOLO(r"F:\WEBSCRAPER\runs\detect\microsd_detektor_v2\weights\best.pt")

# 2. Ścieżki do folderów
folder_testowy = r"F:\WEBSCRAPER\zdjecia"
folder_val = r"F:\WEBSCRAPER\val_zdj"  # <--- DODANE (folder docelowy)

# Upewniamy się, że folder docelowy istnieje (jeśli nie, skrypt go stworzy)
os.makedirs(folder_val, exist_ok=True)

# Pobieramy listę wszystkich plików z folderu
pliki = [os.path.join(folder_testowy, f) for f in os.listdir(folder_testowy) 
         if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

if not pliki:
    print("Nie znaleziono żadnych zdjęć w folderze.")
    exit()

print(f"Znaleziono {len(pliki)} zdjęć. Uruchamiam detekcję...")
print("--- STEROWANIE ---")
print("-> Strzałka w Prawo (lub 'D'): Następne zdjęcie")
print("<- Strzałka w Lewo (lub 'A'): Poprzednie zdjęcie")
print("-> Strzałka w Górę (lub 'W') : Skopiuj zdjęcie do folderu val_zdj") # <--- DODANE
print("[Q] : Zakończ program")

indeks = 0
calkowita_liczba = len(pliki)
nazwa_okna = "Detekcja YOLO"

# Inicjalizujemy okno przed pętlą, aby móc dynamicznie zmieniać jego tytuł
cv2.namedWindow(nazwa_okna, cv2.WINDOW_NORMAL)

while True:
    sciezka = pliki[indeks]
    nazwa_pliku = os.path.basename(sciezka)
    
    # Model wykonuje przewidywanie "w locie" dla aktualnego zdjęcia
    results = model.predict(source=sciezka, conf=0.65, verbose=False)
    
    img_bgr = None
    for r in results:
        img_bgr = r.plot()  # r.plot() zwraca obraz w formacie BGR (OpenCV)
        
    if img_bgr is None:
        # Zabezpieczenie: jeśli YOLO nic nie przetworzy, ładujemy czysty obraz
        img_bgr = cv2.imread(sciezka)

    # Aktualizujemy tytuł okna
    cv2.setWindowTitle(nazwa_okna, f"Detekcja YOLO | Plik: {nazwa_pliku} ({indeks + 1}/{calkowita_liczba})")
    
    # Wyświetlamy zdjęcie
    cv2.imshow(nazwa_okna, img_bgr)
    
    # Czekamy na akcję użytkownika w nieskończoność (parametr 0)
    klawisz = cv2.waitKeyEx(0)
    
    # Zakończenie programu (klawisz 'q' lub 'Q')
    if klawisz in (ord('q'), ord('Q')):
        print("Zatrzymano przez użytkownika.")
        break
        
    # Następne zdjęcie: strzałka w prawo (kod Windows: 2555904) lub 'd' / 'D'
    elif klawisz in (2555904, ord('d'), ord('D')):
        if indeks < calkowita_liczba - 1:
            indeks += 1
        else:
            print("[INFO] To jest już ostatnie zdjęcie w folderze.")
            
    # Poprzednie zdjęcie: strzałka w lewo (kod Windows: 2424832) lub 'a' / 'A'
    elif klawisz in (2424832, ord('a'), ord('A')):
        if indeks > 0:
            indeks -= 1
        else:
            print("[INFO] To jest pierwsze zdjęcie w folderze.")
            
    # Kopiowanie zdjęcia: strzałka w górę (kod Windows: 2490368) lub 'w' / 'W'
    elif klawisz in (2490368, ord('w'), ord('W')):  # <--- DODANE
        docelowa_sciezka = os.path.join(folder_val, nazwa_pliku)
        try:
            shutil.copy(sciezka, docelowa_sciezka)
            print(f"[SUKCES] Skopiowano '{nazwa_pliku}' do folderu val_zdj")
        except Exception as e:
            print(f"[BŁĄD] Nie udało się skopiować '{nazwa_pliku}': {e}")

cv2.destroyAllWindows()
print("Koniec detekcji.")