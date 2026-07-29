import os
import json
import uuid
import threading
import io
import requests
from urllib.parse import parse_qs, urlparse
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
JOBS = {}

def extract_garena_params(har_data):
    """Bóc tách các Token cốt lõi từ File HAR"""
    params = {
        'openid': '',
        'access_token': '',
        'role_id': '',
        'area_id': '',
        'upload_url': '',
        'bind_url': '',
        'headers': {}
    }
    
    entries = har_data.get('log', {}).get('entries', [])
    for entry in entries:
        req = entry.get('request', {})
        url = req.get('url', '')
        
        # Parse tham số trên URL nếu có
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        if 'openid' in query_params:
            params['openid'] = query_params['openid'][0]
        if 'access_token' in query_params or 'token' in query_params:
            params['access_token'] = query_params.get('access_token', query_params.get('token', ['']))[0]
        if 'role_id' in query_params:
            params['role_id'] = query_params['role_id'][0]
            
        # Tìm URL Upload và URL Save/Bind Poster
        if 'upload' in url.lower() and req.get('method') == 'POST':
            params['upload_url'] = url
            for h in req.get('headers', []):
                if h['name'].lower() not in ['content-length', 'host']:
                    params['headers'][h['name']] = h['value']
                    
        elif any(k in url.lower() for k in ['save', 'set', 'bind', 'confirm', 'poster']) and req.get('method') == 'POST':
            params['bind_url'] = url

    return params

def extract_garena_params(har_data):
    """Bóc tách Token & URL từ File HAR một cách linh hoạt"""
    entries = har_data.get('log', {}).get('entries', [])
    
    post_requests = []
    
    for entry in entries:
        req = entry.get('request', {})
        method = req.get('method', '')
        url = req.get('url', '')
        
        # Bỏ qua các URL rác (Analytics, Ads...)
        if any(ignore in url.lower() for ignore in ['facebook', 'google', 'doubleclick', 'analytics', 'gtag']):
            continue
            
        if method in ['POST', 'PUT']:
            headers = {}
            for h in req.get('headers', []):
                if h['name'].lower() not in ['content-length', 'host']:
                    headers[h['name']] = h['value']
            
            post_requests.append({
                'url': url,
                'headers': headers,
                'body': req.get('postData', {}).get('text', '')
            })

    return post_requests

def process_full_garena_flow(job_id, har_stream, image_bytes):
    try:
        JOBS[job_id] = {'status': 'pending', 'message': '1/3 - Đang đọc file HAR...'}
        
        har_data = json.load(har_stream)
        post_requests = extract_garena_params(har_data)

        # Nếu không có request POST nào trong file HAR
        if not post_requests:
            JOBS[job_id] = {
                'status': 'error', 
                'message': 'File HAR không chứa bất kỳ lệnh POST/Upload nào! Bạn nhớ bấm nút "LƯU/XÁC NHẬN" trong game lúc bắt gói tin nhé.'
            }
            return

        # Tự động chọn Request POST liên quan đến Garena / Moba / Tencent
        target_req = None
        for req in post_requests:
            url_lower = req['url'].lower()
            if any(k in url_lower for k in ['garena', 'moba', 'aov', 'qq.com', 'myqcloud', 'cdngarena', 'kgvn']):
                target_req = req
                break
        
        # Nếu vẫn không lọc được, lấy luôn Request POST đầu tiên
        if not target_req and len(post_requests) > 0:
            target_req = post_requests[0]

        upload_url = target_req['url']
        headers = target_req['headers']

        JOBS[job_id] = {'status': 'pending', 'message': f'2/3 - Đang đẩy ảnh lên API: {upload_url[:40]}...'}

        # Gửi ảnh lên URL tìm được
        files = {'file': ('poster.png', image_bytes, 'image/png')}
        upload_res = requests.post(upload_url, headers=headers, files=files, timeout=20)

        if upload_res.status_code in [200, 201]:
            JOBS[job_id] = {
                'status': 'success', 
                'poster_id': job_id[:8].upper(), 
                'message': 'Đã gửi lệnh Upload thành công! Hãy vào Game kiểm tra.'
            }
        else:
            JOBS[job_id] = {
                'status': 'error', 
                'message': f'Garena từ chối (Mã {upload_res.status_code}). URL đã thử: {upload_url}'
            }

    except Exception as e:
        JOBS[job_id] = {'status': 'error', 'message': f'Lỗi đọc file HAR: {str(e)}'}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def api_upload():
    image_file = request.files.get('image')
    har_file = request.files.get('har_file')

    if not image_file or not har_file:
        return jsonify({'success': False, 'error': 'Thiếu file ảnh hoặc file HAR!'}), 400

    job_id = uuid.uuid4().hex[:16]
    JOBS[job_id] = {'status': 'pending', 'message': 'Khởi tạo Hàng đợi...'}

    image_bytes = image_file.read()
    har_bytes = io.BytesIO(har_file.read())

    # Chạy ngầm quy trình 2 bước
    thread = threading.Thread(target=process_full_garena_flow, args=(job_id, har_bytes, image_bytes))
    thread.start()

    return jsonify({'success': True, 'job_id': job_id})

@app.route('/api/check/<job_id>', methods=['GET'])
def api_check(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Mã Job không tồn tại!'}), 404
    return jsonify({'success': True, 'data': job})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)