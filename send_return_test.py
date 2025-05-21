import pika # type: ignore
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='label_tasks', exchange_type='direct', durable=True)

message = {
    "file_path": r"D:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\daily\2025-05-20\....pdf"  # sửa đúng đường dẫn file PDF thật
}

channel.basic_publish(
    exchange='label_tasks',
    routing_key='return',
    body=json.dumps(message)
)

print("Sent return label task.")
connection.close()
