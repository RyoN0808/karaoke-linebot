from typing import List, Dict, Optional
from utils import rating  # rating.pyにランク判定用の関数・定数がある想定

def predict_next_rating(scores: List[float]) -> Dict[str, Optional[float]]:
    """
    ユーザーのスコアリストから次回投稿時のレーティング変動を予測する関数。
    最新のスコア記録に基づき、仮定した次回1件のスコアを加味して新しい平均スコアを算出し、
    現在のランクよりランクアップする条件やランクダウンする条件を判定する。
    結果として、次回何点以上でランクアップするか、何点未満でランクダウンとなるかを示す情報をJSON形式で返す。
    """
    result: Dict[str, Optional[float]] = {}
    total_scores = len(scores)
    if total_scores == 0:
        # スコア記録がない場合は予測不能なので空の結果を返す
        return result

    # 評価対象とするスコア数の決定：30件以上なら最新29件、未満なら全件
    if total_scores >= 30:
        base_scores = scores[:29]   # 最新29件（次回投稿時に残るスコア群）
        new_count = 30             # 次回投稿後の評価対象件数は30件で固定
    else:
        base_scores = scores[:]    # 全スコア（次回投稿時もすべて残る）
        new_count = total_scores + 1  # 次回投稿後は件数が1つ増える

    base_sum = sum(base_scores)  # ベースとなる最新29件（または全件）の合計値

    # 現在の平均スコアとランクを算出（評価対象は現時点で最大30件）
    current_count = min(total_scores, 30)
    current_avg = sum(scores[:current_count]) / current_count
    current_rank = rating.get_rank(current_avg)  # 現在のランクを取得（例："A", "B", など）

    # 上位ランクと下位ランクを取得
    next_rank = rating.get_next_rank(current_rank)       # 1つ上のランク（無ければNone）
    lower_rank = rating.get_previous_rank(current_rank)  # 1つ下のランク（無ければNone）

    # ランクアップ閾値計算
    if next_rank:
        next_threshold = rating.get_threshold(next_rank)  # 上位ランクの最低平均値
        # 次回スコアがこの値以上ならランクアップする最低値を計算
        required_score = next_threshold * new_count - base_sum
        # 小数点が出た場合は切り上げる（そのスコア「以上」でランクアップのため）
        required_score = math.ceil(required_score)
        if required_score <= 0:
            required_score = 0  # マイナスは0に補正
        # 100点満点を超える場合もそのまま記録（次回1回では到達不可の指標）
        result["rank_up_score"] = required_score
    else:
        # 現在が最高ランクの場合はランクアップ閾値なし
        result["rank_up_score"] = None

    # ランクダウン閾値計算
    if lower_rank:
        current_threshold = rating.get_threshold(current_rank)  # 現在ランク維持に必要な最低平均
        # 次回スコアがこの値を下回るとランクダウンとなる境界値を計算
        # （平均がcurrent_thresholdちょうどになるスコアを求め、それ未満でダウン）
        boundary_score = current_threshold * new_count - base_sum
        # 境界値（平均ぎりぎり維持できる次回スコア）。これ未満でアウト。
        boundary_score = math.floor(boundary_score)
        if boundary_score < 0:
            boundary_score = 0
        # ランクダウン判定は「boundary_score未満」なので、ユーザーには boundary_score を閾値として提示
        result["rank_down_score"] = boundary_score
        # もし0点未満が境界の場合（通常ありえないが念のため）、Noneにする
        if result["rank_down_score"] == 0 and (current_threshold * new_count - base_sum) <= 0:
            result["rank_down_score"] = None
    else:
        # 最低ランクの場合はランクダウン閾値なし
        result["rank_down_score"] = None

    return result
