# test_db.py
from fetch import get_connection
try:
    conn = get_connection()
    print("Connected to DB ok")
    conn.close()
except Exception as e:
    print("DB connection failed:", e)