from flask import Flask, render_template, request, jsonify
import config
from downloader import MusicDownloader
import os

app = Flask(__name__)
loader = MusicDownloader()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query')
    if not query:
        return jsonify({"success": False, "message": "No query provided"}), 400
    
    result = loader.search_video(query)
    if result.get('found'):
        return jsonify({"success": True, "result": result})
    else:
        return jsonify({"success": False, "message": "No results found."})

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"success": False, "message": "No URL provided"}), 400
        
    print(f"Received download request for: {url}")
    success, message = loader.download_track(url)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

if __name__ == '__main__':
    print(f"Starting server on 0.0.0.0:5000. Download Dir: {config.DOWNLOAD_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=False)
