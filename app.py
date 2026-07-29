import os
import json
import io
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from PIL import Image

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Tối đa 16MB

WORKER_UPLOAD_URL = "https://proxy-api-garena.meow-web.workers.dev/api/upload"

# Bộ lưu trữ Session & Token bóc tách từ file HAR
session_store = {
    "headers": {
        "origin": "https://aov-theme.meow-web.workers.dev",
        "referer": "https://aov-theme.meow-web.workers.dev/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "cookies": {}
}

# --- GIAO DIỆN WEB UI ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AOV Theme & Poster Studio Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-base: #07090e;
            --bg-card: #0f172a;
            --border-subtle: #1e293b;
            --neon-blue: #3b82f6;
            --neon-glow: rgba(59, 130, 246, 0.25);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }
        body { 
            background-color: var(--bg-base); 
            color: var(--text-main); 
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            padding: 30px 0;
        }
        .container-custom { max-width: 950px; width: 100%; margin: auto; }
        .glass-panel { 
            background: var(--bg-card); 
            border: 1px solid var(--border-subtle); 
            border-radius: 16px; 
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.7);
        }
        .step-badge {
            background: rgba(59, 130, 246, 0.1);
            color: var(--neon-blue);
            border: 1px solid rgba(59, 130, 246, 0.3);
            font-size: 0.75rem;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 600;
        }
        .drop-zone {
            border: 2px dashed #334155;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            background: #090d16;
            cursor: pointer;
            transition: all 0.25s ease-in-out;
        }
        .drop-zone:hover, .drop-zone.dragover {
            border-color: var(--neon-blue);
            background: #111c33;
            box-shadow: 0 0 20px var(--neon-glow);
        }
        .preview-box-wrapper {
            position: relative;
            width: 100%;
            height: 240px;
            background: #04060a;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border-subtle);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #preview-img { max-height: 100%; max-width: 100%; object-fit: contain; }
        .btn-gaming {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: white;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            padding: 12px;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        }
        .btn-gaming:hover:not(:disabled) {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            box-shadow: 0 0 20px var(--neon-glow);
            transform: translateY(-1px);
        }
        .form-control {
            background-color: #090d16;
            border-color: var(--border-subtle);
            color: #fff;
            border-radius: 10px;
            padding: 10px 14px;
        }
        .form-control:focus {
            background-color: #090d16;
            color: #fff;
            border-color: var(--neon-blue);
            box-shadow: 0 0 0 3px var(--neon-glow);
        }
        .console-terminal {
            background: #04060a;
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 15px;
            font-family: 'Fira Code', monospace;
            font-size: 0.82rem;
            max-height: 160px;
            overflow-y: auto;
            color: #38bdf8;
        }
        .modal-content {
            background-color: var(--bg-card);
            color: var(--text-main);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
        }
        .img-container {
            max-height: 400px;
            background: #04060a;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .img-container img { max-width: 100%; }
    </style>
</head>
<body>
<div class="container-custom px-3">
    <div class="text-center mb-5">
        <h1 class="fw-bold text-primary mb-2"><i class="fa-solid fa-gamepad me-2"></i>AOV POSTER STUDIO PRO</h1>
        <p class="text-muted small">Hệ thống bóc tách Session HAR & Tự động đẩy Theme/Poster lên Garena Worker API</p>
    </div>

    <div class="row g-4">
        <div class="col-lg-5">
            <div class="glass-panel p-4 h-100 d-flex flex-column justify-content-between">
                <div>
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <span class="step-badge">BƯỚC 1</span>
                        <i class="fa-solid fa-key text-warning"></i>
                    </div>
                    <h5 class="fw-bold mb-2">Nạp Session HAR</h5>
                    <p class="text-muted small mb-4">Chọn file `.har` thu thập từ F12 (Network) khi thao tác.</p>
                    
                    <div class="mb-3">
                        <input type="file" id="har-input" class="form-control mb-3" accept=".har">
                        <button class="btn btn-outline-warning w-100 py-2 fw-semibold" onclick="uploadHAR()">
                            <i class="fa-solid fa-wand-magic-sparkles me-2"></i> Phân tích & Lưu Token
                        </button>
                    </div>
                </div>

                <div class="mt-4">
                    <label class="text-muted small mb-2 fw-semibold"><i class="fa-solid fa-terminal me-1"></i> Trạng thái Session:</label>
                    <div id="har-status" class="p-3 rounded bg-black text-muted small border border-secondary border-opacity-25 text-center">
                        Chưa có file HAR nào được nạp.
                    </div>
                </div>
            </div>
        </div>

        <div class="col-lg-7">
            <div class="glass-panel p-4">
                <div class="d-flex align-items-center justify-content-between mb-3">
                    <span class="step-badge">BƯỚC 2</span>
                    <i class="fa-solid fa-cloud-arrow-up text-success"></i>
                </div>
                <h5 class="fw-bold mb-2">Đẩy Ảnh Lên Server</h5>
                <p class="text-muted small mb-4">Chọn ảnh, cắt chỉnh tỷ lệ và gửi đi.</p>

                <div id="upload-area">
                    <div class="drop-zone" id="drop-zone" onclick="document.getElementById('image-input').click()">
                        <i class="fa-solid fa-image fa-3xl text-primary mb-3" style="font-size: 2.5rem;"></i>
                        <p class="mb-1 fw-semibold">Kéo thả ảnh vào đây hoặc bấm để chọn</p>
                        <span class="text-muted small">Hỗ trợ PNG, JPG, WEBP</span>
                        <input type="file" id="image-input" hidden accept="image/*" onchange="initCropperModal(this.files[0])">
                    </div>
                </div>

                <div id="preview-box" class="d-none">
                    <div class="preview-box-wrapper mb-3">
                        <img id="preview-img" alt="Preview">
                        <button class="position-absolute top-0 end-0 m-2 btn btn-dark btn-sm rounded-circle shadow border border-secondary" onclick="resetImage()" title="Chọn ảnh khác">
                            <i class="fa-solid fa-xmark"></i>
                        </button>
                    </div>
                    <button class="btn btn-outline-info btn-sm w-100 mb-2" onclick="reopenCropper()">
                        <i class="fa-solid fa-crop me-1"></i> Cắt lại ảnh / Chỉnh sửa khung hình
                    </button>
                </div>

                <button id="upload-btn" class="btn btn-gaming w-100 mt-2" onclick="uploadImage()" disabled>
                    <i class="fa-solid fa-rocket me-2"></i> Gửi Request Lên Server Garena
                </button>

                <div class="mt-4">
                    <label class="text-muted small mb-2 fw-semibold"><i class="fa-solid fa-code me-1"></i> Console Log / Phản hồi Server:</label>
                    <div id="console-output" class="console-terminal">Chờ thực thi lệnh...</div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="cropModal" tabindex="-1" data-bs-backdrop="static" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered modal-lg">
        <div class="modal-content p-3">
            <div class="modal-header border-bottom border-secondary border-opacity-25">
                <h5 class="modal-title fw-bold text-primary"><i class="fa-solid fa-crop me-2"></i>Cắt & Tùy Chỉnh Khung Hình Poster</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="img-container">
                    <img id="image-to-crop" src="" alt="Source">
                </div>
            </div>
            <div class="modal-footer border-top border-secondary border-opacity-25 d-flex justify-content-between">
                <div>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="cropper.rotate(90)"><i class="fa-solid fa-rotate-right"></i> Xoay 90°</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="cropper.reset()"><i class="fa-solid fa-rotate-left"></i> Đặt lại</button>
                </div>
                <div>
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Hủy</button>
                    <button type="button" class="btn btn-gaming btn-sm px-4" onclick="saveCroppedImage()">Xác nhận cắt ảnh</button>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.5.13/cropper.min.js"></script>
<script>
    let selectedFile = null;
    let cropper = null;
    let originalRawFile = null;

    function initCropperModal(file) {
        if (!file) return;
        originalRawFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            const imageEl = document.getElementById('image-to-crop');
            imageEl.src = e.target.result;
            const cropModal = new bootstrap.Modal(document.getElementById('cropModal'));
            cropModal.show();
            setTimeout(() => {
                if (cropper) cropper.destroy();
                cropper = new Cropper(imageEl, {
                    aspectRatio: NaN,
                    viewMode: 1,
                    autoCropArea: 0.9,
                });
            }, 200);
        };
        reader.readAsDataURL(file);
    }

    function reopenCropper() {
        if (!originalRawFile) return;
        initCropperModal(originalRawFile);
    }

    function saveCroppedImage() {
        if (!cropper) return;
        cropper.getCroppedCanvas({ maxWidth: 2048, maxHeight: 2048 }).toBlob((blob) => {
            selectedFile = new File([blob], originalRawFile.name || "poster.jpg", { type: "image/jpeg" });
            document.getElementById('preview-img').src = URL.createObjectURL(blob);
            document.getElementById('upload-area').classList.add('d-none');
            document.getElementById('preview-box').classList.remove('d-none');
            document.getElementById('upload-btn').disabled = false;
            const modalEl = document.getElementById('cropModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            modal.hide();
        }, 'image/jpeg', 0.9);
    }

    function resetImage() {
        selectedFile = null;
        originalRawFile = null;
        if (cropper) { cropper.destroy(); cropper = null; }
        document.getElementById('image-input').value = '';
        document.getElementById('upload-area').classList.remove('d-none');
        document.getElementById('preview-box').classList.add('d-none');
        document.getElementById('upload-btn').disabled = true;
    }

    const dropZone = document.getElementById('drop-zone');
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
    dropZone.ondragleave = () => { dropZone.classList.remove('dragover'); };
    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) initCropperModal(e.dataTransfer.files[0]);
    };

    async function uploadHAR() {
        const fileInput = document.getElementById('har-input');
        if (!fileInput.files.length) return alert('Vui lòng chọn file .har trước!');
        
        const statusBox = document.getElementById('har-status');
        statusBox.className = "p-3 rounded bg-black text-warning small border border-warning border-opacity-25 text-center";
        statusBox.innerText = "Đang trích xuất dữ liệu từ file HAR...";

        const formData = new FormData();
        formData.append('har_file', fileInput.files[0]);

        try {
            const res = await fetch('/api/parse-har', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                statusBox.className = "p-3 rounded bg-black text-success small border border-success border-opacity-25 text-center fw-semibold";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> ${data.message}`;
            } else {
                throw new Error(data.message);
            }
        } catch (err) {
            statusBox.className = "p-3 rounded bg-black text-danger small border border-danger border-opacity-25 text-center";
            statusBox.innerText = "Lỗi: " + err.message;
        }
    }

    async function uploadImage() {
        if (!selectedFile) return;
        
        const btn = document.getElementById('upload-btn');
        const consoleBox = document.getElementById('console-output');
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Đang xử lý & đẩy dữ liệu...`;
        consoleBox.innerText = "Đang truyền tải request tới Worker API...";

        const formData = new FormData();
        formData.append('image', selectedFile);

        try {
            const res = await fetch('/api/upload-image', { method: 'POST', body: formData });
            const data = await res.json();
            
            consoleBox.innerText = JSON.stringify(data, null, 2);
            if (data.success) {
                consoleBox.style.color = "#4ade80";
            } else {
                consoleBox.style.color = "#f87171";
            }
        } catch (err) {
            consoleBox.style.color = "#f87171";
            consoleBox.innerText = "Lỗi kết nối Server Python: " + err.message;
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-rocket me-2"></i> Gửi Request Lên Server Garena`;
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
            for h in req.get('headers', []):
                name = h.get('name', '').lower()
                if name in ['authorization', 'cookie', 'x-csrf-token', 'user-agent', 'origin', 'referer']:
                    session_store["headers"][name] = h.get('value')
            for c in req.get('cookies', []):
                session_store["cookies"][c.get('name')] = c.get('value')
            extracted_count += 1
                
        return jsonify({
            "success": True, 
            "message": f"Đã quét và nạp toàn bộ Session từ {extracted_count} request trong HAR!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi đọc file HAR: {str(e)}"}), 500

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

        # Gửi đồng thời các biến form key 'file', 'image' và 'link' để Worker chắc chắn bắt được dữ liệu
        files = {
            'file': ('poster.jpg', img_io, 'image/jpeg'),
            'image': ('poster.jpg', img_io, 'image/jpeg'),
            'link': (None, '')
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