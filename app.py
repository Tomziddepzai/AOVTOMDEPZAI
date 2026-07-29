import os
import json
import io
import requests
from flask import Flask, request, jsonify, render_template_string
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Tối đa 16MB

# Config mặc định cho Proxy API
WORKER_UPLOAD_URL = "https://proxy-api-garena.meow-web.workers.dev/api/upload"

# Lưu trữ cấu hình Auth trích xuất từ HAR
session_store = {
    "headers": {
        "origin": "https://aov-theme.meow-web.workers.dev",
        "referer": "https://aov-theme.meow-web.workers.dev/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "cookies": {}
}

# --- GIAO DIỆN WEB UI EMBEDDED ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AOV Theme & Poster Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
        .card { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .drop-zone {
            border: 2px dashed #3b82f6;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            background-color: #1e293b;
            cursor: pointer;
            transition: 0.2s;
        }
        .drop-zone:hover { background-color: #334155; }
        #preview-img { max-width: 100%; max-height: 300px; border-radius: 8px; display: none; margin: 15px auto; }
        .btn-custom { background-color: #2563eb; color: white; font-weight: 600; border: none; }
        .btn-custom:hover { background-color: #1d4ed8; }
    </style>
</head>
<body class="py-5">
<div class="container" style="max-width: 700px;">
    <h2 class="text-center mb-4 text-primary fw-bold">AOV Poster / Theme Automation</h2>
    
    <!-- Bước 1: Parse HAR File -->
    <div class="card p-4 mb-4 shadow">
        <h5 class="card-title text-warning mb-3">1. Cấu hình Session (Tải file HAR)</h5>
        <div class="input-group">
            <input type="file" id="har-input" class="form-control" accept=".har">
            <button class="btn btn-outline-warning" onclick="uploadHAR()">Đọc Token từ HAR</button>
        </div>
        <small id="har-status" class="form-text text-muted mt-2">Nạp file HAR lấy từ F12 Network để tự động cập nhật Header/Cookie.</small>
    </div>

    <!-- Bước 2: Upload ảnh -->
    <div class="card p-4 shadow">
        <h5 class="card-title text-success mb-3">2. Tải ảnh & Đẩy lên Server Garena</h5>
        <div class="drop-zone" id="drop-zone" onclick="document.getElementById('image-input').click()">
            <p class="mb-1 fw-bold">Kéo thả ảnh vào đây hoặc nhấp để chọn</p>
            <span class="text-muted small">Hỗ trợ PNG, JPG, WEBP (Tự động nén & tối ưu)</span>
            <input type="file" id="image-input" hidden accept="image/*" onchange="previewFile(this.files[0])">
        </div>
        <img id="preview-img" alt="Preview Image">
        
        <button id="upload-btn" class="btn btn-custom w-100 mt-3 py-2" onclick="uploadImage()" disabled>Tải ảnh lên Server</button>
        
        <div id="result-box" class="mt-3 p-3 rounded d-none"></div>
    </div>
</div>

<script>
    let selectedFile = null;

    // Xem trước ảnh
    function previewFile(file) {
        if (!file) return;
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = document.getElementById('preview-img');
            img.src = e.target.result;
            img.style.display = 'block';
            document.getElementById('upload-btn').disabled = false;
        };
        reader.readAsDataURL(file);
    }

    // Drag and Drop
    const dropZone = document.getElementById('drop-zone');
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.style.backgroundColor = '#334155'; };
    dropZone.ondragleave = () => { dropZone.style.backgroundColor = '#1e293b'; };
    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.style.backgroundColor = '#1e293b';
        if (e.dataTransfer.files.length) previewFile(e.dataTransfer.files[0]);
    };

    // Upload HAR
    async function uploadHAR() {
        const fileInput = document.getElementById('har-input');
        if (!fileInput.files.length) return alert('Vui lòng chọn file .har!');
        
        const formData = new FormData();
        formData.append('har_file', fileInput.files[0]);

        const res = await fetch('/api/parse-har', { method: 'POST', body: formData });
        const data = await res.json();
        document.getElementById('har-status').innerText = data.message;
        document.getElementById('har-status').className = data.success ? "form-text text-success mt-2" : "form-text text-danger mt-2";
    }

    // Upload Image
    async function uploadImage() {
        if (!selectedFile) return;
        
        const btn = document.getElementById('upload-btn');
        const resultBox = document.getElementById('result-box');
        btn.disabled = true;
        btn.innerText = "Đang xử lý & Upload...";
        resultBox.className = "mt-3 p-3 rounded d-none";

        const formData = new FormData();
        formData.append('image', selectedFile);

        try {
            const res = await fetch('/api/upload-image', { method: 'POST', body: formData });
            const data = await res.json();
            
            resultBox.classList.remove('d-none');
            if (data.success) {
                resultBox.className = "mt-3 p-3 rounded alert-success bg-success text-white";
                resultBox.innerHTML = `<strong>Thành công!</strong><br>Response Server: <pre class="mb-0 text-white">${JSON.stringify(data.data, null, 2)}</pre>`;
            } else {
                resultBox.className = "mt-3 p-3 rounded alert-danger bg-danger text-white";
                resultBox.innerHTML = `<strong>Lỗi:</strong> ${data.error}`;
            }
        } catch (err) {
            resultBox.classList.remove('d-none');
            resultBox.className = "mt-3 p-3 rounded alert-danger bg-danger text-white";
            resultBox.innerHTML = `<strong>Lỗi kết nối:</strong> ${err.message}`;
        } finally {
            btn.disabled = false;
            btn.innerText = "Tải ảnh lên Server";
        }
    }
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

# 1. API bóc tách File HAR
@app.route('/api/parse-har', methods=['POST'])
def parse_har():
    if 'har_file' not in request.files:
        return jsonify({"success": False, "message": "Không tìm thấy file HAR"}), 400
    
    file = request.files['har_file']
    try:
        har_data = json.load(file)
        entries = har_data.get('log', {}).get('entries', [])
        
        extracted_count = 0
        for entry in entries:
            req = entry.get('request', {})
            url = req.get('url', '')
            if 'garena' in url or 'upload' in url:
                # Trích xuất Headers
                for h in req.get('headers', []):
                    name = h.get('name', '').lower()
                    if name in ['authorization', 'user-agent', 'origin', 'referer']:
                        session_store["headers"][name] = h.get('value')
                
                # Trích xuất Cookies
                for c in req.get('cookies', []):
                    session_store["cookies"][c.get('name')] = c.get('value')
                
                extracted_count += 1
                
        return jsonify({
            "success": True, 
            "message": f"Đã trích xuất thành công {extracted_count} request liên quan từ HAR!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi đọc file HAR: {str(e)}"}), 500

# 2. API Xử lý nén ảnh & Upload sang Server Garena
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "Chưa chọn file ảnh"}), 400

    image_file = request.files['image']

    try:
        # Nén/Chuyển đổi định dạng ảnh bằng Pillow trước khi upload
        img = Image.open(image_file.stream)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG', quality=85)
        img_io.seek(0)

        # Chuẩn bị payload multipart/form-data đẩy sang Cloudflare Worker / Garena API
        files = {
            'image': ('poster.jpg', img_io, 'image/jpeg')
        }

        response = requests.post(
            WORKER_UPLOAD_URL,
            headers=session_store["headers"],
            cookies=session_store["cookies"],
            files=files,
            timeout=30
        )

        try:
            res_data = response.json()
        except:
            res_data = response.text

        return jsonify({
            "success": response.ok,
            "status_code": response.status_code,
            "data": res_data
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    print(">>> App đang chạy tại: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)