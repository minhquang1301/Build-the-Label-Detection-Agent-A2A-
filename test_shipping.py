import os
import pika  # type: ignore
import json
import google.generativeai as genai
from pypdf import PdfReader
from pdf2image import convert_from_path  # type: ignore
import pytesseract  # type: ignore
import logging
from dotenv import load_dotenv  # type: ignore
import sys
import time

# Load environment variables
load_dotenv()

# --- Config ---
MESSAGE_QUEUE_HOST = os.getenv("MESSAGE_QUEUE_HOST", "localhost")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")
TESSERACT_CMD_PATH = os.getenv("TESSERACT_CMD_PATH", r"D:\\Tesseract-OCR\\tesseract.exe")
GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH", r"D:\\gs\\gs10.02.1\\bin\\gswin64c.exe")
POPPLER_PATH = os.getenv("POPPLER_PATH", r"D:\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin")

# --- Logging Setup ---
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- External Tool Setup ---
if TESSERACT_CMD_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
if GHOSTSCRIPT_PATH:
    os.environ["GHOSTSCRIPT_PATH"] = GHOSTSCRIPT_PATH
if POPPLER_PATH:
    os.environ["PATH"] += os.pathsep + POPPLER_PATH

# --- Gemini Model Initialization ---
def get_gemini_model():
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel(GEMINI_MODEL_NAME)
    except Exception as e:
        logger.critical(f"Error initializing Gemini model: {e}", exc_info=True)
        return None

# --- Gemini Prompt ---
prompt = """
You are an AI agent specialized in analyzing shipping labels from various courier services.
Your task is to extract key shipment details from the attached shipping label (provided as a PDF document).
Labels may be in different languages (including Vietnamese and English), contain both printed and handwritten text,
and come in a variety of formats. Please extract the following fields clearly and return them in a clean JSON object:
1. tracking_number
2. order_id
3. sender_address
4. recipient_address
Return your output strictly as a valid JSON object.
"""

# --- Text Extraction ---
def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        return "\n".join(filter(None, (page.extract_text() for page in reader.pages)))
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}", exc_info=True)
        return ""

def extract_text_with_ocr(pdf_path):
    logger.info(f"Fallback to OCR for: {pdf_path}")
    try:
        images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: {e}", exc_info=True)
        return ""

# --- Process Gemini Response ---
def process_shipping_label(pdf_content):
    if not pdf_content.strip():
        logger.warning("PDF content is empty.")
        return None

    model = get_gemini_model()
    if not model:
        return None

    try:
        logger.info(f"Sending content to Gemini (len={len(pdf_content)})")
        for attempt in range(3):
            try:
                response = model.generate_content([prompt, pdf_content])
                response.resolve()
                break
            except Exception as e:
                logger.warning(f"Gemini failed (attempt {attempt+1}/3): {e}")
                time.sleep(2 ** attempt)
        else:
            return None

        raw_text = response.text.strip()
        logger.debug(f"Gemini output preview: {raw_text[:500]}")

        if raw_text.startswith("```json"):
            raw_text = raw_text.removeprefix("```json").removesuffix("```").strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.removeprefix("```").removesuffix("```").strip()

        return json.loads(raw_text)
    except Exception as e:
        logger.error(f"Gemini processing error: {e}", exc_info=True)
        return None

# --- RabbitMQ Callback ---
def callback(ch, method, properties, body):
    message = json.loads(body.decode())
    file_path = message.get("file_path")
    logger.info(f"Received task: {file_path}")

    text = extract_text_from_pdf(file_path)
    if not text.strip():
        text = extract_text_with_ocr(file_path)

    if not text.strip():
        logger.warning(f"Unreadable PDF: {file_path}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    extracted_data = process_shipping_label(text)
    if extracted_data:
        logger.info(f"Extracted Data: {json.dumps(extracted_data, indent=2, ensure_ascii=False)}")
    else:
        logger.error(f"Failed to extract data from: {file_path}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

# --- Main Consumer ---
def main():
    connection = None
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=MESSAGE_QUEUE_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='shipping_queue', durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='shipping_queue', on_message_callback=callback)
        logger.info("Waiting for tasks. Press CTRL+C to exit.")
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        logger.critical(f"RabbitMQ connection failed: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Stopping consumer...")
    except Exception as e:
        logger.critical(f"Unhandled error: {e}", exc_info=True)
    finally:
        if connection and connection.is_open:
            connection.close()
            logger.info("RabbitMQ connection closed.")

# --- Entry Point ---
if __name__ == "__main__":
    main()
