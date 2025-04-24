Karaoke LINE Bot
カラオケのスコア画像をLINEに送信すると、自動でスコアを登録・評価してくれるLINE Botです。

機能一覧
スコア画像をOCRで解析（Google Cloud Vision API使用）

GPTを用いて曲名・アーティスト名・コメントを構造化

Supabaseにスコア情報を保存

単純移動平均によりユーザーの評価スコアを計算

スコアの「スコア・曲名・アーティスト・コメント」修正機能

「成績確認」と送ると自分の成績を確認可能

使い方
LINEでBotにスコア画像を送信

点数・曲名・アーティスト名が自動で登録される

「修正」と送信すると、修正項目をQuickReplyから選択できる

「成績確認」と送信すると、以下のような成績が返信される

あなたの成績
・登録回数: 84 回
・最新スコア: 80
・最高スコア: 92.17
・評価スコア: 83.101

使用技術

バックエンド	Flask (Python)
OCR	Google Cloud Vision API
データベース	Supabase (PostgreSQL)
フロント	LINE Messaging API
構造化AI	GPT（OpenAI API）
環境構築方法（ローカル）
bash


# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows の場合は venv\Scripts\activate

# パッケージのインストール
pip install -r requirements.txt

# .env ファイルの作成
cp .env.example .env
# .env に各種キーを設定（LINEのトークン、SupabaseのURLなど）



今後の拡張案
ユーザーごとのマイページ機能（LINE IDと連携）

Webでのランキング表示（Next.jsなどを使用）

店舗や大会など、複数グループ対応機能の追加

