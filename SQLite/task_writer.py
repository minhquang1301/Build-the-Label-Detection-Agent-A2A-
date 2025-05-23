import os
import datetime
import time
import sqlite3

DAILY_FOLDER_BASE = r"D:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\daily"
DB_PATH = "label_tasks.db"

LABEL_PATTERNS = {
    "shipping": "shippinglabel",
    "product": "productinfo",
    "return": "returnlabel"
}

def get_daily_folder_path():
    today = datetime.date.today()
    return os.path.join(DAILY_FOLDER_BASE, today.strftime("%Y-%m-%d"))

def identify_label_type(filename):
    for label_type, pattern in LABEL_PATTERNS.items():
        if pattern.lower() in filename.lower():
            return label_type
    return None

def insert_task(file_path, label_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS label_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            label_type TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM label_tasks WHERE file_path = ?", (file_path,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO label_tasks (file_path, label_type) VALUES (?, ?)", (file_path, label_type))
        print(f"📥 Ghi task mới: {file_path}")
    conn.commit()
    conn.close()

def main():
    while True:
        daily_folder = get_daily_folder_path()
        if os.path.exists(daily_folder):
            for filename in os.listdir(daily_folder):
                if filename.lower().endswith(".pdf"):
                    filepath = os.path.join(daily_folder, filename)
                    label_type = identify_label_type(filename)
                    if label_type:
                        insert_task(filepath, label_type)
                    else:
                        print(f"❓ Không xác định được loại nhãn: {filepath}")
            time.sleep(60)
        else:
            print(f"📂 Chưa có thư mục hôm nay: {daily_folder}")
            time.sleep(3600)

if __name__ == "__main__":
    main()