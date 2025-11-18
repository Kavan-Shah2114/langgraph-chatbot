-- Create users table
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL
);

-- Create threads table (user_id may be missing; this adds it if needed)
CREATE TABLE IF NOT EXISTS threads (
  thread_id TEXT PRIMARY KEY,
  topic TEXT,
  pinned BOOLEAN DEFAULT FALSE,
  last_updated TIMESTAMP DEFAULT NOW(),
  user_id INTEGER
);

-- Create messages table (per-thread conversation persistence)
CREATE TABLE IF NOT EXISTS messages (
  id SERIAL PRIMARY KEY,
  thread_id TEXT REFERENCES threads(thread_id) ON DELETE CASCADE,
  role TEXT,
  content TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Create documents table; ensure columns exist (title, content, content_tsv, thread_id)
CREATE TABLE IF NOT EXISTS documents (
  id SERIAL PRIMARY KEY,
  title TEXT,
  content TEXT,
  content_tsv tsvector,
  thread_id TEXT
);

-- Create tsvector trigger using built-in helper (idempotent)
-- If tsvector_update_trigger doesn't exist in your PG (it is standard), the DO block will still work.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'documents_tsvector_update'
  ) THEN
    PERFORM set_config('search_path', current_schema(), false);
    CREATE TRIGGER documents_tsvector_update
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION
    tsvector_update_trigger(content_tsv, 'pg_catalog.english', title, content);
  END IF;
END$$;

-- GIN index for full-text search
CREATE INDEX IF NOT EXISTS documents_tsv_idx ON documents USING GIN(content_tsv);

SELECT * FROM documents;