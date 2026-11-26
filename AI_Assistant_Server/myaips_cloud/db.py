# db.py

import os
import psycopg2

# Περιβάλλον (π.χ. από .env)
DB_HOST = os.getenv("POSTGRES_HOST", "db")        # πρόσεξε: στο docker compose έχεις "db"
DB_NAME = os.getenv("POSTGRES_DB", "myai")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")

def get_connection():
    """
    ΕΝΙΑΙΑ συνάρτηση σύνδεσης στη βάση.

    - Χωρίς RealDictCursor (επιστρέφει κλασικό cursor με tuples)
    - Έτσι ΟΛΟ το υπάρχον code που κάνει row[0] κτλ θα δουλεύει
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )
    return conn
