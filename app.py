from flask import Flask, render_template_string, request, send_file, url_for
import os
import zipfile
import qrcode
from fpdf import FPDF
import img2pdf
from PIL import Image
import tempfile
import magic  # To detect file type
import socket  # To get the local IP address
import traceback
import logging

# Initialize Flask app
app = Flask(__name__)

# Define upload, QR code, and ZIP folders
UPLOAD_FOLDER = "uploads"
QR_FOLDER = "qrcodes"
ZIP_FOLDER = "zips"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Get the local IP address of the machine
def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Create a temporary socket to find the IP address
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Connect to a public DNS server
            return s.getsockname()[0]
    except Exception as e:
        logging.error(f"Error getting local IP: {e}")
        return "127.0.0.1"  # Fallback to localhost


LOCAL_IP = get_local_ip()
FLASK_PORT = 5000  # Default Flask port


# Embedded HTML Templates with CSS and JavaScript
INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Converter</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #121212;
            color: #e0e0e0;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .container {
            background: #1e1e1e;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #bb86fc;
            font-size: 1.8rem;
            margin-bottom: 1.5rem;
        }
        .upload-area {
            border: 2px dashed #444;
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 1rem;
            cursor: pointer;
            transition: border-color 0.3s ease, transform 0.3s ease;
        }
        .upload-area:hover {
            border-color: #bb86fc;
            transform: scale(1.02);
        }
        .upload-area.dragover {
            border-color: #bb86fc;
            background-color: #333;
        }
        input[type="file"] {
            display: none;
        }
        button {
            padding: 0.75rem 1.5rem;
            background-color: #bb86fc;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: background-color 0.3s ease;
        }
        button:hover {
            background-color: #9c27b0;
        }
        .error {
            color: red;
            margin-top: 1rem;
        }
        .loading {
            margin-top: 1rem;
            color: #bb86fc;
            font-size: 0.9rem;
        }
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const uploadArea = document.querySelector('.upload-area');
            const fileInput = document.querySelector('input[type="file"]');
            const loading = document.getElementById('loading');

            // Open file dialog when upload area is clicked
            uploadArea.addEventListener('click', () => {
                fileInput.click();
            });

            // Handle file selection (both from input and drag-and-drop)
            const handleFile = (file) => {
                if (file) {
                    const formData = new FormData();
                    formData.append('file', file);

                    // Show loading message
                    loading.style.display = 'block';

                    // Submit form programmatically
                    fetch('/', {
                        method: 'POST',
                        body: formData,
                    })
                    .then(response => response.text())
                    .then(html => {
                        document.body.innerHTML = html; // Update the page with the result
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('An error occurred while uploading the file.');
                    });
                }
            };

            // File input change event
            fileInput.addEventListener('change', () => {
                const file = fileInput.files[0];
                handleFile(file);
            });

            // Drag-and-drop functionality
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const file = e.dataTransfer.files[0];
                handleFile(file);
            });
        });
    </script>
</head>
<body>
    <div class="container">
        <h1>Upload and Convert</h1>
        <div class="upload-area">
            <p>Drag & Drop or Click to Upload</p>
            <input type="file" name="file" id="file" required>
        </div>
        <div id="loading" class="loading" style="display: none;">Processing your file...</div>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
    </div>
</body>
</html>
"""

RESULT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Processing Complete</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #121212;
            color: #e0e0e0;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .container {
            background: #1e1e1e;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 400px;
            width: 100%;
        }
        h1 {
            color: #bb86fc;
            font-size: 1.8rem;
            margin-bottom: 1.5rem;
        }
        p {
            color: #ccc;
            margin-bottom: 1.5rem;
        }
        img {
            margin-top: 1rem;
            display: block;
            border: 2px solid #444;
            border-radius: 8px;
            transition: transform 0.3s ease;
        }
        img:hover {
            transform: scale(1.05);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Processing Complete</h1>
        <p>Scan the QR code below to download the file:</p>
        <img src="{{ qr_code_url }}" alt="QR Code" width="200" height="200">
    </div>
</body>
</html>
"""


def convert_to_pdf(input_file):
    """Converts the input file to PDF if it's not already a PDF."""
    mime = magic.Magic(mime=True)
    file_type = mime.from_file(input_file)

    # Check if the file is already a PDF
    if file_type == "application/pdf":
        return input_file  # Return the original file path if it's already a PDF

    pdf_path = os.path.splitext(input_file)[0] + ".pdf"

    if file_type.startswith("image"):
        # Convert image to PDF
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(input_file))
    elif file_type.startswith("text"):
        # Convert text file to PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        with open(input_file, 'r') as file:
            for line in file:
                pdf.cell(200, 10, txt=line, ln=1)

        pdf.output(pdf_path)
    else:
        raise ValueError(f"Unsupported file format: {file_type}. Only images and text files can be converted to PDF.")

    return pdf_path


def compress_file(file_to_compress):
    """Compresses the given file into a .zip archive."""
    zip_path = os.path.join(ZIP_FOLDER, os.path.basename(os.path.splitext(file_to_compress)[0]) + ".zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(file_to_compress, os.path.basename(file_to_compress))
    return zip_path


def generate_qr_code(file_url, qr_code_path):
    """Generates a QR code linking to the given file URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(file_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="white", back_color="black").resize((200, 200))
    img.save(qr_code_path)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Step 1: Handle file upload
        uploaded_file = request.files["file"]
        if not uploaded_file:
            return render_template_string(INDEX_HTML, error="No file uploaded.")

        # Validate file size (limit to 10MB)
        if len(uploaded_file.read()) > 10 * 1024 * 1024:  # 10MB
            return render_template_string(INDEX_HTML, error="File too large. Maximum size is 10MB.")
        uploaded_file.seek(0)  # Reset file pointer after reading

        # Create temporary directories
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            uploaded_file.save(file_path)

            try:
                # Step 2: Convert the file to PDF (if not already a PDF)
                pdf_file = convert_to_pdf(file_path)

                # Step 3: Compress the PDF into a .zip file
                zip_file = compress_file(pdf_file)

                # Step 4: Generate a QR code for the local file URL
                file_url = f"http://{LOCAL_IP}:{FLASK_PORT}/zip/{os.path.basename(zip_file)}"
                qr_code_path = os.path.join(QR_FOLDER, os.path.splitext(uploaded_file.filename)[0] + "_qr.png")
                generate_qr_code(file_url, qr_code_path)

                # Step 5: Serve the result page with the QR code embedded
                return render_template_string(RESULT_HTML, qr_code_url=url_for("serve_qr", filename=os.path.basename(qr_code_path)))

            except Exception as e:
                logging.error(f"Error processing file: {e}")
                traceback.print_exc()
                return render_template_string(INDEX_HTML, error=f"An error occurred: {e}")

    return render_template_string(INDEX_HTML, error=None)


@app.route("/qr/<filename>")
def serve_qr(filename):
    """Serve the QR code image."""
    qr_path = os.path.join(QR_FOLDER, filename)
    if not os.path.exists(qr_path):
        return "QR code not found.", 404
    return send_file(qr_path, mimetype='image/png')


@app.route("/zip/<filename>")
def serve_zip(filename):
    """Serve the compressed .zip file."""
    zip_path = os.path.join(ZIP_FOLDER, filename)
    if not os.path.exists(zip_path):
        return "Zip file not found.", 404
    return send_file(zip_path, as_attachment=True)


if __name__ == "__main__":
    logging.info(f"Running on http://{LOCAL_IP}:{FLASK_PORT}")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)