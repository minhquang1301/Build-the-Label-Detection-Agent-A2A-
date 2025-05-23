import os
import json
import sqlite3
import time
import google.generativeai as genai
from pypdf import PdfReader
from pdf2image import convert_from_path  # type: ignore
import pytesseract  # type: ignore

# --- Cấu hình ---
pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract-OCR\tesseract.exe"
os.environ["GHOSTSCRIPT_PATH"] = r"D:\gs\gs10.02.1\bin\gswin64c.exe"
DB_PATH = "task_queue.db"

GEMINI_API_KEY = "YOUR GEMINI API KEY"
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

# --- Cấu hình Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
try:
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    print(f"[!] Error initializing Gemini model: {e}")
    exit()

# --- SQLite Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

# --- Thêm task mới ---
def add_task(file_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (file_path, status) VALUES (?, ?)", (file_path, "pending"))
    conn.commit()
    conn.close()

# --- Lấy task tiếp theo ---
def get_next_task():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path FROM tasks WHERE status = 'pending' LIMIT 1")
    task = cursor.fetchone()
    conn.close()
    return task

# --- Cập nhật trạng thái task ---
def update_task_status(task_id, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()

# --- Trích xuất nội dung PDF ---
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
        print(f"[!] Error reading PDF {pdf_path}: {e}")
    return text

# --- Fallback OCR ---
def extract_text_with_ocr(pdf_path):
    print("🔁 Falling back to OCR...")
    try:
        poppler_path = r"D:\Release-24.08.0-0\poppler-24.08.0\Library\bin"
        images = convert_from_path(pdf_path, poppler_path=poppler_path)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"[!] OCR failed for {pdf_path}: {e}")
        return ""

# --- Gọi Gemini ---
def process_shipping_label(pdf_content):
    prompt = """You will receive the content of a shipping label. Please extract the following fields:
- Tracking Number
- Sender Address
- Recipient Address
- Delivery Date

Return ONLY a valid JSON object with clear field names. Do not include explanations or markdown formatting.
"""

    try:
        if not pdf_content.strip():
            print("[!] PDF content is empty. Skipping Gemini call.")
            return None

        response = gemini_model.generate_content([prompt, pdf_content])
        response.resolve()

        if response.parts:
            result = response.parts[0].text.strip()
            if result.startswith("```"):
                result = result.replace("```json", "").replace("```", "").strip()

            if result.startswith("{") and result.endswith("}"):
                try:
                    return json.loads(result)
                except json.JSONDecodeError as e:
                    print(f"[!] JSON decode error: {e}")
                    return None
            else:
                print("[!] Gemini response is not valid JSON.")
                return None
        else:
            print("[!] No content received from Gemini.")
            return None
    except Exception as e:
        print(f"[!] Error during Gemini extraction: {e}")
        return None

# --- Main Loop ---
def main():
    init_db()
    print("🔄 Waiting for PDF tasks in SQLite. Press CTRL+C to exit.")

    while True:
        task = get_next_task()
        if not task:
            time.sleep(2)
            continue

        task_id, file_path = task
        print(f"\n📄 Processing: {file_path}")
        update_task_status(task_id, "processing")

        pdf_text = extract_text_from_pdf(file_path)
        if not pdf_text.strip():
            pdf_text = extract_text_with_ocr(file_path)

        if not pdf_text.strip():
            print("[!] Cannot read PDF content. Skipping.")
            update_task_status(task_id, "failed")
            continue

        extracted_data = process_shipping_label(pdf_text)
        if extracted_data:
            print("✅ Extracted Data:")
            print(json.dumps(extracted_data, indent=4, ensure_ascii=False))
            update_task_status(task_id, "done")
        else:
            print("[!] Extraction failed.")
            update_task_status(task_id, "failed")

        time.sleep(1)

if __name__ == "__main__":
    main()
