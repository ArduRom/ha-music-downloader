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
    manual_artists = data.get('artists') # Expecting list of strings
    manual_title = data.get('title')     # Expecting string
    
    if not url:
        return jsonify({"success": False, "message": "No URL provided"}), 400
        
    print(f"Received download request for: {url} | Artists: {manual_artists} | Title: {manual_title}")
    
    # Pass metadata to downloader
    success, message = loader.download_track(url, manual_artists, manual_title)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    if isinstance(e, HTTPException):
        return ignored
    # Return JSON for non-HTTP errors
    print(f"SERVER ERROR: {e}")
    import traceback
    traceback.print_exc()
    return jsonify({"success": False, "message": str(e), "error": "Internal Server Error"}), 500

from werkzeug.exceptions import HTTPException

if __name__ == '__main__':
    print(f"Starting server on 0.0.0.0:8099. Download Dir: {config.DOWNLOAD_DIR}")
    # Fix: Set threaded=True for better responsiveness
    app.run(host='0.0.0.0', port=8099, debug=False, threaded=True)
