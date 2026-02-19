import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB", "esign_metadata")
DB_USER = os.getenv("POSTGRES_USER", "admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")

def migrate():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=5432
        )
        cur = conn.cursor()
        
        print("Adding access_scope to users table...")
        try:
            cur.execute("ALTER TABLE users ADD COLUMN access_scope VARCHAR DEFAULT 'global';")
        except Exception as e:
            print(f"users.access_scope already exists or error: {e}")
            conn.rollback()
        else:
            conn.commit()

        print("Adding requester_email to document_requests table...")
        try:
            cur.execute("ALTER TABLE document_requests ADD COLUMN requester_email VARCHAR;")
        except Exception as e:
            print(f"document_requests.requester_email already exists or error: {e}")
            conn.rollback()
        else:
            conn.commit()

        cur.close()
        conn.close()
        print("Migration complete!")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
