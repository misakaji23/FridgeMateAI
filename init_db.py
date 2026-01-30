import sqlite3
from datetime import datetime, timedelta

# データベースファイル名
DATABASE = "inventory.db"

def init_db():
    today = datetime.today().date()
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # 既存テーブル削除（やり直し用）
    c.execute("DROP TABLE IF EXISTS items")

    # テーブル作成
    c.execute("""
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        category TEXT,
        expiry_date TEXT,
        updated_at TEXT
    )
    """)
# 初期データ投入
    sample_data = [
        ("豚肉",2 , "肉", (today + timedelta(days=3)).isoformat(), datetime.now().isoformat()),
        ("キャベツ", 5, "野菜", (today + timedelta(days=14)).isoformat(), datetime.now().isoformat()),
        ("玉ねぎ" ,3, "野菜", (today + timedelta(days=30)).isoformat(), datetime.now().isoformat()),
        ("豆腐", 5, "加工食品", (today + timedelta(days=14)).isoformat(), datetime.now().isoformat())
    ]

    c.executemany(
        "INSERT INTO items (name, quantity, category, expiry_date, updated_at) VALUES (?, ?, ?, ?, ?)",
        sample_data
    )


    conn.commit()
    conn.close()
    print("✅ テーブル作成と初期データ挿入が完了しました！")

if __name__ == "__main__":
    init_db()