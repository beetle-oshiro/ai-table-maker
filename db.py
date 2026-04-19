# PostgreSQLに接続するためのライブラリ
import psycopg2

# .envを読み込むためのライブラリ
import os
from dotenv import load_dotenv

# .envファイルの内容を読み込む
load_dotenv()

# データベースに接続する関数
def get_connection():
    return psycopg2.connect(
        os.getenv("DATABASE_URL")
    )