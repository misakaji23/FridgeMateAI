from flask import Flask, render_template, request, g, redirect, url_for
import webbrowser
from threading import Timer
from flask_sqlalchemy import SQLAlchemy
import sqlite3
from datetime import datetime, timedelta #賞味期限の計算
import os
import socket
from ml_recipe_recommender import MLRecipeRecommender

import sys
import qrcode
import io
import base64

# PyInstallerのリソースパス取得用関数
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# 定数定義
# 実行ファイルのディレクトリ（データベース保存用）
if getattr(sys, 'frozen', False):
    # exeとして実行されている場合
    EXE_DIR = os.path.dirname(sys.executable)
else:
    # 通常のPythonスクリプトとして実行されている場合
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

# 読み込み専用リソース（Excel, SQLなど）は resource_path を使用
# データベースは EXE_DIR に保存（永続化のため）
DATABASE = os.path.join(EXE_DIR, "inventory.db")
app = Flask(__name__)

# レシピ推薦システムの初期化
# データベース(inventory.db)を使用
try:
    recommender = MLRecipeRecommender(DATABASE)
    print("機械学習レシピ推薦システムを初期化しました")
except Exception as e:
    print(f"レシピデータの読み込みエラー: {e}")
    import traceback
    traceback.print_exc()
    recommender = None

#DB接続 SQLiteに接続し、行データを辞書形式で扱えるように設定
def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn
#DB接続の終了(データベースへの接続を常に適切に終了させる)
def close_db_connection(exception):
    db = g.pop("db_connection", None)
    if db is not None:
        db.close()

#DB初期化
def init_db():
    db = get_db_connection()
    db = get_db_connection()
    #スキーマファイルはリソースとしてバンドルされている
    schema_path = resource_path("schema.sql")
    with open(schema_path, mode='r', encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()

    db.commit()

def generate_qr_base64(data):
    """QRコードを生成してBase64文字列として返す"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

#在庫一覧　在庫を取得して表示
@app.route("/")
def index():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
# アラーム判定用　期限切れ、または３日以内のものをアラートに追加
    alerts = []
    from datetime import date, timedelta
    today = date.today()
    for item in items:
        if item["expiry_date"]:
            exp_date = date.fromisoformat(item["expiry_date"])
            if exp_date < today:
                alerts.append(f"{item['name']} は賞味期限切れです！（{exp_date}）")
            elif exp_date <= today + timedelta(days=3):
                alerts.append(f"{item['name']} の賞味期限が近いです！（{exp_date}）")
                alerts.append(f"{item['name']} の賞味期限が近いです！（{exp_date}）")
    
    # ローカルIPの取得とQRコード生成
    local_ip = get_local_ip()
    port = 5000
    access_url = f"http://{local_ip}:{port}"
    qr_code = generate_qr_base64(access_url)
    
    return render_template("index.html", items=items, alerts=alerts, qr_code=qr_code, access_url=access_url)

# 在庫削除　　DBのCRUD処理
@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    db = get_db_connection()
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    db.close()
    return redirect(url_for("index"))

# --- 商品追加 ---
@app.route("/add", methods=["POST"])
def add_item():
    name = request.form["name"]
    quantity = request.form["quantity"]
    category = request.form.get("category", "")
    expiry_date = request.form.get("expiry_date", None)
    db = get_db_connection()
    db.execute(
        "INSERT INTO items (name, quantity, category, expiry_date, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, quantity, category, expiry_date, datetime.now())
    )
    db.commit()
    return "追加しました！ <a href='/'>戻る</a>"

# 在庫を増やす（入庫）　ボタンにて実行
@app.route("/increase/<int:item_id>", methods=["POST"])
def increase(item_id):
    db = get_db_connection()
    db.execute("UPDATE items SET quantity = quantity + 1, updated_at=? WHERE id=?", (datetime.now(), item_id))
    db.commit()
    return "在庫を1増やしました！ <a href='/'>戻る</a>"

# 在庫を減らす（出庫）　ボタンにて実行
@app.route("/decrease/<int:item_id>", methods=["POST"])
def decrease(item_id):
    db = get_db_connection()
    db.execute("UPDATE items SET quantity = quantity - 1, updated_at=? WHERE id=?", (datetime.now(), item_id))
    db.commit()
    return "在庫を1減らしました！ <a href='/'>戻る</a>"

# レシピ推薦機能
@app.route("/recipes")
def recipes():
    try:
        if recommender is None:
            return "レシピデータの読み込みに失敗しました。", 500
        
        conn = get_db_connection()
        items = conn.execute("SELECT * FROM items WHERE quantity > 0").fetchall()
        conn.close()
        
        # 在庫アイテムを辞書のリストに変換
        inventory_items = [
            {
                'name': item['name'],
                'quantity': item['quantity'],
                'expiry_date': item['expiry_date']
            }
            for item in items
        ]
        
        if not inventory_items:
            return render_template("recipes.html", 
                                 main_dishes=[], 
                                 side_dishes=[], 
                                 other_dishes=[],
                                 message="在庫に食材がありません。")
        
        # 5日分の献立を提案（在庫消費シミュレーション付き）
        daily_menus = recommender.recommend_daily_menu(inventory_items, days=5)
        
        if not daily_menus:
            return render_template("recipes.html", 
                                 daily_menus=[],
                                 message="在庫の食材にマッチするレシピが見つかりませんでした。")
        
        return render_template("recipes.html", daily_menus=daily_menus)
    except Exception as e:
        import traceback
        error_msg = f"<h2>エラーが発生しました</h2><p>{str(e)}</p><pre>{traceback.format_exc()}</pre><a href='/'>在庫一覧に戻る</a>"
        return error_msg, 500

# レシピ登録機能
@app.route("/add_recipe", methods=["GET", "POST"])
def add_recipe():
    if request.method == "GET":
        return render_template("add_recipe.html")
    
    try:
        # フォームからデータを取得
        title = request.form.get("title")
        genre = request.form.get("genre")
        servings = request.form.get("servings")
        prep_time = request.form.get("prep_time")
        cook_time = request.form.get("cook_time")
        calorie = request.form.get("calorie")
        
        # 必須チェック
        if not title:
            return "レシピ名は必須です。", 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. recipesテーブルに挿入
        cursor.execute(
            "INSERT INTO recipes (title, genre, prep_time, cook_time, servings, calorie, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, genre, prep_time, cook_time, servings, calorie, datetime.now())
        )
        recipe_id = cursor.lastrowid
        
        # 2. recipe_ingredientsテーブルに挿入
        ingredients = []
        # request.formのキーを解析して材料データを構築
        # ingredients[0][name], ingredients[0][quantity] などの形式
        import re
        ingredient_keys = [k for k in request.form.keys() if k.startswith("ingredients[")]
        ingredient_indices = set()
        for k in ingredient_keys:
            match = re.search(r"ingredients\[(\d+)\]", k)
            if match:
                ingredient_indices.add(int(match.group(1)))
        
        for i in sorted(ingredient_indices):
            name = request.form.get(f"ingredients[{i}][name]")
            if name: # 名前がある場合のみ登録
                quantity = request.form.get(f"ingredients[{i}][quantity]")
                unit = request.form.get(f"ingredients[{i}][unit]")
                is_essential = 1 if request.form.get(f"ingredients[{i}][is_essential]") else 0
                
                cursor.execute(
                    "INSERT INTO recipe_ingredients (recipe_id, name, quantity, unit, is_essential) VALUES (?, ?, ?, ?, ?)",
                    (recipe_id, name, quantity, unit, is_essential)
                )

        # 3. recipe_stepsテーブルに挿入
        steps = request.form.getlist("steps[]")
        for index, description in enumerate(steps):
            if description.strip(): # 空の手順はスキップ
                cursor.execute(
                    "INSERT INTO recipe_steps (recipe_id, step_number, description) VALUES (?, ?, ?)",
                    (recipe_id, index + 1, description)
                )
        
        conn.commit()
        conn.close()
        
        return redirect(url_for("recipes")) # 登録後はレシピ一覧へ（またはトップへ）
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"エラーが発生しました: {e}", 500

# レシピ一覧表示
@app.route("/recipe_list")
def recipe_list():
    try:
        conn = get_db_connection()
        recipes = conn.execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
        conn.close()
        return render_template("recipe_list.html", recipes=recipes)
    except Exception as e:
        return f"エラーが発生しました: {e}", 500

# レシピ編集
@app.route("/edit_recipe/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    conn = get_db_connection()
    
    if request.method == "GET":
        recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if not recipe:
            conn.close()
            return "レシピが見つかりません", 404
            
        ingredients = conn.execute("SELECT * FROM recipe_ingredients WHERE recipe_id = ? ORDER BY id", (recipe_id,)).fetchall()
        steps = conn.execute("SELECT * FROM recipe_steps WHERE recipe_id = ? ORDER BY step_number", (recipe_id,)).fetchall()
        conn.close()
        
        return render_template("edit_recipe.html", recipe=recipe, ingredients=ingredients, steps=steps)
    
    # POST: 更新処理
    try:
        title = request.form.get("title")
        genre = request.form.get("genre")
        servings = request.form.get("servings")
        prep_time = request.form.get("prep_time")
        cook_time = request.form.get("cook_time")
        calorie = request.form.get("calorie")
        
        if not title:
            return "レシピ名は必須です。", 400

        cursor = conn.cursor()
        
        # 1. recipesテーブル更新
        cursor.execute(
            """UPDATE recipes SET title=?, genre=?, prep_time=?, cook_time=?, servings=?, calorie=? 
               WHERE id=?""",
            (title, genre, prep_time, cook_time, servings, calorie, recipe_id)
        )
        
        # 2. recipe_ingredients更新 (一度削除して再登録が簡単)
        cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        
        import re
        ingredient_keys = [k for k in request.form.keys() if k.startswith("ingredients[")]
        ingredient_indices = set()
        for k in ingredient_keys:
            match = re.search(r"ingredients\[(.*?)\].*", k) # Use non-greedy match and allow string indices (e.g. new_...)
            if match:
                # 複雑なキー構造に対応するため、インデックス部分を慎重に抽出
                # ingredients[key][field]
                parts = k.split('[')
                if len(parts) >= 2:
                    idx = parts[1].split(']')[0]
                    ingredient_indices.add(idx)
        
        for i in ingredient_indices:
            name = request.form.get(f"ingredients[{i}][name]")
            if name: 
                quantity = request.form.get(f"ingredients[{i}][quantity]")
                unit = request.form.get(f"ingredients[{i}][unit]")
                is_essential = 1 if request.form.get(f"ingredients[{i}][is_essential]") else 0
                
                cursor.execute(
                    "INSERT INTO recipe_ingredients (recipe_id, name, quantity, unit, is_essential) VALUES (?, ?, ?, ?, ?)",
                    (recipe_id, name, quantity, unit, is_essential)
                )

        # 3. recipe_steps更新 (一度削除して再登録)
        cursor.execute("DELETE FROM recipe_steps WHERE recipe_id = ?", (recipe_id,))
        
        steps = request.form.getlist("steps[]")
        for index, description in enumerate(steps):
            if description.strip(): 
                cursor.execute(
                    "INSERT INTO recipe_steps (recipe_id, step_number, description) VALUES (?, ?, ?)",
                    (recipe_id, index + 1, description)
                )
        
        conn.commit()
        conn.close()
        return redirect(url_for("recipe_list"))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"エラーが発生しました: {e}", 500

# レシピ削除
@app.route("/delete_recipe/<int:recipe_id>", methods=["POST"])
def delete_recipe(recipe_id):
    try:
        conn = get_db_connection()
        # カスケード削除が設定されていれば親だけで消えるが、念のため関連データも削除
        # (SQLiteのデフォルト設定に依存しないように明示的に削除)
        conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        conn.execute("DELETE FROM recipe_steps WHERE recipe_id = ?", (recipe_id,))
        conn.execute("DELETE FROM recipe_feedback WHERE recipe_id = ?", (recipe_id,))
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        
        conn.commit()
        conn.close()
        return redirect(url_for("recipe_list"))
    except Exception as e:
        return f"エラーが発生しました: {e}", 500

# レシピフィードバック保存
@app.route("/feedback", methods=["POST"])
def save_feedback():
    try:
        recipe_id = request.form.get("recipe_id")
        recipe_title = request.form.get("recipe_title")
        feedback_type = request.form.get("feedback_type")  # 'made' または 'rating'
        rating = request.form.get("rating")  # 1-5の星評価（feedback_typeが'rating'の場合）
        
        if not recipe_id or not recipe_title or not feedback_type:
            return "必要な情報が不足しています。", 400
        
        db = get_db_connection()
        if feedback_type == 'made':
            # 「作った」フィードバック
            db.execute(
                "INSERT INTO recipe_feedback (recipe_id, recipe_title, feedback_type, feedback_date) VALUES (?, ?, ?, ?)",
                (recipe_id, recipe_title, 'made', datetime.now())
            )
        elif feedback_type == 'rating' and rating:
            # 評価フィードバック
            rating_int = int(rating)
            if 1 <= rating_int <= 5:
                db.execute(
                    "INSERT INTO recipe_feedback (recipe_id, recipe_title, feedback_type, rating, feedback_date) VALUES (?, ?, ?, ?, ?)",
                    (recipe_id, recipe_title, 'rating', rating_int, datetime.now())
                )
            else:
                db.close()
                return "評価は1-5の範囲で入力してください。", 400
        else:
            db.close()
            return "無効なフィードバックタイプです。", 400
        
        db.commit()
        db.close()
        return redirect(url_for("recipes"))
    except Exception as e:
        import traceback
        error_msg = f"<h2>エラーが発生しました</h2><p>{str(e)}</p><pre>{traceback.format_exc()}</pre><a href='/recipes'>レシピ一覧に戻る</a>"
        return error_msg, 500

def get_local_ip():
    """ローカルネットワークのIPアドレスを取得"""
    try:
        # 外部サーバーに接続せずにローカルIPを取得（実際には接続しない）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 実際には接続しない、ローカルIPを取得するため
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            # フォールバック: ホスト名から取得
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return ip
        except Exception:
            return "127.0.0.1"

#ブラウザ自動起動
def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

#アプリ起動
if __name__ == "__main__":
    port = 5000
    local_ip = get_local_ip()
    
    print("=" * 60)
    print("Flaskアプリケーションを起動します...")
    print("=" * 60)
    print(f"\n📱 スマートフォンからアクセスする場合:")
    print(f"   同一Wi-Fiネットワークに接続後、以下のURLにアクセス:")
    print(f"   http://{local_ip}:{port}")
    
    # ターミナルにQRコードを表示
    qr = qrcode.QRCode(version=1, box_size=1, border=1)
    qr.add_data(f"http://{local_ip}:{port}")
    qr.make(fit=True)
    print("\n--- スマートフォン用QRコード ---")
    qr.print_ascii(invert=True)
    print("--------------------------------\n")
    
    print(f"\n💻 PCからアクセスする場合:")
    print(f"   http://127.0.0.1:{port} または http://localhost:{port}")
    print("=" * 60)
    print("\n利用可能なルート:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule}")
    print("\n" + "=" * 60)
    print("サーバーを停止するには Ctrl+C を押してください")
    print("=" * 60 + "\n")
    
    Timer(3, open_browser).start() #サーバー起動時に３秒後ブラウザを自動起動
    # host='0.0.0.0' で全てのネットワークインターフェースでリッスン（同一ネットワークからアクセス可能に）
    app.run(host='0.0.0.0', debug=True, use_reloader=False, port=port)