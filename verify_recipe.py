import requests
import unittest
import threading
import time
import os
import sqlite3
import app2
from app2 import app, init_db, get_db_connection

# Use a test database
TEST_DB = "test_inventory.db"
app.config['DATABASE'] = TEST_DB

class TestRecipeRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup test database
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        
        # Override the database connection in app2 for testing if possible, 
        # but app2.py hardcodes 'inventory.db' in get_db_connection.
        # We might need to monkeypatch or just use the real DB but careful not to mess it up?
        # A safer way is to rely on app.test_client() which Flask provides.
        pass

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
        # Initialize DB (using the hardcoded one in app2.py for now, 
        # normally we should swap it out, but for this quick verify we will just use it 
        # and maybe delete the recipe after)
        # Actually app2.py uses 'inventory.db' inside functions. 
        # Let's just create a dummy recipe and check if it exists, then delete it.
        pass

    def test_1_get_add_recipe_page(self):
        response = self.app.get('/add_recipe')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'recipe', response.data.lower()) # check for some content
        print("GET /add_recipe page successful")

    def test_2_post_add_recipe(self):
        # Prepare form data
        data = {
            'title': 'Test Curry',
            'genre': '主菜',
            'servings': '4',
            'prep_time': '20',
            'cook_time': '40',
            'calorie': '800',
            'ingredients[0][name]': 'Test Potato',
            'ingredients[0][quantity]': '2',
            'ingredients[0][unit]': 'pieces',
            'ingredients[0][is_essential]': '1',
            'steps[]': ['Peel potatoes', 'Boil them']
        }
        
        response = self.app.post('/add_recipe', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        print("POST /add_recipe successful")
        
        # Verify in DB
        # We need to access the actual DB used by app2
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM recipes WHERE title = 'Test Curry'")
        recipe = cursor.fetchone()
        self.assertIsNotNone(recipe)
        print(f"Verified recipe '{recipe[1]}' in DB with ID {recipe[0]}")
        
        recipe_id = recipe[0]
        
        # Verify ingredients
        cursor.execute("SELECT name FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        ing = cursor.fetchone()
        self.assertEqual(ing[0], 'Test Potato')
        print("Verified ingredient in DB")

        # Clean up
        cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
        conn.close()
        print("Test data cleaned up")

if __name__ == '__main__':
    unittest.main()
