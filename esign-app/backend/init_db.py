import os
import time
import psycopg2
from psycopg2 import sql

# Database connection settings
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("POSTGRES_DB", "esign_metadata")
DB_USER = os.getenv("POSTGRES_USER", "admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")

def wait_for_db():
    """Wait for the database to be available."""
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            conn.close()
            print("Database is ready!")
            return
        except psycopg2.OperationalError:
            print(f"Waiting for database... ({i+1}/{max_retries})")
            time.sleep(2)
    raise Exception("Database not available after waiting.")

def init_db():
    """Initialize the database schema."""
    wait_for_db()
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    cur = conn.cursor()

    # Create document_metadata table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_metadata (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            blob_url TEXT,
            department VARCHAR(50),
            doc_type VARCHAR(50),
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Create workflow_logs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workflow_logs (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES document_metadata(id),
            action VARCHAR(50) NOT NULL,
            performed_by VARCHAR(100),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Database schema initialized successfully.")

if __name__ == "__main__":
    init_db()
