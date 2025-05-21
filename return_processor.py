import os
import pika # type: ignore
import json
import google.generativeai as genai
from pypdf import PdfReader

# --- Configuration ---
MESSAGE_QUEUE_HOST = "localhost"
GEMINI_API_KEY = "YOUR GEMINI_API_KEY"  # Replace with your actual API key
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"

genai.configure(api_key=GEMINI_API_KEY)
try:
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    exit()

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

def process_return_label(pdf_content):
    prompt = f"""Extract the following information from this return label:
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
            print("Gemini response:")
            print(response.parts[0].text)  # In ra nội dung để kiểm tra
            return json.loads(response.parts[0].text)
        else:
            print("No parts in Gemini response.")
            return None
    except Exception as e:
        print(f"Error during Gemini data extraction for return label: {e}")
        return None

def callback(ch, method, properties, body):
    message = json.loads(body.decode())
    file_path = message['file_path']
    print(f"Received task for shipping label: {file_path}")

    pdf_text = extract_text_from_pdf(file_path)
    if pdf_text:
        extracted_data = process_return_label(pdf_text)
        if extracted_data:
            print("Extracted Shipping Label Data:")
            print(json.dumps(extracted_data, indent=4))
            # In a real application, you would store this data
        else:
            print(f"Failed to extract data from shipping label: {file_path}")
    else:
        print(f"Could not read PDF: {file_path}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(MESSAGE_QUEUE_HOST))
    channel = connection.channel()
    channel.exchange_declare(exchange='label_tasks', exchange_type='direct', durable=True)
    channel.queue_declare(queue='return_queue', durable=True)
    channel.queue_bind(exchange='label_tasks', queue='return_queue', routing_key='return')


    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='return_queue', on_message_callback=callback)

    print(' [*] Waiting for shipping label tasks. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == "__main__":
    main()
