import hashlib
import os
from google.cloud import storage
import psycopg2
from natsort import natsorted, ns

DB_PARAMS = {
    "dbname": "Postgre_Trade_Scraper",  # Zmienione na nazwę Twojej bazy
    "user": "postgres",
    "password": "1221",
    "host": "localhost",
    "port": "5432"
}

def oblicz_sha256(sciezka_pliku):
    sha256_hash = hashlib.sha256()
    with open(sciezka_pliku, "rb") as f:
        for bajt_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(bajt_block)
    return sha256_hash.hexdigest()

def przetworz_nowe_zdjecie(sciezka_lokalna, bucket, photo_name):
    hash_pliku = oblicz_sha256(sciezka_lokalna)
    
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    # try:
    #     # 1. BRAMKARZ: Sprawdzamy duplikat po haszu
    #     cur.execute("SELECT id FROM zdjecia_karty_for_yolo WHERE hash_sha256 = %s", (hash_pliku,))
    #     if cur.fetchone():
    #         print("[POMINIĘTO] Zdjęcie to duplikat. Usuwam lokalnie.")
    #         os.remove(sciezka_lokalna)
    #         return False
            
        # 2. GENEROWANIE NAZWY: Prosimy bazę o bezpieczny, kolejny numer z sekwencji
    cur.execute("SELECT nextval(pg_get_serial_sequence('zdjecia_karty', 'id'))")
    nowe_id = cur.fetchone()[0]
    
    # Tworzymy nową ścieżkę dla chmury (np. 01_landing_zone/1.jpg)
    sciezka_w_chmurze = f"02_old_repository_for_yolo/{photo_name}"
    
    # 3. CHMURA: Wysyłamy plik pod nową, czystą nazwą
    blob = bucket.blob(sciezka_w_chmurze)
    blob.upload_from_filename(sciezka_lokalna)
    print(f"[CHMURA] Wgrano zdjęcie jako: {photo_name}  ")
    
    # 4. BAZA: Zapisujemy wszystko, używając wyciągniętego wcześniej ID
    cur.execute(
        """INSERT INTO zdjecia_karty_for_yolo (id, hash_sha256, sciezka_gcs) 
            VALUES (%s, %s, %s)""",
        (nowe_id, hash_pliku, sciezka_w_chmurze)
    )
    conn.commit()
    print("[BAZA] Pomyślnie zaindeksowano nowe zdjęcie.")
    return True
    cur.close()#do usuniecia
    conn.close()#do usuniecia
        
    # except Exception as e:
    #     conn.rollback()
    #     print(f"[BŁĄD] Potok danych napotkał problem: {e}")
    #     return False
    # finally:
    #     cur.close()
    #     conn.close()

if __name__ == "__main__":
    PROJECT_ID = "project-6ffdf12f-c10d-4003-8bf"
    BUCKET_NAME = "smart_trade_scraper"
    print("Łączenie z Google Cloud...")
    gcs_client = storage.Client(project=PROJECT_ID)
    gcs_bucket = gcs_client.bucket(BUCKET_NAME)
    for photo in natsorted(os.listdir(r"F:\WEBSCRAPER\wytrenowane_zdjecia"), alg=ns.PATH): #natsorted służy do czytania cyfr po kolei w ludzki sposób np. 1, 2, 3, 4....
        photo_lockal_path= f"F:/WEBSCRAPER/wytrenowane_zdjecia/{photo}"
        przetworz_nowe_zdjecie(photo_lockal_path, gcs_bucket, photo)