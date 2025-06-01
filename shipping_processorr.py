import os
import pika  # type: ignore
import json
import google.generativeai as genai
from pypdf import PdfReader
from pdf2image import convert_from_path # type: ignore
import pytesseract # type: ignore
import logging
from dotenv import load_dotenv # type: ignore
import sys # Import sys for logging to sys.stdout

# Load environment variables from .env file
load_dotenv()

# --- Config ---
MESSAGE_QUEUE_HOST = os.getenv("MESSAGE_QUEUE_HOST", "localhost")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")

# If needed, specify the path to Tesseract (if it cannot be found automatically)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD_PATH = os.getenv("TESSERACT_CMD_PATH", r"D:\Tesseract-OCR\tesseract.exe")
GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH", r"D:\gs\gs10.02.1\bin\gswin64c.exe")
POPPLER_PATH = os.getenv("POPPLER_PATH", r"D:\Release-24.08.0-0\poppler-24.08.0\Library\bin")

# --- Logging Setup ---
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout) # Use sys.stdout for compatibility with containerized environments
logger = logging.getLogger(__name__)

# --- Initialize External Tools ---
if TESSERACT_CMD_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
if GHOSTSCRIPT_PATH: # Though often not directly needed by pdf2image if Poppler is set
    os.environ["GHOSTSCRIPT_PATH"] = GHOSTSCRIPT_PATH
if POPPLER_PATH:
    # Set the path to Poppler's bin directory for pdf2image to find pdftoppm.exe
    os.environ["PATH"] += os.pathsep + POPPLER_PATH

genai.configure(api_key=GEMINI_API_KEY)
try:
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    logger.info(f"Gemini model '{GEMINI_MODEL_NAME}' initialized successfully.")
except Exception as e:
    logger.critical(f"CRITICAL: Error initializing Gemini model: {e}", exc_info=True)
    exit()

# --- Gemini Prompt ---
prompt = """
You are an AI agent specialized in analyzing shipping labels from various courier services.
Your task is to extract key shipment details from the attached shipping label (provided as a PDF document).
Labels may be in different languages (including Vietnamese and English), contain both printed and handwritten text,
and come in a variety of formats. Please extract the following fields clearly and return them in a clean JSON object:
1. tracking_number  The shipment tracking number (e.g., SPXVM056647973), often labeled as "Tracking No.", "Tracking ID", or "Mã vận đơn". If multiple tracking numbers are present, prioritize the primary one or the longest one.
2. order_id  The customer order ID (e.g., "258319PMADJ01"), often labeled as "Order ID" or "Mã đơn hàng".
3. sender_address  Full sender's name, phone number, and address, typically after keywords like "FROM", "Từ", or "Sender".
4. recipient_address  Full receiver's name, phone number, and address, typically after keywords like "TO", "Đến", or "Receiver".
If any field is missing, ambiguous, or not found, return its value as "Not found".
Return your output strictly as a valid JSON object. Do not include any explanations or additional text.
Example output format: {"tracking_number": "...", "order_id": "...", "sender_address": "...", "recipient_address": "...", "delivery_date": "..."}
"""

# --- Extract PDF text via pypdf ---
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except FileNotFoundError:
        logger.error(f"File not found: {pdf_path}")
        return ""
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path} with pypdf: {e}", exc_info=True)
        return ""
    return text.strip()

# --- Fallback OCR for image-based PDFs ---
def extract_text_with_ocr(pdf_path):
    logger.info(f"🔁 Falling back to OCR for: {pdf_path}")
    try:
        # Path to the directory containing pdftoppm.exe
        if not POPPLER_PATH:
            logger.warning("POPPLER_PATH not configured. OCR might fail or be slow.")
        images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image) + "\n" # Add newline like pypdf extraction
        return text.strip()
    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: {e}", exc_info=True)
        return ""

# --- Process shipping label via Gemini ---
def process_shipping_label(pdf_content: str):
    try:
        if not pdf_content.strip():
            logger.warning("PDF content for shipping label is empty. Skipping Gemini call.")
            return None

        logger.info(f"Sending content (length: {len(pdf_content)}) to Gemini for shipping label processing.")
        response = gemini_model.generate_content([prompt, pdf_content]) # Corrected method name
        response.resolve()

        if response.parts:
            result = response.parts[0].text.strip()
            logger.debug(f"=== Gemini Raw Response (Shipping) ===\n{result}")

            # Clean up markdown (e.g., ```json ... ```)
            if result.startswith("```json"):
                result = result[len("```json"):].strip()
            if result.startswith("```"): # General case after json specific
                result = result[len("```"):].strip()
            if result.endswith("```"):
                result = result[:-len("```")].strip()
            try:
                return json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for shipping label: {e}. Raw response: '{result}'", exc_info=True)
                return None
        else:
            logger.warning(f"No content (parts) received from Gemini for shipping label. Prompt feedback: {getattr(response, 'prompt_feedback', 'N/A')}")
            return None

    except Exception as e:
        logger.error(f"Error during Gemini extraction for shipping label: {e}", exc_info=True)
        if 'response' in locals() and hasattr(response, 'prompt_feedback'): # Log feedback if available
            logger.error(f"Gemini Prompt Feedback: {response.prompt_feedback}")
        return None

# --- RabbitMQ callback ---
def callback(ch, method, properties, body):
    message = json.loads(body.decode())
    file_path = message.get("file_path")
    logger.info(f"📄 Received task for shipping label: {file_path}")

    # Step 1: Try extract with pypdf
    pdf_text = extract_text_from_pdf(file_path)
    logger.debug(f"🔍 PDF Text Preview (pypdf) for {file_path}:\n{pdf_text[:300] if pdf_text else '[Empty]'}")

    # Step 2: Fallback to OCR if needed
    if not pdf_text.strip():
        pdf_text = extract_text_with_ocr(file_path)
        logger.debug(f"🔍 PDF Text Preview (OCR) for {file_path}:\n{pdf_text[:300] if pdf_text else '[Empty]'}")

    if not pdf_text.strip():
        logger.warning(f"Skipping file (unreadable after pypdf and OCR): {file_path}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    extracted_data = process_shipping_label(pdf_text)
    if extracted_data:
        logger.info(f"✅ Extracted Shipping Label Data for {file_path}:")
        logger.info(json.dumps(extracted_data, indent=2, ensure_ascii=False)) # Indent 2 for brevity in logs
    else:
        logger.error(f"Failed to extract data from shipping label: {file_path}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

# --- Main function to start RabbitMQ consumer ---
def main():
    connection = None
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=MESSAGE_QUEUE_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='shipping_queue', durable=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='shipping_queue', on_message_callback=callback)
        logger.info("🔄 [*] Waiting for shipping label tasks. To exit press CTRL+C")
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        logger.critical(f"Failed to connect to RabbitMQ: {e}", exc_info=True)
        sys.exit(1) # Exit if connection fails
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping consumer...")
        if connection and connection.is_open:
            connection.stop_consuming()
    except Exception as e:
        logger.critical(f"Unhandled exception in main consumer loop: {e}", exc_info=True)
    finally:
        if connection and connection.is_open:
            connection.close()
            logger.info("RabbitMQ connection closed. Exiting.")

# --- Entry Point ---
if __name__ == "__main__":
    main()