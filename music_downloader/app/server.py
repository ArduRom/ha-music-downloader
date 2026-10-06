from flask import Flask, render_template, request, jsonify
from werkzeug.exceptions import HTTPException
from concurrent.futures import ThreadPoolExecutor
import config
import metadata
from downloader import MusicDownloader
from jobs import JobManager
import os
import traceback

app = Flask(__name__)
# Fix: Ensure config is loaded before we start
loader = MusicDownloader()
search_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='search')


def run_download(payload, progress_cb):
    return loader.download_track(
        payload['url'],
        payload.get('artists'),
        payload.get('title'),
        payload.get('album'),
        payload.get('year'),
        genre=payload.get('genre'),
        cover_url=payload.get('cover'),
        isrc=payload.get('isrc'),
        track_number=payload.get('track_number'),
        progress_cb=progress_cb,
    )


jobs = JobManager(run_download, os.path.join(config.DATA_DIR, 'history.json'))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/suggest')
def suggest():
    query = request.args.get('q', '')
    return jsonify({"success": True, "results": metadata.suggest(query)})


@app.route('/search', methods=['POST'])
def search():
    data = request.json or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({"success": False, "message": "No query provided"}), 400

    # YouTube search and library lookup run in parallel
    yt_future = search_pool.submit(loader.search_video, query)
    lib_future = search_pool.submit(metadata.lookup, query)
    result = yt_future.result()
    library = lib_future.result()

    reference = library['reference']
    pinned = data.get('reference')
    if pinned:
        reference = metadata.match_reference(pinned, library['matches'])

    downloaded = jobs.downloaded_ids()
    videos = result.get('results') or []
    for video in videos:
        video['downloaded'] = video['id'] in downloaded
    metadata.annotate_videos(videos, reference)

    result.update({
        'success': 'error' not in result,
        'message': result.get('error'),
        'reference': reference,
        'matches': library['matches'],
        'library_errors': library['errors'],
    })
    return jsonify(result)


@app.route('/compare', methods=['POST'])
def compare():
    """Re-evaluate search results against another reference version."""
    data = request.json or {}
    videos = data.get('videos') or []
    metadata.annotate_videos(videos, data.get('reference'))
    return jsonify({"success": True, "results": videos})


@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json or {}
    title = data.get('title')
    channel = data.get('channel')

    if not title:
        return jsonify({"success": False, "message": "No title provided"}), 400

    proposal = loader.analyze_metadata(title, channel, data.get('duration'))
    rel, exists = loader.target_exists(
        proposal['proposal_artists'], proposal['proposal_title'], proposal['proposal_album'])
    proposal['target_path'] = rel
    proposal['exists'] = exists
    return jsonify({"success": True, "result": proposal})


@app.route('/target', methods=['POST'])
def target():
    data = request.json or {}
    rel, exists = loader.target_exists(data.get('artists') or [], data.get('title'), data.get('album'))
    return jsonify({"success": True, "path": rel, "exists": exists})


@app.route('/download', methods=['POST'])
def download():
    data = request.json or {}
    url = data.get('url')

    if not url:
        return jsonify({"success": False, "message": "No URL provided"}), 400

    print(f"Received download request for: {url}")
    job, created = jobs.submit(data)
    message = "Download gestartet" if created else "Wird bereits heruntergeladen"
    return jsonify({"success": True, "message": message, "job": job, "created": created})


@app.route('/jobs')
def list_jobs():
    return jsonify({"success": True, "jobs": jobs.list()})


@app.route('/jobs/clear', methods=['POST'])
def clear_jobs():
    jobs.clear_finished()
    return jsonify({"success": True, "jobs": jobs.list()})


@app.route('/history')
def history():
    return jsonify({"success": True, "history": jobs.history()})


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
