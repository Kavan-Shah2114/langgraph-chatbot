import sqlite3

DB_PATH = "chatbot.db"

def fetch_threads():
    """Fetch thread IDs + topics from DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT thread_id, topic FROM threads")
    rows = cursor.fetchall()
    conn.close()

    return [{"id": r[0], "topic": r[1]} for r in rows]

def add_thread_to_db(thread_id, topic="New Chat"):
    """Insert thread into DB if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO threads (thread_id, topic) VALUES (?, ?)",
        (thread_id, topic),
    )
    conn.commit()
    conn.close()

def update_thread_topic(thread_id, topic):
    """Update topic name in DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE threads SET topic = ? WHERE thread_id = ?",
        (topic, thread_id),
    )
    conn.commit()
    conn.close()