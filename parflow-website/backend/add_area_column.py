from app import app
from models import db
import sqlite3

def add_area_column():
    with app.app_context():
        conn = sqlite3.connect('instance/watershed.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(watersheds)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'area' not in columns:
            cursor.execute("ALTER TABLE watersheds ADD COLUMN area FLOAT")
            conn.commit()
            print("✅ 列 area 已成功添加")
        else:
            print("ℹ️ 列 area 已存在，无需添加")
        conn.close()

if __name__ == '__main__':
    add_area_column()