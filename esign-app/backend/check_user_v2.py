from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
import json
import os

# Override for local execution
os.environ["POSTGRES_HOST"] = "localhost"
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "esign_metadata")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.email == 'Ranjith.Krishnan@berkeleyuae.com').first()
    if user:
        print(f"User: {user.email}")
        print(f"Role: {user.role}")
        print(f"Access Scope: {user.access_scope}")
        print(f"Permissions: {json.dumps(user.permissions)}")
    else:
        print("User not found")
finally:
    db.close()
