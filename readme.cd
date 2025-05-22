--- /dev/null
+++ b/d:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\A2A\README.md
@@ -0,0 +1,154 @@
+# A2A Label Detection and Data Extraction System
+
+This project automates the detection of PDF label files (shipping, product, return), queues them for processing using RabbitMQ, and extracts relevant data using Google Gemini AI.
+
+## Features
+
+*   **Automatic Label Detection**: Monitors a specified daily folder for new PDF files.
+*   **Label Categorization**: Identifies label types (shipping, return, etc.) based on filename patterns.
+*   **Message Queuing**: Uses RabbitMQ to manage tasks for different label processors.
+*   **AI-Powered Data Extraction**: Leverges Google Gemini to extract structured data from PDF content.
+*   **OCR Fallback**: For shipping labels (and return labels with suggested updates), if direct text extraction fails, OCR is used as a fallback.
+
+## Project Structure
+
+```
+A2A/
+├── label_detector.py       # Detects new PDF files and publishes tasks to RabbitMQ
+├── shipping_processornew.py # Processes shipping labels
+├── return_processor.py     # Processes return labels
+├── createdaily.py          # Utility to create the daily folder
+├── .env.example            # Example environment variables file
+└── requirements.txt        # Python dependencies
+```
+
+## Prerequisites
+
+*   **Python 3.8+**
+*   **RabbitMQ Server**: Installed and running.
+*   **Tesseract OCR**: Installed and configured (including adding to PATH or specifying `TESSERACT_CMD_PATH`).
+    *   Download: Tesseract at UB Mannheim
+*   **Poppler**: Required by `pdf2image` for PDF to image conversion (for OCR).
+    *   Download: Poppler Windows builds or via your system's package manager (e.g., `brew install poppler` on macOS, `sudo apt-get install poppler-utils` on Debian/Ubuntu).
+    *   Ensure the `bin/` directory of Poppler is added to your system's PATH or specify `POPPLER_PATH`.
+*   **Ghostscript**: Required by `pdf2image` in some cases, especially on Windows.
+    *   Download: Ghostscript
+    *   Ensure the `bin/` directory of Ghostscript is added to your system's PATH or specify `GHOSTSCRIPT_PATH`.
+*   **Google Gemini API Key**: Obtain an API key from Google AI Studio.
+
+## Installation
+
+1.  **Clone the repository (if applicable) or download the files into a directory (e.g., `A2A`).**
+2.  **Navigate to the project directory:**
+    ```bash
+    cd path/to/A2A
+    ```
+3.  **Create a virtual environment (recommended):**
+    ```bash
+    python -m venv venv
+    source venv/bin/activate  # On Windows: venv\Scripts\activate
+    ```
+4.  **Install dependencies:**
+    Create a `requirements.txt` file (see content below) in the `A2A` directory and run:
+    ```bash
+    pip install -r requirements.txt
+    ```
+
+## Configuration
+
+1.  **Create a `.env` file** in the `A2A` directory by copying `.env.example` (see content below):
+    ```bash
+    cp .env.example .env
+    ```
+2.  **Edit the `.env` file** with your specific configurations:
+    ```dotenv
+    # --- General ---
+    MESSAGE_QUEUE_HOST="localhost"
+
+    # --- Gemini AI ---
+    GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE" # Replace with your actual API key
+    GEMINI_MODEL_NAME="gemini-1.5-flash-latest"
+
+    # --- File Paths ---
+    # Base directory for daily folders (label_detector.py, createdaily.py)
+    DAILY_FOLDER_BASE="D:\\Desktop\\Thực tập\\A2A và MCP\\Build the Label Detection Agent (A2A)\\daily" # Use double backslashes or forward slashes
+
+    # --- OCR and PDF Tools Paths (shipping_processornew.py, return_processor.py) ---
+    # Full path to tesseract.exe (e.g., "C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
+    TESSERACT_CMD_PATH="D:\\Tesseract-OCR\\tesseract.exe"
+    # Full path to gswin64c.exe (Ghostscript) (e.g., "C:\\Program Files\\gs\\gs10.0X.X\\bin\\gswin64c.exe")
+    GHOSTSCRIPT_PATH="D:\\gs\\gs10.02.1\\bin\\gswin64c.exe"
+    # Full path to Poppler's bin directory (e.g., "C:\\path\\to\\poppler-XX.YY.Z\\Library\\bin")
+    POPPLER_PATH="D:\\Release-24.08.0-0\\poppler-24.08.0\\Library\\bin"
+    ```
+    **Important:**
+    *   Replace placeholder values with your actual API key and paths.
+    *   Ensure paths are correct for your system. Use double backslashes (`\\`) or forward slashes (`/`) for paths in the `.env` file.
+
+## Running the Application
+
+1.  **Ensure RabbitMQ server is running.**
+
+2.  **Create the daily folder (if it doesn't exist):**
+    Run this script once daily or ensure it's run by a scheduler.
+    ```bash
+    python createdaily.py
+    ```
+
+3.  **Start the Label Detector (in a separate terminal/process):**
+    This script monitors the daily folder for new PDFs.
+    ```bash
+    python label_detector.py
+    ```
+
+4.  **Start the Label Processors (each in a separate terminal/process):**
+    *   **Shipping Label Processor:**
+        ```bash
+        python shipping_processornew.py
+        ```
+    *   **Return Label Processor:**
+        ```bash
+        python return_processor.py
+        ```
+
+5.  **Using `startA2A.bat` (Example for Windows):**
+    You can create a batch file (e.g., `startA2A.bat`) in the `A2A` directory to simplify starting all components.
+    ```batch
+    @echo off
+    echo Starting A2A Label Detection System...
+
+    REM Ensure your virtual environment is activated if you run this script directly
+    REM Or, specify the full path to the python executable in your venv
+    REM Example: SET PYTHON_EXE=D:\path\to\A2A\venv\Scripts\python.exe
+    REM %PYTHON_EXE% createdaily.py
+
+    echo Starting Daily Folder Creator (if needed, can be run once)...
+    REM python createdaily.py
+
+    echo Starting Label Detector...
+    start "Label Detector" cmd /k python label_detector.py
+
+    echo Starting Shipping Processor...
+    start "Shipping Processor" cmd /k python shipping_processornew.py
+
+    echo Starting Return Processor...
+    start "Return Processor" cmd /k python return_processor.py
+
+    echo All components started.
+    ```
+    *Note: The `cmd /k` option keeps the command prompt window open after the script finishes, which is useful for seeing logs. Use `cmd /c` if you want it to close.*
+
+## How It Works
+
+1.  `createdaily.py` ensures the target folder for the current day exists.
+2.  `label_detector.py` scans the daily folder for new PDF files.
+3.  If a new PDF is found, its filename is checked against predefined patterns in `LABEL_PATTERNS` to determine the label type (e.g., "shipping", "return").
+4.  A message containing the file path and label type is published to the `label_tasks` exchange in RabbitMQ with a routing key corresponding to the label type.
+5.  `shipping_processornew.py` listens to the `shipping_queue` (bound with routing_key 'shipping').
+6.  `return_processor.py` listens to the `return_queue` (bound with routing_key 'return').
+7.  When a processor receives a message:
+    a.  It attempts to extract text from the PDF using `pypdf`.
+    b.  If `pypdf` fails or returns empty text (and OCR fallback is implemented), it converts the PDF to images and uses `pytesseract` (OCR) to extract text.
+    c.  The extracted text is sent to the Google Gemini API with a specific prompt to extract structured data.
+    d.  The extracted JSON data is logged to the console. In a real application, this data would be stored in a database or used for further processing.
+
+```

Here are the new files and suggested code modifications:

**New File: `d:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\A2A\requirements.txt`**
```diff
--- /dev/null
+++ b/d:\Desktop\Thực tập\A2A và MCP\Build the Label Detection Agent (A2A)\A2A\requirements.txt
@@ -0,0 +1,8 @@
+pika
+google-generativeai
+pypdf
+pdf2image
+pytesseract
+python-dotenv
+Pillow # A dependency for pdf2image and sometimes pytesseract
