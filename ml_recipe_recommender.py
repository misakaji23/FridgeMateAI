import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class MLRecipeRecommender:
    """機械学習ベースのレシピ推薦システム - 特徴量から学習されたモデルを使用"""
    
    def __init__(self, recipe_db_path: str, ingredients_path: str, steps_path: str):
        """
        レシピデータを読み込んで機械学習モデルを構築
        
        Args:
            recipe_db_path: レシピdb.xlsxのパス
            ingredients_path: 分量・材料.xlsxのパス
            steps_path: 調理手順.xlsxのパス
        """
        self.recipe_db_path = recipe_db_path
        self.ingredients_path = ingredients_path
        self.steps_path = steps_path
        
        # Excelファイルを読み込む
        self.recipes_df = pd.read_excel(recipe_db_path, sheet_name='レシピdb')
        self.ingredients_df = pd.read_excel(ingredients_path, sheet_name='分量・材料')
        self.steps_df = pd.read_excel(steps_path, sheet_name='調理手順')
        
        # データの前処理
        self._preprocess_data()
        
        # 特徴量エンジニアリング
        self._build_feature_vectors()
    
    def _preprocess_data(self):
        """データの前処理"""
        # Recipe_IDを文字列に統一（ヘッダー行を除外）
        self.ingredients_df = self.ingredients_df[
            self.ingredients_df['Recipe_ID'].astype(str).str.isdigit()
        ].copy()
        self.steps_df = self.steps_df[
            self.steps_df['Recipe_ID'].astype(str).str.isdigit()
        ].copy()
        self.recipes_df = self.recipes_df[
            self.recipes_df['Recipe_ID'].astype(str).str.isdigit()
        ].copy()
        
        # Recipe_IDを数値型に変換
        self.ingredients_df['Recipe_ID'] = pd.to_numeric(self.ingredients_df['Recipe_ID'], errors='coerce')
        self.steps_df['Recipe_ID'] = pd.to_numeric(self.steps_df['Recipe_ID'], errors='coerce')
        self.recipes_df['Recipe_ID'] = pd.to_numeric(self.recipes_df['Recipe_ID'], errors='coerce')
        
        # NaN行を削除
        self.ingredients_df = self.ingredients_df.dropna(subset=['Recipe_ID'])
        self.steps_df = self.steps_df.dropna(subset=['Recipe_ID'])
        self.recipes_df = self.recipes_df.dropna(subset=['Recipe_ID'])
        
        # 材料名の正規化
        if 'Ingredient_Name_Normalized' in self.ingredients_df.columns:
            self.ingredients_df['Ingredient_Normalized'] = (
                self.ingredients_df['Ingredient_Name_Normalized']
                .astype(str)
                .str.strip()
                .str.lower()
            )
    
    def _build_feature_vectors(self):
        """レシピの特徴量ベクトルを構築"""
        # 各レシピの材料リストを作成（TF-IDF用）
        recipe_ingredients = {}
        for recipe_id in self.recipes_df['Recipe_ID'].unique():
            ingredients = self.ingredients_df[
                self.ingredients_df['Recipe_ID'] == recipe_id
            ]['Ingredient_Name_Normalized'].astype(str).tolist()
            recipe_ingredients[recipe_id] = ' '.join(ingredients)
        
        # TF-IDFベクトル化（材料ベースの特徴量）
        ingredient_texts = [recipe_ingredients.get(rid, '') for rid in self.recipes_df['Recipe_ID'].unique()]
        self.tfidf_vectorizer = TfidfVectorizer(max_features=100, stop_words=None)
        self.ingredient_features = self.tfidf_vectorizer.fit_transform(ingredient_texts)
        
        # レシピIDとインデックスのマッピング
        self.recipe_id_to_index = {
            rid: idx for idx, rid in enumerate(self.recipes_df['Recipe_ID'].unique())
        }
        self.index_to_recipe_id = {v: k for k, v in self.recipe_id_to_index.items()}
    
    def extract_inventory_features(self, inventory_items: List[Dict]) -> Dict:
        """
        在庫アイテムから特徴量を抽出
        
        Returns:
            期限スコア、数量スコア、食材リストなどの特徴量辞書
        """
        today = date.today()
        ingredient_scores = {}
        ingredient_list = []
        total_quantity = 0
        expiring_count = 0
        
        for item in inventory_items:
            name = str(item.get('name', '')).strip().lower()
            quantity = item.get('quantity', 0)
            expiry_date_str = item.get('expiry_date')
            
            if not name or quantity <= 0 or not expiry_date_str:
                continue
            
            try:
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                days_until_expiry = (expiry_date - today).days
                
                # 期限に基づくスコア
                if days_until_expiry < 0:
                    score = 200.0
                    expiring_count += 1
                elif days_until_expiry <= 1:
                    score = 150.0
                    expiring_count += 1
                elif days_until_expiry <= 3:
                    score = 120.0
                    expiring_count += 1
                elif days_until_expiry <= 7:
                    score = 80.0
                else:
                    score = 30.0
                
                score *= (1 + min(quantity / 10, 1))
                
                if name in ingredient_scores:
                    ingredient_scores[name] = max(ingredient_scores[name], score)
                else:
                    ingredient_scores[name] = score
                
                ingredient_list.append(name)
                total_quantity += quantity
                    
            except (ValueError, TypeError):
                continue
        
        return {
            'ingredient_scores': ingredient_scores,
            'ingredient_list': ingredient_list,
            'total_quantity': total_quantity,
            'expiring_count': expiring_count,
            'ingredient_text': ' '.join(ingredient_list)
        }
    
    def normalize_ingredient_name(self, name: str) -> str:
        """食材名を正規化"""
        if pd.isna(name):
            return ""
        return str(name).strip().lower()
    
    def calculate_recipe_score_with_ml(self, recipe_id: int, inventory_features: Dict) -> Tuple[float, Dict]:
        """
        機械学習ベースのスコア計算
        
        Args:
            recipe_id: レシピID
            inventory_features: 在庫の特徴量
        
        Returns:
            (総合スコア, 詳細情報)
        """
        recipe_ingredients = self.ingredients_df[
            self.ingredients_df['Recipe_ID'] == recipe_id
        ]
        
        if recipe_ingredients.empty:
            return 0.0, {}
        
        # 特徴量1: 食材のTF-IDF類似度
        recipe_text = ' '.join(recipe_ingredients['Ingredient_Name_Normalized'].astype(str).tolist())
        inventory_text = inventory_features['ingredient_text']
        
        if recipe_id in self.recipe_id_to_index:
            recipe_idx = self.recipe_id_to_index[recipe_id]
            recipe_tfidf = self.ingredient_features[recipe_idx]
            
            # 在庫食材のTF-IDFベクトル
            inventory_tfidf = self.tfidf_vectorizer.transform([inventory_text])
            
            # コサイン類似度
            similarity = cosine_similarity(recipe_tfidf, inventory_tfidf)[0][0]
        else:
            similarity = 0.0
        
        # 特徴量2: 期限が近い食材のマッチングスコア
        ingredient_scores = inventory_features['ingredient_scores']
        matched_essential = []
        matched_optional = []
        expiry_score = 0.0
        
        if 'Is_Essential' in recipe_ingredients.columns:
            essential_ingredients = recipe_ingredients[
                recipe_ingredients['Is_Essential'] == True
            ]
            optional_ingredients = recipe_ingredients[
                recipe_ingredients['Is_Essential'] == False
            ]
        else:
            essential_ingredients = recipe_ingredients
            optional_ingredients = pd.DataFrame()
        
        # 必須食材のチェック
        for _, row in essential_ingredients.iterrows():
            ingredient_name = self.normalize_ingredient_name(
                row.get('Ingredient_Name_Normalized', '')
            )
            
            matched = False
            matched_score = 0.0
            best_match = None
            
            for inv_name, inv_score in ingredient_scores.items():
                if ingredient_name == inv_name:
                    matched = True
                    matched_score = inv_score
                    best_match = inv_name
                    break
                elif ingredient_name in inv_name or inv_name in ingredient_name:
                    if not matched or inv_score > matched_score:
                        matched = True
                        matched_score = inv_score
                        best_match = inv_name
            
            if matched and best_match:
                matched_essential.append({
                    'name': ingredient_name,
                    'inventory_name': best_match,
                    'score': matched_score
                })
                expiry_score += matched_score * 2.0
            else:
                expiry_score -= 50.0
        
        # オプション食材のチェック
        for _, row in optional_ingredients.iterrows():
            ingredient_name = self.normalize_ingredient_name(
                row.get('Ingredient_Name_Normalized', '')
            )
            
            for inv_name, inv_score in ingredient_scores.items():
                if ingredient_name == inv_name or ingredient_name in inv_name or inv_name in ingredient_name:
                    matched_optional.append({
                        'name': ingredient_name,
                        'inventory_name': inv_name,
                        'score': inv_score
                    })
                    expiry_score += inv_score * 0.5
                    break
        
        # 特徴量3: 必須食材のマッチ率(充足率計算)
        essential_match_rate = len(matched_essential) / max(len(essential_ingredients), 1)
        
        # 総合スコア計算（特徴量の重み付け）
        # TF-IDF類似度: 40%、期限スコア: 50%、マッチ率: 10%
        final_score = (
            similarity * 100 * 0.4 +  # TF-IDF類似度を0-100スケールに変換
            expiry_score * 0.5 +
            essential_match_rate * 100 * 0.1
        )
        
        # マッチ率で最終調整
        final_score *= essential_match_rate
        
        return final_score, {
            'similarity': similarity,
            'expiry_score': expiry_score,
            'match_rate': essential_match_rate,
            'essential_match_rate': essential_match_rate,  # テンプレート互換性のため
            'matched_essential': matched_essential,
            'matched_optional': matched_optional,
            'total_ingredients': len(recipe_ingredients),
            'matched_count': len(matched_essential) + len(matched_optional)
        }
    
    def recommend_recipes(self, inventory_items: List[Dict], top_n: int = 5) -> List[Dict]:
        """
        機械学習ベースのレシピ推薦
        
        Args:
            inventory_items: 在庫アイテムのリスト
            top_n: 返すレシピの数
        
        Returns:
            推薦レシピのリスト（スコア順）
        """
        # 在庫から特徴量を抽出
        inventory_features = self.extract_inventory_features(inventory_items)
        
        if not inventory_features['ingredient_scores']:
            return []
        
        # 各レシピのスコアを計算
        recipe_scores = []
        
        for recipe_id in self.recipes_df['Recipe_ID'].unique():
            score, details = self.calculate_recipe_score_with_ml(recipe_id, inventory_features)
            
            if score > 0:
                recipe_info = self.recipes_df[
                    self.recipes_df['Recipe_ID'] == recipe_id
                ].iloc[0].to_dict()
                
                # 調理手順を取得
                steps = self.steps_df[
                    self.steps_df['Recipe_ID'] == recipe_id
                ].sort_values('Step_Number')
                
                # 材料を取得
                ingredients = self.ingredients_df[
                    self.ingredients_df['Recipe_ID'] == recipe_id
                ]
                
                recipe_scores.append({
                    'recipe_id': int(recipe_id),
                    'title': recipe_info.get('Title', ''),
                    'genre': recipe_info.get('Genre', ''),
                    'prep_time': recipe_info.get('Prep_Time_Min', ''),
                    'cook_time': recipe_info.get('Cook_Time_Min', ''),
                    'total_time': recipe_info.get('Total_Time_Min', ''),
                    'servings': recipe_info.get('Servings', ''),
                    'calorie': recipe_info.get('Calorie', ''),
                    'method': recipe_info.get('Method_Main', ''),
                    'score': score,
                    'match_details': details,
                    'steps': [
                        {
                            'step_number': int(row['Step_Number']),
                            'description': str(row['Step_Description'])
                        }
                        for _, row in steps.iterrows()
                    ],
                    'ingredients': [
                        {
                            'name': row.get('Ingredient_Name_Normalized', ''),
                            'quantity': '' if pd.isna(row.get('Quantity_Amount', '')) else str(row.get('Quantity_Amount', '')),
                            'unit': '' if pd.isna(row.get('Quantity_Unit', '')) else str(row.get('Quantity_Unit', '')),
                            'is_essential': row.get('Is_Essential', False)
                        }
                        for _, row in ingredients.iterrows()
                    ]
                })
        
        # スコアでソート（降順）
        recipe_scores.sort(key=lambda x: x['score'], reverse=True)
        
        return recipe_scores[:top_n]

    def recommend_daily_menu(self, inventory_items: List[Dict], days: int = 5) -> List[Dict]:
        """
        5日分の献立を提案する。
        各日の料理で使用した食材を在庫から減算し、翌日の提案に反映させる。
        
        Args:
            inventory_items: 初期の在庫アイテムリスト
            days: 提案する日数
            
        Returns:
            各日の献立リスト（日ごとの辞書リスト）
        """
        import copy
        
        # 在庫のシミュレーション用コピーを作成
        current_inventory = copy.deepcopy(inventory_items)
        daily_menus = []
        used_recipe_ids = set()
        
        for day in range(1, days + 1):
            # 現在の在庫でレシピを推薦
            # 候補を多めに取得して、選ばれていないものを探す
            recommendations = self.recommend_recipes(current_inventory, top_n=50)
            
            # 既に選ばれたレシピを除外
            candidates = [r for r in recommendations if r['recipe_id'] not in used_recipe_ids]
            
            day_menu = {
                'day': day,
                'main_dish': None,
                'side_dish': None
            }
            
            # 主菜と副菜を選ぶ
            # 注: recommend_recipesの結果には 'genre' が含まれている前提
            # ExcelのGenre値: '主菜', '副菜' など
            
            # 主菜の選定
            for r in candidates:
                genre = str(r.get('genre', '')).strip()
                if (genre.startswith('主') or genre == 'Main') and r['recipe_id'] not in used_recipe_ids:
                    day_menu['main_dish'] = r
                    used_recipe_ids.add(r['recipe_id'])
                    break
            
            # 副菜の選定
            for r in candidates:
                genre = str(r.get('genre', '')).strip()
                if (genre.startswith('副') or genre == 'Side') and r['recipe_id'] not in used_recipe_ids:
                    day_menu['side_dish'] = r
                    used_recipe_ids.add(r['recipe_id'])
                    break
            
            # メニューが決まらなかった場合のフォールバック（ジャンル不問でスコア高いもの）
            if not day_menu['main_dish'] and candidates:
                 for r in candidates:
                    if r['recipe_id'] not in used_recipe_ids:
                        day_menu['main_dish'] = r
                        used_recipe_ids.add(r['recipe_id'])
                        break
                        
            # それでも決まらなければこの日はスキップ（ありえないはずだが）
            if not day_menu['main_dish']:
                continue
                
            daily_menus.append(day_menu)
            
            # 食材の消費シミュレーション
            dishes_to_cook = []
            if day_menu['main_dish']: dishes_to_cook.append(day_menu['main_dish'])
            if day_menu['side_dish']: dishes_to_cook.append(day_menu['side_dish'])
            
            for dish in dishes_to_cook:
                # レシピに必要な食材を取得（recommend_recipesの戻り値に含まれている）
                ingredients = dish.get('ingredients', [])
                
                for ing in ingredients:
                    ing_name = self.normalize_ingredient_name(ing['name'])
                    
                    # 在庫から該当する食材を探して減らす
                    # 簡易的に、名前がマッチする在庫を1つ減らす
                    for item in current_inventory:
                        inv_name = self.normalize_ingredient_name(item['name'])
                        if ing_name == inv_name or ing_name in inv_name or inv_name in ing_name:
                            # 数量を減らす（単位変換は難しいため、1単位減らすとする）
                            # もし数量が数値でなければ無視
                            try:
                                qty = float(item['quantity'])
                                if qty > 0:
                                    item['quantity'] = qty - 1
                            except (ValueError, TypeError):
                                pass
                            break
            
            # 数量が0以下になった在庫は、次の日の推薦計算では使われないようにする
            # (extract_inventory_features で quantity <= 0 はスキップされるため、リストから削除しなくてもOKだが、
            #  念のため削除しておくと計算が速い)
            current_inventory = [item for item in current_inventory if item.get('quantity', 0) > 0]
            
        return daily_menus

