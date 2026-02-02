
import sqlite3
import pandas as pd
import os
import sys
import traceback
from ml_recipe_recommender import MLRecipeRecommender

DB_PATH = "inventory.db"

def check_db_schema():
    print("--- Database Schema Check ---")
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables found: {[t[0] for t in tables]}")
    
    for table_name in tables:
        t = table_name[0]
        print(f"\nTable: {t}")
        cursor.execute(f"PRAGMA table_info({t})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
            
        # Show first row data
        try:
            df = pd.read_sql(f"SELECT * FROM {t} LIMIT 1", conn)
            if not df.empty:
                print(f"  Sample data: {df.to_dict(orient='records')[0]}")
            else:
                print("  (Empty table)")
        except Exception as e:
            print(f"  Could not read data: {e}")

    conn.close()

def check_ml_recommender():
    print("\n--- ML Recommender Check ---")
    try:
        recommender = MLRecipeRecommender(DB_PATH)
        print("MLRecipeRecommender initialized successfully.")
        
        # Test recommendation with dummy inventory
        dummy_inventory = [
            {'name': 'Potato', 'quantity': 2, 'expiry_date': '2030-01-01'},
            {'name': 'Carrot', 'quantity': 1, 'expiry_date': '2030-01-01'}
        ]
        
        print("Running recommend_daily_menu with dummy inventory...")
        menu = recommender.recommend_daily_menu(dummy_inventory, days=1)
        print(f"Recommendation result: {menu}")
        
    except Exception as e:
        print(f"ERROR in ML Recommender: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_db_schema()
    check_ml_recommender()
