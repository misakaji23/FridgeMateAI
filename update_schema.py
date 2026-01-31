import sqlite3
import os

# Define path to DB and schema
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "inventory.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

def update_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Applying schema to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
        conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    print("Database schema updated successfully.")

if __name__ == "__main__":
    update_db()
