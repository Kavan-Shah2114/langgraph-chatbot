# fetch.py
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432"),
        database=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASS")
    )

# ------------- Users -------------
def create_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (username, password)
        VALUES (%s, %s)
        ON CONFLICT (username) DO NOTHING
    """, (username, password))
    conn.commit()
    conn.close()

def authenticate_user(username, password):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    row = cur.fetchone()
    conn.close()
    return row

# ------------- Threads -------------
def ensure_threads_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            thread_id TEXT PRIMARY KEY,
            topic TEXT,
            pinned BOOLEAN DEFAULT FALSE,
            last_updated TIMESTAMP DEFAULT NOW(),
            user_id INTEGER
        );
    """)
    conn.commit()
    conn.close()

def add_thread_to_db(thread_id, topic, user_id):
    ensure_threads_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO threads (thread_id, topic, last_updated, user_id)
        VALUES (%s, %s, NOW(), %s)
        ON CONFLICT (thread_id) DO NOTHING
    """, (thread_id, topic, user_id))
    conn.commit()
    conn.close()

def fetch_threads(user_id):
    ensure_threads_table()
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT thread_id AS id, topic, pinned, last_updated
        FROM threads
        WHERE user_id = %s
        ORDER BY pinned DESC, last_updated DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def update_thread_topic(thread_id, topic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE threads SET topic=%s, last_updated=NOW() WHERE thread_id=%s", (topic, thread_id))
    conn.commit()
    conn.close()

def touch_thread(thread_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE threads SET last_updated=NOW() WHERE thread_id=%s", (thread_id,))
    conn.commit()
    conn.close()

def set_thread_pinned(thread_id, pinned: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE threads SET pinned=%s WHERE thread_id=%s", (pinned, thread_id))
    conn.commit()
    conn.close()

def delete_thread(thread_id):
    # delete thread cascades messages (if FK configured) and remove docs/notes:
    conn = get_connection()
    cur = conn.cursor()
    # delete messages
    cur.execute("DELETE FROM messages WHERE thread_id=%s", (thread_id,))
    # delete documents linked to the thread
    cur.execute("DELETE FROM documents WHERE thread_id=%s", (thread_id,))
    # delete thread
    cur.execute("DELETE FROM threads WHERE thread_id=%s", (thread_id,))
    conn.commit()
    conn.close()

# ------------- Messages (persist chat history) -------------
def ensure_messages_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            thread_id TEXT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    conn.close()

def save_message(thread_id, role, content):
    ensure_messages_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (thread_id, role, content) VALUES (%s, %s, %s)", (thread_id, role, content))
    conn.commit()
    conn.close()

def load_messages(thread_id):
    ensure_messages_table()
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT role, content FROM messages WHERE thread_id=%s ORDER BY created_at ASC", (thread_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ------------- Documents / Knowledge Base (per-thread) -------------
def ensure_documents_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            title TEXT,
            content TEXT,
            content_tsv tsvector,
            thread_id TEXT
        );
    """)
    conn.commit()
    conn.close()

def save_document(title, content, thread_id=None):
    ensure_documents_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO documents (title, content, thread_id) VALUES (%s, %s, %s)", (title, content, thread_id))
    conn.commit()
    conn.close()

def search_documents(query, thread_id=None, limit=3):
    ensure_documents_table()
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if thread_id:
        cur.execute("""
            SELECT id, title, content FROM documents
            WHERE thread_id = %s AND content_tsv @@ plainto_tsquery('english', %s)
            ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('english', %s)) DESC
            LIMIT %s
        """, (thread_id, query, query, limit))
    else:
        cur.execute("""
            SELECT id, title, content FROM documents
            WHERE content_tsv @@ plainto_tsquery('english', %s)
            ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('english', %s)) DESC
            LIMIT %s
        """, (query, query, limit))
    rows = cur.fetchall()
    conn.close()
    return rows