import re
import unicodedata

def extract_score_from_text(ocr_text: str) -> float:
    """OCR結果のテキストからカラオケの最終スコア値を抽出し、floatで返す。見つからない場合はNoneを返す。"""
    # 1. 前処理: テキスト正規化と不要文字除去
    text = unicodedata.normalize('NFKC', ocr_text)    # 全角数字・記号を半角に正規化&#8203;:contentReference[oaicite:5]{index=5}
    text = text.replace(',', '')                     # コンマを除去（桁区切り無視）
    # 小数点の前後や数字間の不要な空白を除去/結合
    text = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', text)         # 数字と数字の間のピリオド周辺の空白除去
    text = re.sub(r'(\d{1,3})\s+(\d{3})\s*点', r'\1.\2点', text)  # 「AAA BBB 点」のパターンを「AAA.BBB点」に修正

    # 2. スコア候補の抽出: 正規表現で数字パターンを検索
    # 小数点付き候補
    decimal_candidates = re.findall(r'\d{1,3}\.\d{3}', text)
    # 小数点なし候補（1～3桁の整数）
    int_candidates = re.findall(r'\b\d{1,3}\b', text)
    # 抽出候補をマージ（小数点付き優先）
    candidates = []
    for dc in decimal_candidates:
        candidates.append(dc)
    for num in int_candidates:
        # もし既存の小数候補の一部（例えば「91.446」の「91」）ならスキップ
        if any(dc.startswith(num + '.') or dc.endswith('.' + num) for dc in decimal_candidates):
            continue
        if num not in candidates:
            candidates.append(num)

    # 3. 数値として不適切な候補の除外
    # 文字列をfloatに変換でき、0<=値<=100のものだけ残す
    valid_candidates = []
    for cand in candidates:
        try:
            val = float(cand)
        except ValueError:
            continue
        if not (0 <= val <= 100):
            continue  # スコア範囲外の値は除外
        valid_candidates.append((cand, val))
    if not valid_candidates:
        return None  # 該当候補なし

    # 4. 文脈によるスコア候補の評価
    best_val = None
    for cand_str, val in valid_candidates:
        # 該当する数値が含まれる行を取得
        for line in text.splitlines():
            if cand_str in line:
                # 文脈キーワードが行内に含まれるか？
                if re.search(r'平均|ボーナス|分析|レポート|前回|最新', line):
                    # ラベル付き（平均・ボーナス・分析レポート・前回など）は最終スコアではない
                    break  # この行の数値候補はスコアから除外
                # 「点」が付いているか確認（付いていなくても候補とするが、あれば信頼度UP）
                if '点' in line:
                    best_val = val
                else:
                    best_val = val
                # ラベルが無くこの数値が行内に存在 -> 最終スコアと判断
                return best_val
    # もしラベルなし候補が複数あった場合（通常は1つのはず）、一番大きい値を採用するなどの処理も考えられる
    # ここでは単純化のため、最初に見つかったラベル無し候補(best_val)を返す
    return best_val
