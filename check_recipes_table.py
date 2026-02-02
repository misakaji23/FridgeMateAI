import sqlite3

try:
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check recipes schema if exists
    if ('recipes',) in tables:
        cursor.execute("PRAGMA table_info(recipes)")
        columns = cursor.fetchall()
        print("\nRecipes Columns:")
        for col in columns:
            print(col)
            
        # Check count
        cursor.execute("SELECT COUNT(*) FROM recipes")
        count = cursor.fetchone()[0]
        print(f"\nRecipe count: {count}")
        
    else:
        print("\nRecipes table NOT FOUND")
        
    conn.close()
except Exception as e:
    print(e)
