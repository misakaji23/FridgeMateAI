import requests
import sqlite3
import os

BASE_URL = "http://127.0.0.1:5000"

def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

def test_recipe_management():
    print("Testing Recipe Management Features...")
    
    # 1. Add a dummy recipe directly to DB to ensure we have something to edit/delete
    print("\n[Setup] Adding dummy recipe...")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO recipes (title, genre, created_at) VALUES (?, ?, datetime('now'))", ("Test Recipe", "Other"))
    recipe_id = cursor.lastrowid
    cursor.execute("INSERT INTO recipe_ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)", (recipe_id, "Test Ing", "100", "g"))
    cursor.execute("INSERT INTO recipe_steps (recipe_id, step_number, description) VALUES (?, ?, ?)", (recipe_id, 1, "Test Step"))
    conn.commit()
    conn.close()
    print(f"Added recipe with ID: {recipe_id}")

    try:
        # 2. Test Recipe List Access
        print(f"\n[Test] Accessing Recipe List ({BASE_URL}/recipe_list)...")
        response = requests.get(f"{BASE_URL}/recipe_list")
        if response.status_code == 200:
            print("SUCCESS: Recipe list page accessed.")
            if "Test Recipe" in response.text:
                 print("SUCCESS: Created recipe found in list.")
            else:
                 print("WARNING: Created recipe NOT found in list content.")
        else:
            print(f"FAILURE: Status code {response.status_code}")

        # 3. Test Edit Page Access
        print(f"\n[Test] Accessing Edit Page ({BASE_URL}/edit_recipe/{recipe_id})...")
        response = requests.get(f"{BASE_URL}/edit_recipe/{recipe_id}")
        if response.status_code == 200:
             print("SUCCESS: Edit page accessed.")
             if "Test Ing" in response.text:
                 print("SUCCESS: Ingredient found in edit page.")
        else:
             print(f"FAILURE: Status code {response.status_code}")

        # 4. Test Edit Submission (POST)
        print(f"\n[Test] Submitting Edit ({BASE_URL}/edit_recipe/{recipe_id})...")
        payload = {
            "title": "Updated Recipe Title",
            "genre": "主菜",
            "ingredients[0][name]": "Updated Ing",
            "ingredients[0][quantity]": "200",
            "ingredients[0][unit]": "kg",
            "steps[]": ["Updated Step 1", "New Step 2"]
        }
        response = requests.post(f"{BASE_URL}/edit_recipe/{recipe_id}", data=payload)
        if response.status_code == 200 or response.status_code == 302:
             print("SUCCESS: Edit submitted.")
             
             # Verify in DB
             conn = get_db_connection()
             updated_recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
             if updated_recipe and updated_recipe["title"] == "Updated Recipe Title":
                 print("SUCCESS: Database updated correctly.")
             else:
                 print("FAILURE: Database update failed.")
             conn.close()
        else:
             print(f"FAILURE: Status code {response.status_code}")

        # 5. Test Delete (POST)
        print(f"\n[Test] Deleting Recipe ({BASE_URL}/delete_recipe/{recipe_id})...")
        response = requests.post(f"{BASE_URL}/delete_recipe/{recipe_id}")
        if response.status_code == 200 or response.status_code == 302:
             print("SUCCESS: Delete request submitted.")
             
             # Verify in DB
             conn = get_db_connection()
             deleted_recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
             if not deleted_recipe:
                 print("SUCCESS: Recipe removed from database.")
             else:
                 print("FAILURE: Recipe still exists in database.")
             conn.close()
        else:
             print(f"FAILURE: Status code {response.status_code}")

    except Exception as e:
        print(f"ERROR: {e}")
        print("Ensure the Flask server is running locally on port 5000.")

if __name__ == "__main__":
    test_recipe_management()
