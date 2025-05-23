import os
import sqlite3
import json
import time
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
import google.generativeai as genai

# --- Config ---
DB_PATH = "label_tasks.db"
GEMINI_API_KEY = "AIzaSyCCeiOc72dEH4Axye8L4u8c2_nNf2Un_OQ"
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

# Đường dẫn phần mềm xử lý ảnh
pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract-OCR\tesseract.exe"
os.environ["GHOSTSCRIPT_PATH"] = r"D:\gs\gs10.02.1\bin\gswin64c.exe"

# Poppler để chuyển PDF sang ảnh
poppler_path = r"D:\Release-24.08.0-0\poppler-24.08.0\Library\bin"

# --- Khởi tạo Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)

# --- Xử lý PDF ---
def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        print(f"[!] Lỗi đọc PDF: {e}")
        return ""

def extract_text_with_ocr(pdf_path):
    try:
        images = convert_from_path(pdf_path, poppler_path=poppler_path)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as e:
        print(f"[!] Lỗi OCR: {e}")
        return ""

# --- Gửi nội dung tới Gemini ---
def process_shipping_label(pdf_content):
    prompt = """You will receive the content of a shipping label. Please extract the following fields:
- Tracking Number
- Sender Address
- Recipient Address
- Delivery Date

Return ONLY a valid JSON object with clear field names. Do not include explanations or markdown formatting.
"""
    try:
        response = gemini_model.generate_content([prompt, pdf_content])
        response.resolve()
        result = response.text.strip()

        if result.startswith("```"):
            result = result.replace("```json", "").replace("```", "").strip()

        return json.loads(result) if result.startswith("{") else None
    except Exception as e:
        print(f"[!] Lỗi xử lý Gemini: {e}")
        return None

# --- Xử lý từng task ---
def process_pending_tasks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_path FROM label_tasks WHERE status = 'pending' LIMIT 1")
    task = cursor.fetchone()
    if not task:
        print("⏳ Không có task nào. Chờ thêm...")
        conn.close()
        return

    task_id, file_path = task
    print(f"\n📄 Đang xử lý file: {file_path}")

    # Cập nhật status => processing
    cursor.execute("UPDATE label_tasks SET status = 'processing' WHERE id = ?", (task_id,))
    conn.commit()

    # Đọc file PDF
    text = extract_text_from_pdf(file_path)
    if not text.strip():
        text = extract_text_with_ocr(file_path)

    if not text.strip():
        print("[❌] Không đọc được nội dung file.")
        cursor.execute("UPDATE label_tasks SET status = 'error' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
        return

    # Gửi đến Gemini
    data = process_shipping_label(text)
    if data:
        print("✅ Kết quả trích xuất:")
        print(json.dumps(data, indent=4, ensure_ascii=False))
        cursor.execute("UPDATE label_tasks SET status = 'done' WHERE id = ?", (task_id,))
    else:
        print("[❌] Không trích xuất được thông tin.")
        cursor.execute("UPDATE label_tasks SET status = 'error' WHERE id = ?", (task_id,))
    
    conn.commit()
    conn.close()

def main():
    while True:
        process_pending_tasks()  # ← hàm bạn đã định nghĩa ở trên để xử lý task

        # Sau khi xử lý, kiểm tra còn task nào status 'pending' không
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM label_tasks WHERE status = 'pending'")
            count = cursor.fetchone()[0]
            conn.close()
        except Exception as e:
            print(f"[!] SQLite error: {e}")
            break  # dừng nếu lỗi DB

        if count == 0:
            print("✅ Đã xử lý hết tất cả các task. Tự động dừng chương trình.")
            break  # ← dừng vòng lặp

        time.sleep(5)  # ← nếu còn task, chờ 5s rồi xử lý tiếp

if __name__ == "__main__":
    main()