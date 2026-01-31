import pandas as pd
import sqlite3
import os
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPE_DB_PATH = os.path.join(BASE_DIR, "レシピdb.xlsx")
INGREDIENTS_PATH = os.path.join(BASE_DIR, "分量・材料.xlsx")
STEPS_PATH = os.path.join(BASE_DIR, "調理手順.xlsx")
DATABASE_PATH = os.path.join(BASE_DIR, "inventory.db")

def migrate():
    print("Migration started...")
    
    # Check if Excel files exist
    if not (os.path.exists(RECIPE_DB_PATH) and os.path.exists(INGREDIENTS_PATH) and os.path.exists(STEPS_PATH)):
        print("Excel files not found. Please ensure they are in the same directory.")
        return

    # Connect to DB
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Load Excel files
        print("Loading Excel files...")
        recipes_df = pd.read_excel(RECIPE_DB_PATH, sheet_name='レシピdb')
        ingredients_df = pd.read_excel(INGREDIENTS_PATH, sheet_name='分量・材料')
        steps_df = pd.read_excel(STEPS_PATH, sheet_name='調理手順')

        # Clean IDs
        recipes_df = recipes_df[pd.to_numeric(recipes_df['Recipe_ID'], errors='coerce').notnull()]
        
        migrated_count = 0
        
        # Determine starting ID for recipes to avoid conflicts if needed, 
        # but we'll let AUTOINCREMENT handle it and map old IDs to new IDs
        # Actually, for consistency with ML model training data (if it relied on IDs), 
        # we might want to preserve IDs IF possible, but 'id' in DB is AUTOINCREMENT.
        # However, the ML model in this app seems to rebuild features from data every time (__init__),
        # so ID continuity might not be strictly required as long as relationships are preserved.
        # We will create a mapping from Old_Recipe_ID -> New_Recipe_ID.
        
        id_map = {} # Old -> New

        print("Migrating recipes...")
        for _, row in recipes_df.iterrows():
            old_id = row['Recipe_ID']
            title = row['Title']
            genre = row.get('Genre')
            prep_time = row.get('Prep_Time_Min')
            cook_time = row.get('Cook_Time_Min')
            servings = row.get('Servings')
            calorie = row.get('Calorie')
            
            # Simple check if this recipe might already be in DB (by title) to avoid duplicates on re-run
            # But user said "Yes" to migration, assuming they want to import.
            # We'll insert.
            
            cursor.execute(
                "INSERT INTO recipes (title, genre, prep_time, cook_time, servings, calorie, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, genre, prep_time, cook_time, servings, calorie, datetime.now())
            )
            new_id = cursor.lastrowid
            id_map[old_id] = new_id
            migrated_count += 1

        print(f"Migrated {migrated_count} recipes.")

        print("Migrating ingredients...")
        ing_count = 0
        for _, row in ingredients_df.iterrows():
            old_id = row['Recipe_ID']
            # Only migrate if we have a parent recipe
            if old_id not in id_map: 
                continue
            
            new_rec_id = id_map[old_id]
            name = row.get('Ingredient_Name_Normalized', '')
            if pd.isna(name): name = ""
            quantity = row.get('Quantity_Amount', '')
            if pd.isna(quantity): quantity = ""
            unit = row.get('Quantity_Unit', '')
            if pd.isna(unit): unit = ""
            is_essential = 1 if row.get('Is_Essential') else 0

            cursor.execute(
                "INSERT INTO recipe_ingredients (recipe_id, name, quantity, unit, is_essential) VALUES (?, ?, ?, ?, ?)",
                (new_rec_id, name, str(quantity), str(unit), is_essential)
            )
            ing_count += 1
            
        print(f"Migrated {ing_count} ingredients.")

        print("Migrating steps...")
        step_count = 0
        for _, row in steps_df.iterrows():
            old_id = row['Recipe_ID']
            if old_id not in id_map:
                continue
                
            new_rec_id = id_map[old_id]
            step_num = row.get('Step_Number')
            desc = row.get('Step_Description', '')
            if pd.isna(desc): desc = ""

            cursor.execute(
                "INSERT INTO recipe_steps (recipe_id, step_number, description) VALUES (?, ?, ?)",
                (new_rec_id, step_num, desc)
            )
            step_count += 1
            
        print(f"Migrated {step_count} steps.")

        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
