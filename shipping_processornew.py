import os
import pika   # type: ignore
import json
import google.generativeai as genai
from pypdf import PdfReader
from pdf2image import convert_from_path # type: ignore
import pytesseract # type: ignore
pytesseract.pytesseract.tesseract_cmd = r"D:\Tesseract-OCR\tesseract.exe"
os.environ["GHOSTSCRIPT_PATH"] = r"D:\gs\gs10.02.1\bin\gswin64c.exe" 
# --- Config ---
MESSAGE_QUEUE_HOST = "localhost"
GEMINI_API_KEY = "YOUR GEMINI_API_KEY"
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

# Nếu cần, chỉ định đường dẫn đến Tesseract (nếu không tự tìm được)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

genai.configure(api_key=GEMINI_API_KEY)
try:
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    print(f"[!] Error initializing Gemini model: {e}")
    exit()

# --- Extract PDF text via pypdf ---
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

# --- Fallback OCR for image-based PDFs ---
def extract_text_with_ocr(pdf_path):
    print("🔁 Falling back to OCR...")
    try:
        # Đường dẫn đến thư mục chứa pdftoppm.exe
        poppler_path = r"D:\Release-24.08.0-0\poppler-24.08.0\Library\bin"  # 🔁 Thay bằng đường đúng trên máy bạn
        images = convert_from_path(pdf_path, poppler_path=poppler_path)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"[!] OCR failed for {pdf_path}: {e}")
        return ""

# --- Process shipping label via Gemini ---
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
            print("=== Gemini Raw Response ===")
            print(result)

            # Clean up markdown (e.g., ```json ... ```)
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

# --- RabbitMQ callback ---
def callback(ch, method, properties, body):
    message = json.loads(body.decode())
    file_path = message.get("file_path")
    print(f"\n📄 Received task for shipping label: {file_path}")

    # Step 1: Try extract with pypdf
    pdf_text = extract_text_from_pdf(file_path)
    print("🔍 PDF Text Preview (pypdf):")
    print(pdf_text[:300] if pdf_text else "[Empty]")

    # Step 2: Fallback to OCR if needed
    if not pdf_text.strip():
        pdf_text = extract_text_with_ocr(file_path)
        print("🔍 PDF Text Preview (OCR):")
        print(pdf_text[:300] if pdf_text else "[Empty]")

    if not pdf_text.strip():
        print(f"[!] Skipping file (unreadable): {file_path}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    extracted_data = process_shipping_label(pdf_text)
    if extracted_data:
        print("✅ Extracted Shipping Label Data:")
        print(json.dumps(extracted_data, indent=4, ensure_ascii=False))
    else:
        print(f"[!] Failed to extract data from shipping label: {file_path}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

# --- Main function ---
def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(MESSAGE_QUEUE_HOST))
    channel = connection.channel()
    channel.exchange_declare(exchange='label_tasks', exchange_type='direct', durable=True)
    channel.queue_declare(queue='shipping_queue', durable=True)
    channel.queue_bind(exchange='label_tasks', queue='shipping_queue', routing_key='shipping')

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='shipping_queue', on_message_callback=callback)

    print("🔄 [*] Waiting for shipping label tasks. To exit press CTRL+C")
    channel.start_consuming()

# --- Entry Point ---
if __name__ == "__main__":
    main()
