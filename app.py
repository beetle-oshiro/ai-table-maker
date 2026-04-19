# Flask本体を使うために読み込む
from flask import Flask, render_template, request

# db.py の get_connection 関数を使うために読み込む
from db import get_connection

# OpenAI APIを使うために読み込む
from openai import OpenAI

# .env を読み込むためのライブラリ
from dotenv import load_dotenv

# 環境変数を使うためのライブラリ
import os

# JSON文字列をPythonで使える形に変換するためのライブラリ
import json

# PostgreSQLで安全にSQLを組み立てるためのライブラリ
from psycopg2 import sql


# .envファイルの内容を読み込む
load_dotenv()

# Flaskアプリを作成
app = Flask(__name__)

# OpenAIクライアントを作成
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# AIに入力内容を整理してもらう関数
def make_table_data_with_ai(table_name, columns):

    # AIへの指示文
    prompt = f"""
あなたはテーブル作成補助AIです。
以下の内容を整理して、必ずJSON形式だけで返してください。

【ルール】
- table_name はそのまま使う
- columns は配列にする
- 各columnは name と type を持つ
- 説明文は不要
- ```json なども不要
- JSON以外の文章は一切書かない

【返却例】
{{
  "table_name": "books",
  "columns": [
    {{"name": "title", "type": "TEXT"}},
    {{"name": "price", "type": "INTEGER"}},
    {{"name": "published_date", "type": "DATE"}}
  ]
}}

【入力データ】
table_name: {table_name}

columns:
{json.dumps(columns, ensure_ascii=False)}
"""

    # OpenAI APIを呼び出す
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    # AIが返したテキストを返す
    return response.output_text


# トップページ
@app.route("/")
def form():
    return render_template("form.html")


# テーブル一覧
@app.route("/tables")
def tables():

    # DB接続
    conn = get_connection()
    cur = conn.cursor()

    # publicスキーマのテーブル一覧を取得
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)

    tables_data = cur.fetchall()

    # テーブル名だけ取り出す
    table_list = [row[0] for row in tables_data]

    # 接続を閉じる
    cur.close()
    conn.close()

    return render_template("tables.html", tables=table_list)


# 確認画面
@app.route("/confirm", methods=["POST"])
def confirm():

    # フォームからデータを受け取る
    table_name = request.form.get("table_name")

    col1_name = request.form.get("col1_name")
    col1_type = request.form.get("col1_type")

    col2_name = request.form.get("col2_name")
    col2_type = request.form.get("col2_type")

    col3_name = request.form.get("col3_name")
    col3_type = request.form.get("col3_type")

    # いったんフォームの内容をまとめる
    columns = [
        {"name": col1_name, "type": col1_type},
        {"name": col2_name, "type": col2_type},
        {"name": col3_name, "type": col3_type},
    ]

    # AIに内容を整理してもらう
    ai_result_text = make_table_data_with_ai(table_name, columns)

    # AIの返り値(JSON文字列)をPythonの辞書に変換する
    ai_result = json.loads(ai_result_text)

    # 整理後の値を取り出す
    ai_table_name = ai_result["table_name"]
    ai_columns = ai_result["columns"]

    # 確認画面に渡す
    return render_template(
        "confirm.html",
        table_name=ai_table_name,
        columns=ai_columns
    )


# テーブル作成
@app.route("/create", methods=["POST"])
def create_table():

    # 確認画面から送られてきたデータを受け取る
    table_name = request.form.get("table_name")
    col_names = request.form.getlist("col_name")
    col_types = request.form.getlist("col_type")

    # カラム定義を1つずつ作るための入れ物
    column_defs = []

    # カラム名と型を組み合わせて、SQL用の部品を作る
    for name, col_type in zip(col_names, col_types):
        column_defs.append(
            sql.SQL("{} {}").format(
                sql.Identifier(name),
                sql.SQL(col_type)
            )
        )

    # CREATE TABLE文を安全に作成
    create_sql = sql.SQL("CREATE TABLE {} ({});").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(column_defs)
    )

    # データベースに接続
    conn = get_connection()
    cur = conn.cursor()

    # SQLを実行
    cur.execute(create_sql)

    # 保存を確定
    conn.commit()

    # 接続を閉じる
    cur.close()
    conn.close()

    return render_template("create_done.html", table_name=table_name)


# テーブルの中身を表示
@app.route("/view/<table_name>")
def view_table(table_name):

    # データベースに接続
    conn = get_connection()
    cur = conn.cursor()

    # テーブルのデータを取得
    cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name)))
    rows = cur.fetchall()

    # カラム名を取得
    columns = [desc[0] for desc in cur.description]

    # 接続を閉じる
    cur.close()
    conn.close()

    # 一覧画面を表示
    return render_template(
        "view_table.html",
        table_name=table_name,
        columns=columns,
        rows=rows
    )


# データ追加画面を表示
@app.route("/add/<table_name>")
def add_form(table_name):

    # データベースに接続
    conn = get_connection()
    cur = conn.cursor()

    # テーブルのカラム情報を取得
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    columns_data = cur.fetchall()

    # カラム名だけ取り出す
    columns = [row[0] for row in columns_data]

    # 接続を閉じる
    cur.close()
    conn.close()

    # 入力画面を表示
    return render_template(
        "add_form.html",
        table_name=table_name,
        columns=columns
    )


# データを登録する
@app.route("/insert/<table_name>", methods=["POST"])
def insert_data(table_name):

    # データベースに接続
    conn = get_connection()
    cur = conn.cursor()

    # テーブルのカラム情報を取得
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    columns_data = cur.fetchall()

    # カラム名だけ取り出す
    columns = [row[0] for row in columns_data]

    # フォームから入力値を取得
    values = []
    for col in columns:
        values.append(request.form.get(col))

    # INSERT文を安全に作成
    insert_sql = sql.SQL("INSERT INTO {} ({}) VALUES ({});").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join([sql.Identifier(col) for col in columns]),
        sql.SQL(", ").join([sql.Placeholder() for _ in columns])
    )

    # SQLを実行
    cur.execute(insert_sql, values)

    # 保存を確定
    conn.commit()

    # 接続を閉じる
    cur.close()
    conn.close()

    # 一覧画面に戻る
    return render_template("insert_done.html", table_name=table_name)


# アプリ起動
if __name__ == "__main__":
    app.run(debug=True)