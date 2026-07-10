import psycopg2;
import logging;

DB_PARAMS = {
    "dbname": "Postgre_Trade_Scraper", 
    "user": "postgres",
    "password": "1221",
    "host": "localhost",
    "port": "5432"
}

def pobierz_ostatnie_20_id_vinted():
    """Zwraca listę 20 najnowszych ID z bazy danych jako punkty stopu."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        with conn.cursor() as cur:
            # Dodano 'id DESC', by zapewnić idealną kolejność dla ogłoszeń z tą samą sekundą dodania
            cur.execute("SELECT vinted_id FROM punkty_stopu ORDER BY data_dodania DESC, id DESC LIMIT 20;")
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"[BAZA] Błąd odczytu: {e}")
        return []
    finally:
        # Ten blok zawsze się wykona, co zapobiega wyciekowi połączeń
        if conn is not None:
            conn.close()

def zapisz_nowe_id_vinted(lista_nowych_id):
    """Zapisuje nowe ID do bazy i czyści stare rekordy (zostawia tylko 20)."""
    if not lista_nowych_id:
        return
        
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
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
                    SELECT id FROM punkty_stopu ORDER BY data_dodania DESC, id DESC LIMIT 20
                );
            """)
        conn.commit()
        logging.info(f"[BAZA] Zapisano {len(lista_nowych_id)} nowych ogłoszeń do bufora stopu.")
    except Exception as e:
        logging.error(f"[BAZA] Błąd zapisu: {e}")
    finally:
        # Zamykamy fizyczne połączenie z bazą
        if conn is not None:
            conn.close()

def pobierz_ostatnie_50_id_olx(kategoria):
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT olx_id FROM olx_punkty_stopu 
                WHERE kategoria = %s 
                ORDER BY data_dodania DESC, id DESC LIMIT 50;
            """, (kategoria,))
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"[BAZA OLX] Błąd odczytu dla {kategoria}: {e}")
        return []
    finally:
        if conn is not None: conn.close()

def zapisz_nowe_id_olx(kategoria, lista_nowych_id):
    if not lista_nowych_id: return
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        with conn.cursor() as cur:
            for olx_id in lista_nowych_id:
                cur.execute(
                    "INSERT INTO olx_punkty_stopu (kategoria, olx_id) VALUES (%s, %s) ON CONFLICT (kategoria, olx_id) DO NOTHING;", 
                    (kategoria, olx_id)
                )
            
            cur.execute("""
                DELETE FROM olx_punkty_stopu 
                WHERE kategoria = %s AND id NOT IN (
                    SELECT id FROM olx_punkty_stopu 
                    WHERE kategoria = %s 
                    ORDER BY data_dodania DESC, id DESC LIMIT 50
                );
            """, (kategoria, kategoria))
        conn.commit()
    except Exception as e:
        logging.error(f"[BAZA OLX] Błąd zapisu dla {kategoria}: {e}")
    finally:
        if conn is not None: conn.close()