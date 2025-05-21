import os
import datetime
import time
import pika # type: ignore
import json

# --- Configuration ---
DAILY_FOLDER_BASE = r"D:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\daily"  # Replace with your actual path
LABEL_PATTERNS = {
    "shipping": "shippinglabel",
    "product": "productinfo",
    "return": "returnlabel"
    # Add more label types and their identifying patterns
}
MESSAGE_QUEUE_HOST = "localhost"

def get_daily_folder_path():
    today = datetime.date.today()
    return os.path.join(DAILY_FOLDER_BASE, today.strftime("%Y-%m-%d"))

def identify_label_type(filename):
    for label_type, pattern in LABEL_PATTERNS.items():
        if pattern.lower() in filename.lower():
            return label_type
    return None

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(MESSAGE_QUEUE_HOST))
    channel = connection.channel()
    channel.exchange_declare(exchange='label_tasks', exchange_type='direct', durable=True) # Make exchange durable

    processed_files = set()

    while True:
        daily_folder = get_daily_folder_path()
        if os.path.exists(daily_folder):
            for filename in os.listdir(daily_folder):
                if filename.lower().endswith(".pdf"):
                    filepath = os.path.join(daily_folder, filename)
                    if filepath not in processed_files:
                        label_type = identify_label_type(filename)
                        if label_type:
                            message = {"file_path": filepath, "label_type": label_type}
                            channel.basic_publish(exchange='label_tasks',
                                                  routing_key=label_type,
                                                  body=json.dumps(message),
                                                  properties=pika.BasicProperties(
                                                      delivery_mode=2,  # Make messages persistent
                                                  ))
                            print(f"Published task for {filepath} as type: {label_type}")
                            processed_files.add(filepath)
                        else:
                            print(f"Could not identify label type for: {filepath}")
            time.sleep(60)
        else:
            print(f"Daily folder not found: {daily_folder}")
            time.sleep(3600)

    connection.close()

if __name__ == "__main__":
    main()