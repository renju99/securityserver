from database import SessionLocal
import models
import json

db = SessionLocal()
user = db.query(models.User).filter(models.User.email == 'Ranjith.Krishnan@berkeleyuae.com').first()
if user:
    print(f"User: {user.email}")
    print(f"Role: {user.role}")
    print(f"Access Scope: {user.access_scope}")
    print(f"Permissions: {json.dumps(user.permissions)}")
else:
    print("User not found")
db.close()
