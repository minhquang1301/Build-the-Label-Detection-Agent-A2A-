import os
import json
import time
import sqlite3
import google.generativeai as genai
from pypdf import PdfReader

# --- Configuration ---
DB_PATH = "return_tasks.db"
GEMINI_API_KEY = "YOUR GEMINI API KEY"
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

genai.configure(api_key=GEMINI_API_KEY)
try:
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    exit()

# --- SQLite Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS return_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

def add_task(file_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO return_tasks (file_path, status) VALUES (?, ?)", (file_path, "pending"))
    conn.commit()
    conn.close()

def get_next_task():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path FROM return_tasks WHERE status = 'pending' LIMIT 1")
    task = cursor.fetchone()
    conn.close()
    return task

def update_task_status(task_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE return_tasks SET status = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()

# --- PDF Extraction ---
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

# --- Gemini Extraction ---
def process_return_label(pdf_content):
    prompt = """Extract the following information from this return label:
    - Return ID
    - Order ID
    - Reason for return
    - Return Date

Return the result as a JSON object.
"""

    try:
        response = gemini_model.generate_content([prompt, pdf_content])
        response.resolve()
        if response.parts:
            result = response.parts[0].text.strip()
            print("Gemini response:")
            print(result)

            if result.startswith("```"):
                result = result.replace("```json", "").replace("```", "").strip()

            return json.loads(result)
        else:
            print("No parts in Gemini response.")
            return None
    except Exception as e:
        print(f"Error during Gemini data extraction for return label: {e}")
        return None

# --- Main Loop ---
def main():
    init_db()
    print('🔁 Waiting for return label tasks in SQLite. Press CTRL+C to exit.')

    while True:
        task = get_next_task()
        if not task:
            time.sleep(2)
            continue

        task_id, file_path = task
        print(f"\n📄 Processing return label: {file_path}")
        update_task_status(task_id, "processing")

        pdf_text = extract_text_from_pdf(file_path)
        if pdf_text:
            extracted_data = process_return_label(pdf_text)
            if extracted_data:
                print("✅ Extracted Return Label Data:")
                print(json.dumps(extracted_data, indent=4))
                update_task_status(task_id, "done")
            else:
                print(f"[!] Failed to extract data from return label: {file_path}")
                update_task_status(task_id, "failed")
        else:
            print(f"[!] Could not read PDF: {file_path}")
            update_task_status(task_id, "failed")

        time.sleep(1)

if __name__ == "__main__":
    main()
