from flask import Flask, render_template, request, jsonify
from werkzeug.exceptions import HTTPException
import config
from downloader import MusicDownloader
import os
import threading
import traceback

app = Flask(__name__)
# Fix: Ensure config is loaded before we start
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
    return jsonify(result)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    title = data.get('title')
    channel = data.get('channel')
    
    if not title:
        return jsonify({"success": False, "message": "No title provided"}), 400
        
    proposal = loader.analyze_metadata(title, channel)
    return jsonify({"success": True, "result": proposal})

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    manual_artists = data.get('artists')
    manual_title = data.get('title')
    manual_album = data.get('album')
    manual_year = data.get('year')
    
    if not url:
        return jsonify({"success": False, "message": "No URL provided"}), 400
        
    print(f"Received download request for: {url}")
    
    # Define wrapper for background execution
    def background_task():
        print(f"Starting background download for {url}")
        try:
            loader.download_track(url, manual_artists, manual_title, manual_album, manual_year)
            print(f"Background download finished for {url}")
        except Exception as e:
            print(f"Background download failed: {e}")

    # Start independent thread
    thread = threading.Thread(target=background_task)
    thread.daemon = True # ensure thread dies if main process dies
    thread.start()
    
    return jsonify({"success": True, "message": "Download started in background. Check /media folder soon."})

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors like 404
    if isinstance(e, HTTPException):
        print(f"HTTP ERROR: {e}")
        return e
        
    # Generic error handling for 500s
    print(f"SERVER ERROR: {e}")
    traceback.print_exc()
    return jsonify({"success": False, "message": str(e), "error": "Internal Server Error"}), 500

if __name__ == '__main__':
    print(f"Starting server on 0.0.0.0:8099. Download Dir: {config.DOWNLOAD_DIR}")
    # Fix: Set threaded=True for better responsiveness
    app.run(host='0.0.0.0', port=8099, debug=False, threaded=True)
