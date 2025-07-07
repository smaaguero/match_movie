from app import app, db, init_db

with app.app_context():
    init_db()
