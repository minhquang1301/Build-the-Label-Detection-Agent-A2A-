import os
import datetime

DAILY_FOLDER_BASE = "D:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\daily"  # Thay thế bằng đường dẫn thực tế

today = datetime.date.today()
daily_folder_name = today.strftime("%Y-%m-%d")
daily_folder_path = os.path.join(DAILY_FOLDER_BASE, daily_folder_name)

if not os.path.exists(daily_folder_path):
    try:
        os.makedirs(daily_folder_path)
        print(f"Đã tạo thư mục hàng ngày: {daily_folder_path}")
    except Exception as e:
        print(f"Lỗi khi tạo thư mục: {e}")
else:
    print(f"Thư mục hàng ngày đã tồn tại: {daily_folder_path}")