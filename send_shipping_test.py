import pika # type: ignore
import json

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='label_tasks', exchange_type='direct', durable=True)

message = {
    "file_path": r"D:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\somsn3cwjv4r8_shippinglabel_1733940323.pdf"
}

channel.basic_publish(
    exchange='label_tasks',
    routing_key='shipping',
    body=json.dumps(message)
)

print("✅ Task sent.")
connection.close()