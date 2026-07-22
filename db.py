import os
import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "Emara_shop"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD")
    )