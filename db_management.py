import psycopg2;
import logging;

DB_PARAMS = {
    "dbname": "Postgre_Trade_Scraper", 
    "user": "postgres",
    "password": "1221",
    "host": "localhost",
    "port": "5432"
}

def pobierz_ostatnie_20_id():
    """Zwraca listę 20 najnowszych ID z bazy danych jako punkty stopu."""
    try:
        with psycopg2.connect(**DB_PARAMS) as conn:
            with conn.cursor() as cur:
                # Sortujemy malejąco po dacie dodania i bierzemy 20
                cur.execute("SELECT vinted_id FROM punkty_stopu ORDER BY data_dodania DESC LIMIT 20;")
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"[BAZA] Błąd odczytu: {e}")
        return []

def zapisz_nowe_id(lista_nowych_id):
    """Zapisuje nowe ID do bazy i czyści stare rekordy (zostawia tylko 20)."""
    if not lista_nowych_id:
        return
        
    try:
        with psycopg2.connect(**DB_PARAMS) as conn:
            with conn.cursor() as cur:
                # 1. Wrzucamy nowe ID (ignorujemy, jeśli już takie jest w bazie)
                for v_id in lista_nowych_id:
                    cur.execute(
                        "INSERT INTO punkty_stopu (vinted_id) VALUES (%s) ON CONFLICT (vinted_id) DO NOTHING;", 
                        (v_id,)
                    )
                
                # 2. ODKURZACZ - Usuwamy wszystko z wyjątkiem 20 najnowszych
                cur.execute("""
                    DELETE FROM punkty_stopu 
                    WHERE id NOT IN (
                        SELECT id FROM punkty_stopu ORDER BY data_dodania DESC LIMIT 20
                    );
                """)
            conn.commit()
            logging.info(f"[BAZA] Zapisano {len(lista_nowych_id)} nowych ogłoszeń do bufora stopu.")
    except Exception as e:
        logging.error(f"[BAZA] Błąd zapisu: {e}")