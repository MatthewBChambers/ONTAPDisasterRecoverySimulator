from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
import requests
import os
import tempfile
from datetime import datetime

app = Flask(__name__)

# Node configurations
NODES = {
    'node_a': {
        'url': 'http://localhost:8001',
    },
    'node_b': {
        'url': 'http://localhost:8002',
    }
}

# Shared storage path
STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared_storage")
os.makedirs(STORAGE_PATH, exist_ok=True)

def get_active_node():
    """Get the first available node."""
    for node_name, node_info in NODES.items():
        try:
            response = requests.get(f"{node_info['url']}/health")
            if response.status_code == 200:
                return node_name, node_info
        except requests.RequestException:
            continue
    return None, None

@app.route('/')
def index():
    """Display file list and upload form."""
    node_name, node_info = get_active_node()
    if not node_info:
        return render_template('error.html', message="No active nodes available")

    try:
        response = requests.get(f"{node_info['url']}/files")
        files = response.json()['files']
        return render_template('index.html', files=files, active_node=node_name)
    except requests.RequestException as e:
        return render_template('error.html', message=str(e))

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    node_name, node_info = get_active_node()
    if not node_info:
        return jsonify({"error": "No active nodes available"}), 503

    if 'file' not in request.files:
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    try:
        files = {'file': (file.filename, file.stream, file.content_type)}
        response = requests.post(f"{node_info['url']}/files/upload", files=files)
        if response.status_code == 200:
            return redirect(url_for('index'))
        else:
            return render_template('error.html', message="Upload failed")
    except requests.RequestException as e:
        return render_template('error.html', message=str(e))

@app.route('/download/<filename>')
def download_file(filename):
    """Handle file download."""
    node_name, node_info = get_active_node()
    if not node_info:
        return jsonify({"error": "No active nodes available"}), 503

    try:
        response = requests.get(f"{node_info['url']}/files/{filename}", stream=True)
        if response.status_code == 200:
            temp = tempfile.NamedTemporaryFile(delete=False)
            for chunk in response.iter_content(chunk_size=8192):
                temp.write(chunk)
            temp.close()
            return send_file(temp.name, download_name=filename, as_attachment=True)
        else:
            return render_template('error.html', message="Download failed")
    except requests.RequestException as e:
        return render_template('error.html', message=str(e))

@app.route('/delete/<filename>')
def delete_file(filename):
    """Handle file deletion."""
    node_name, node_info = get_active_node()
    if not node_info:
        return jsonify({"error": "No active nodes available"}), 503

    try:
        response = requests.delete(f"{node_info['url']}/files/{filename}")
        return redirect(url_for('index'))
    except requests.RequestException as e:
        return render_template('error.html', message=str(e))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 