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

def safe_convert(value, default=None, to_type=None):
    """安全に値を変換する（NaNやNoneを処理）"""
    if pd.isna(value) or value is None:
        return default
    if to_type == int:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    if to_type == str:
        return str(value) if value else default
    return value

def migrate():
    print("=" * 60)
    print("Excelファイルからデータベースへの移行を開始します...")
    print("=" * 60)
    
    # Check if Excel files exist
    if not os.path.exists(RECIPE_DB_PATH):
        print(f"[ERROR] {RECIPE_DB_PATH} が見つかりません。")
        return False
    if not os.path.exists(INGREDIENTS_PATH):
        print(f"[ERROR] {INGREDIENTS_PATH} が見つかりません。")
        return False
    if not os.path.exists(STEPS_PATH):
        print(f"[ERROR] {STEPS_PATH} が見つかりません。")
        return False

    print("[OK] Excelファイルが見つかりました。")
    print(f"   - {RECIPE_DB_PATH}")
    print(f"   - {INGREDIENTS_PATH}")
    print(f"   - {STEPS_PATH}")

    # Connect to DB
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # テーブルが存在しない場合は作成
    schema_path = os.path.join(BASE_DIR, "schema.sql")
    if os.path.exists(schema_path):
        print("[INFO] データベーススキーマを確認しています...")
        with open(schema_path, mode='r', encoding='utf-8') as f:
            schema_sql = f.read()
            cursor.executescript(schema_sql)
        conn.commit()
        print("[OK] データベーススキーマを確認しました。")

    try:
        # Load Excel files
        print("\n[INFO] Excelファイルを読み込んでいます...")
        recipes_df = pd.read_excel(RECIPE_DB_PATH, sheet_name='レシピdb')
        ingredients_df = pd.read_excel(INGREDIENTS_PATH, sheet_name='分量・材料')
        steps_df = pd.read_excel(STEPS_PATH, sheet_name='調理手順')
        
        print(f"   - レシピ: {len(recipes_df)}件")
        print(f"   - 材料: {len(ingredients_df)}件")
        print(f"   - 手順: {len(steps_df)}件")

        # Clean IDs - 数値でないRecipe_IDを除外
        recipes_df = recipes_df[pd.to_numeric(recipes_df['Recipe_ID'], errors='coerce').notnull()]
        recipes_df['Recipe_ID'] = recipes_df['Recipe_ID'].astype(int)
        print(f"\n[OK] 有効なレシピID: {len(recipes_df)}件")
        
        # 既存のレシピをチェック（重複を避けるため）
        cursor.execute("SELECT title FROM recipes")
        existing_titles = {row[0].lower() for row in cursor.fetchall()}
        
        migrated_count = 0
        skipped_count = 0
        id_map = {} # Old -> New

        print("\n[INFO] レシピを移行しています...")
        for idx, row in recipes_df.iterrows():
            old_id = int(row['Recipe_ID'])
            title = safe_convert(row.get('Title'), '', str)
            
            if not title:
                print(f"   [WARN] Recipe_ID {old_id}: タイトルが空のためスキップ")
                skipped_count += 1
                continue
            
            # 重複チェック（タイトルが既に存在する場合はスキップ）
            if title.lower() in existing_titles:
                print(f"   [WARN] 「{title}」は既に登録されているためスキップ")
                skipped_count += 1
                continue
            
            genre = safe_convert(row.get('Genre'), None, str)
            prep_time = safe_convert(row.get('Prep_Time_Min'), None, int)
            cook_time = safe_convert(row.get('Cook_Time_Min'), None, int)
            servings = safe_convert(row.get('Servings'), None, int)
            calorie = safe_convert(row.get('Calorie'), None, int)
            
            cursor.execute(
                "INSERT INTO recipes (title, genre, prep_time, cook_time, servings, calorie, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, genre, prep_time, cook_time, servings, calorie, datetime.now())
            )
            new_id = cursor.lastrowid
            id_map[old_id] = new_id
            migrated_count += 1
            existing_titles.add(title.lower())  # 追加したタイトルを記録
            
            if migrated_count % 10 == 0:
                print(f"   ... {migrated_count}件移行完了")

        print(f"\n[OK] レシピ移行完了: {migrated_count}件（スキップ: {skipped_count}件）")

        print("\n[INFO] 材料を移行しています...")
        ing_count = 0
        ing_skipped = 0
        for idx, row in ingredients_df.iterrows():
            old_id = safe_convert(row.get('Recipe_ID'), None, int)
            # Only migrate if we have a parent recipe
            if old_id is None or old_id not in id_map: 
                ing_skipped += 1
                continue
            
            new_rec_id = id_map[old_id]
            name = safe_convert(row.get('Ingredient_Name_Normalized'), '', str)
            if not name:
                continue  # 材料名が空の場合はスキップ
            
            quantity = safe_convert(row.get('Quantity_Amount'), '', str)
            unit = safe_convert(row.get('Quantity_Unit'), '', str)
            is_essential = 1 if safe_convert(row.get('Is_Essential'), False) else 0

            cursor.execute(
                "INSERT INTO recipe_ingredients (recipe_id, name, quantity, unit, is_essential) VALUES (?, ?, ?, ?, ?)",
                (new_rec_id, name, quantity, unit, is_essential)
            )
            ing_count += 1
            
            if ing_count % 50 == 0:
                print(f"   ... {ing_count}件移行完了")
            
        print(f"[OK] 材料移行完了: {ing_count}件（スキップ: {ing_skipped}件）")

        print("\n[INFO] 調理手順を移行しています...")
        step_count = 0
        step_skipped = 0
        for idx, row in steps_df.iterrows():
            old_id = safe_convert(row.get('Recipe_ID'), None, int)
            if old_id is None or old_id not in id_map:
                step_skipped += 1
                continue
                
            new_rec_id = id_map[old_id]
            step_num = safe_convert(row.get('Step_Number'), None, int)
            if step_num is None:
                step_skipped += 1
                continue
                
            desc = safe_convert(row.get('Step_Description'), '', str)
            if not desc:
                step_skipped += 1
                continue

            cursor.execute(
                "INSERT INTO recipe_steps (recipe_id, step_number, description) VALUES (?, ?, ?)",
                (new_rec_id, step_num, desc)
            )
            step_count += 1
            
            if step_count % 50 == 0:
                print(f"   ... {step_count}件移行完了")
            
        print(f"[OK] 調理手順移行完了: {step_count}件（スキップ: {step_skipped}件）")

        conn.commit()
        print("\n" + "=" * 60)
        print("[OK] 移行が正常に完了しました！")
        print("=" * 60)
        print(f"\n[RESULT] 移行結果:")
        print(f"   - レシピ: {migrated_count}件")
        print(f"   - 材料: {ing_count}件")
        print(f"   - 調理手順: {step_count}件")
        print("\nデータベースを確認してください。")
        return True

    except FileNotFoundError as e:
        conn.rollback()
        print(f"\n[ERROR] Excelファイルが見つかりません: {e}")
        return False
    except KeyError as e:
        conn.rollback()
        print(f"\n[ERROR] Excelファイルの列が見つかりません: {e}")
        print("   必要な列: Recipe_ID, Title, Genre, Prep_Time_Min, Cook_Time_Min, Servings, Calorie")
        print("   または: Ingredient_Name_Normalized, Quantity_Amount, Quantity_Unit, Is_Essential")
        print("   または: Step_Number, Step_Description")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
