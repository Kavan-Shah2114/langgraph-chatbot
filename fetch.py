import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

# ---------------- USERS ----------------

def authenticate_user(username, password):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, username FROM users
        WHERE username=%s AND password=%s
    """, (username, password))
    
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def create_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (username, password)
        VALUES (%s, %s)
    """, (username, password))
    conn.commit()
    cur.close()
    conn.close()

# ---------------- THREADS ----------------

def add_thread_to_db(thread_id, title, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO threads (thread_id, topic, user_id)
        VALUES (%s, %s, %s)
    """, (thread_id, title, user_id))
    conn.commit()
    cur.close()
    conn.close()

def fetch_threads(user_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT thread_id AS id, topic, pinned, last_updated
        FROM threads
        WHERE user_id=%s
        ORDER BY pinned DESC, last_updated DESC
    """, (user_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data

def delete_thread(thread_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE thread_id=%s", (thread_id,))
    cur.execute("DELETE FROM documents WHERE thread_id=%s", (thread_id,))
    cur.execute("DELETE FROM threads WHERE thread_id=%s", (thread_id,))
    conn.commit()
    cur.close()
    conn.close()

def update_thread_topic(thread_id, topic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE threads
        SET topic=%s
        WHERE thread_id=%s
    """, (topic, thread_id))
    conn.commit()
    cur.close()
    conn.close()

def touch_thread(thread_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE threads
        SET last_updated=NOW()
        WHERE thread_id=%s
    """, (thread_id,))
    conn.commit()
    cur.close()
    conn.close()

def set_thread_pinned(thread_id, state):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE threads SET pinned=%s WHERE thread_id=%s
    """, (state, thread_id))
    conn.commit()
    cur.close()
    conn.close()

# ---------------- MESSAGES ----------------

def save_message(thread_id, role, content):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (thread_id, role, content)
        VALUES (%s, %s, %s)
    """, (thread_id, role, content))
    conn.commit()
    cur.close()
    conn.close()

def load_messages(thread_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT role, content
        FROM messages
        WHERE thread_id=%s
        ORDER BY created_at ASC
    """, (thread_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data

# ---------------- DOCUMENTS ----------------

def save_document(title, content, thread_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (thread_id, title, content)
        VALUES (%s, %s, %s)
    """, (thread_id, title, content))
    conn.commit()
    cur.close()
    conn.close()

def search_documents(query, thread_id, limit=10):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Always return all documents for thread if query is empty
    if not query.strip():
        cur.execute("""
            SELECT title, content FROM documents
            WHERE thread_id=%s
            ORDER BY id DESC
            LIMIT %s
        """, (thread_id, limit))
    else:
        cur.execute("""
            SELECT title, content FROM documents
            WHERE thread_id=%s
              AND content ILIKE %s
            LIMIT %s
        """, (thread_id, f"%{query}%", limit))

    data = cur.fetchall()
    cur.close()
    conn.close()
    return data