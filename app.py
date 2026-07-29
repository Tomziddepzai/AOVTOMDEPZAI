import os
import json
import io
import requests
from flask import Flask, request, jsonify, render_template_string
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Tối đa 16MB

WORKER_UPLOAD_URL = "https://proxy-api-garena.meow-web.workers.dev/api/upload"

session_store = {
    "headers": {
        "origin": "https://aov-theme.meow-web.workers.dev",
        "referer": "https://aov-theme.meow-web.workers.dev/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "cookies": {}
}

# --- GIAO DIỆN MỚI: XỊN SÒ, GỌN GÀNG, CHUẨN GAMING ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AOV Theme & Poster Studio</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: #131c2e;
            --border-color: #1e293b;
            --accent-color: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.3);
        }
        body { 
            background-color: var(--bg-color); 
            color: #f1f5f9; 
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .main-container { max-width: 850px; margin: auto; width: 100%; padding: 20px; }
        .glass-card { 
            background: var(--card-bg); 
            border: 1px solid var(--border-color); 
            border-radius: 16px; 
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }
        .drop-zone {
            border: 2px dashed #334155;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            background: #0f172a;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .drop-zone:hover, .drop-zone.dragover {
            border-color: var(--accent-color);
            background: #1e293b;
            box-shadow: 0 0 15px var(--accent-glow);
        }
        .preview-container {
            position: relative;
            width: 100%;
            height: 220px;
            border-radius: 10px;
            overflow: hidden;
            background: #090d16;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid var(--border-color);
        }
        #preview-img { max-height: 100%; max-width: 100%; object-fit: contain; }
        .btn-gaming {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: white;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            transition: all 0.2s;
        }
        .btn-gaming:hover {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            box-shadow: 0 0 15px var(--accent-glow);
            color: white;
        }
        .form-control, .form-control:focus {
            background-color: #090d16;
            border-color: var(--border-color);
            color: #fff;
        }
        .form-control:focus { box-shadow: 0 0 0 2px var(--accent-glow); border-color: var(--accent-color); }
        .badge-status { font-size: 0.85rem; padding: 6px 12px; border-radius: 8px; }
    </style>
</head>
<body>
<div class="main-container">
    <div class="text-center mb-4">
        <h2 class="fw-bold text-gradient text-primary"><i class="fa-solid fa-gamepad me-2"></i>AOV POSTER STUDIO</h2>
        <p class="text-muted small">Hệ thống tự động hóa quản lý & thay thế Theme/Poster Liên Quân Mobile</p>
    </div>

    <div class="row g-4">
        <!-- Cột trái: Cấu hình HAR & Trạng thái -->
        <div class="col-md-5">
            <div class="glass-card p-4 h-100 d-flex flex-column justify-content-between">
                <div>
                    <h6 class="text-warning fw-bold mb-3"><i class="fa-solid fa-key me-2"></i>1. Cấu hình Session</h6>
                    <p class="text-muted small mb-3">Tải file `.har` từ F12 (Network) để bóc tách token xác thực.</p>
                    
                    <div class="mb-3">
                        <input type="file" id="har-input" class="form-control form-control-sm mb-2" accept=".har">
                        <button class="btn btn-outline-warning btn-sm w-100 py-2 fw-semibold" onclick="uploadHAR()">
                            <i class="fa-solid fa-wand-magic-sparkles me-1"></i> Đọc Token từ HAR
                        </button>
                    </div>
                </div>
                
                <div id="har-status" class="alert alert-secondary bg-dark text-muted border-0 small mb-0 py-2 text-center">
                    Chưa nạp file HAR
                </div>
            </div>
        </div>

        <!-- Cột phải: Upload & Preview Ảnh -->
        <div class="col-md-7">
            <div class="glass-card p-4">
                <h6 class="text-success fw-bold mb-3"><i class="fa-solid fa-image me-2"></i>2. Tải ảnh & Đẩy lên Server</h6>
                
                <!-- Khu vực drop zone hoặc Preview -->
                <div id="upload-area">
                    <div class="drop-zone" id="drop-zone" onclick="document.getElementById('image-input').click()">
                        <i class="fa-solid fa-cloud-arrow-up fa-2x text-primary mb-2"></i>
                        <p class="mb-1 fw-semibold small">Kéo thả ảnh vào đây hoặc bấm để chọn</p>
                        <span class="text-muted" style="font-size: 0.75rem;">PNG, JPG, WEBP (Tự động nén tối ưu)</span>
                        <input type="file" id="image-input" hidden accept="image/*" onchange="previewFile(this.files[0])">
                    </div>
                </div>

                <div id="preview-box" class="d-none">
                    <div class="preview-container mb-3">
                        <img id="preview-img" alt="Preview">
                        <button class="position-absolute top-0 end-0 m-2 btn btn-dark btn-sm rounded-circle shadow" onclick="resetImage()" title="Chọn ảnh khác">
                            <i class="fa-solid fa-xmark"></i>
                        </button>
                    </div>
                </div>
                
                <button id="upload-btn" class="btn btn-gaming w-100 mt-3 py-2" onclick="uploadImage()" disabled>
                    <i class="fa-solid fa-rocket me-1"></i> Gửi Yêu Cầu Lên Server Garena
                </button>
                
                <div id="result-box" class="mt-3 p-3 rounded d-none small"></div>
            </div>
        </div>
    </div>
</div>

<script>
    let selectedFile = null;

    function previewFile(file) {
        if (!file) return;
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('preview-img').src = e.target.result;
            document.getElementById('upload-area').classList.add('d-none');
            document.getElementById('preview-box').classList.remove('d-none');
            document.getElementById('upload-btn').disabled = false;
        };
        reader.readAsDataURL(file);
    }

    function resetImage() {
        selectedFile = null;
        document.getElementById('image-input').value = '';
        document.getElementById('upload-area').classList.remove('d-none');
        document.getElementById('preview-box').classList.add('d-none');
        document.getElementById('upload-btn').disabled = true;
        document.getElementById('result-box').className = "mt-3 p-3 rounded d-none small";
    }

    const dropZone = document.getElementById('drop-zone');
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
    dropZone.ondragleave = () => { dropZone.classList.remove('dragover'); };
    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) previewFile(e.dataTransfer.files[0]);
    };

    async function uploadHAR() {
        const fileInput = document.getElementById('har-input');
        if (!fileInput.files.length) return alert('Vui lòng chọn file .har!');
        
        const statusBox = document.getElementById('har-status');
        statusBox.className = "alert alert-warning bg-dark text-warning border-0 small mb-0 py-2 text-center";
        statusBox.innerText = "Đang phân tích file HAR...";

        const formData = new FormData();
        formData.append('har_file', fileInput.files[0]);

        try {
            const res = await fetch('/api/parse-har', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                statusBox.className = "alert alert-success bg-dark text-success border-0 small mb-0 py-2 text-center fw-semibold";
                statusBox.innerHTML = `<i class="fa-solid fa-check-circle me-1"></i> ${data.message}`;
            } else {
                throw new Error(data.message);
            }
        } catch (err) {
            statusBox.className = "alert alert-danger bg-dark text-danger border-0 small mb-0 py-2 text-center";
            statusBox.innerText = "Lỗi: " + err.message;
        }
    }

    async function uploadImage() {
        if (!selectedFile) return;
        
        const btn = document.getElementById('upload-btn');
        const resultBox = document.getElementById('result-box');
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Đang xử lý & đẩy dữ liệu...`;
        resultBox.className = "mt-3 p-3 rounded d-none small";

        const formData = new FormData();
        formData.append('image', selectedFile);

        try {
            const res = await fetch('/api/upload-image', { method: 'POST', body: formData });
            const data = await res.json();
            
            resultBox.classList.remove('d-none');
            if (data.success) {
                resultBox.className = "mt-3 p-3 rounded bg-success text-white bg-opacity-10 border border-success";
                resultBox.innerHTML = `<strong><i class="fa-solid fa-circle-check text-success me-1"></i> Thành công!</strong><br><pre class="mb-0 text-light mt-1" style="max-height: 100px; overflow-y: auto;">${JSON.stringify(data.data, null, 2)}</pre>`;
            } else {
                resultBox.className = "mt-3 p-3 rounded bg-danger text-white bg-opacity-10 border border-danger";
                resultBox.innerHTML = `<strong><i class="fa-solid fa-circle-xmark text-danger me-1"></i> Thất bại:</strong> ${JSON.stringify(data.data || data.error)}`;
            }
        } catch (err) {
            resultBox.classList.remove('d-none');
            resultBox.className = "mt-3 p-3 rounded bg-danger text-white bg-opacity-10 border border-danger";
            resultBox.innerHTML = `<strong>Lỗi kết nối:</strong> ${err.message}`;
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-rocket me-1"></i> Gửi Yêu Cầu Lên Server Garena`;
        }
    }
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_LAYOUT)

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
                for h in req.get('headers', []):
                    name = h.get('name', '').lower()
                    if name in ['authorization', 'user-agent', 'origin', 'referer']:
                        session_store["headers"][name] = h.get('value')
                for c in req.get('cookies', []):
                    session_store["cookies"][c.get('name')] = c.get('value')
                extracted_count += 1
                
        return jsonify({
            "success": True, 
            "message": f"Đã nhận diện {extracted_count} request xác thực từ HAR!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi đọc file: {str(e)}"}), 500

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "Chưa chọn file ảnh"}), 400

    image_file = request.files['image']

    try:
        img = Image.open(image_file.stream)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG', quality=85)
        img_io.seek(0)

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