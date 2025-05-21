import pika # type: ignore
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

message = {
    "file_path": r"D:\your_path\product_label.pdf"
}

channel.basic_publish(
    exchange='label_tasks',
    routing_key='product',
    body=json.dumps(message)
)

print("✅ Task sent.")
connection.close()