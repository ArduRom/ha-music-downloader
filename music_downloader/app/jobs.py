"""
Download queue with progress tracking and a persistent download history.
"""
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

ACTIVE_STATES = ('queued', 'downloading', 'processing')
MAX_FINISHED_JOBS = 50
MAX_HISTORY = 500


class JobManager:
    def __init__(self, run_fn, history_file, max_workers=2):
        """run_fn(payload, progress_cb) -> (ok, message, relative_path)"""
        self._run_fn = run_fn
        self._jobs = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='download')
        self._history_file = history_file
        self._history = self._load_history()

    # -- history -----------------------------------------------------------

    def _load_history(self):
        try:
            with open(self._history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Could not read download history: {e}")
            return []

    def _save_history(self):
        try:
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)
            tmp = self._history_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._history[-MAX_HISTORY:], f, ensure_ascii=False, indent=1)
            os.replace(tmp, self._history_file)
        except Exception as e:
            print(f"Could not write download history: {e}")

    def history(self, limit=24):
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def downloaded_ids(self):
        with self._lock:
            return {h.get('video_id') for h in self._history if h.get('video_id')}

    # -- jobs --------------------------------------------------------------

    def submit(self, payload):
        """Queue a download. Returns (job, created)."""
        video_id = payload.get('video_id')
        with self._lock:
            for job in self._jobs.values():
                if video_id and job['video_id'] == video_id and job['status'] in ACTIVE_STATES:
                    return dict(job), False
            job = {
                'id': uuid.uuid4().hex[:12],
                'video_id': video_id,
                'url': payload.get('url'),
                'title': payload.get('title') or 'Unbekannter Titel',
                'artist': ", ".join(payload.get('artists') or []),
                'album': payload.get('album') or '',
                'image': payload.get('cover') or payload.get('thumbnail'),
                'status': 'queued',
                'progress': 0,
                'message': 'In Warteschlange',
                'path': None,
                'created': time.time(),
                'finished': None,
            }
            self._jobs[job['id']] = job
            self._prune()
        self._pool.submit(self._run, job['id'], payload)
        return dict(job), True

    def _prune(self):
        finished = sorted((j for j in self._jobs.values() if j['status'] not in ACTIVE_STATES),
                          key=lambda j: j['created'])
        for job in finished[:-MAX_FINISHED_JOBS]:
            self._jobs.pop(job['id'], None)

    def _update(self, job_id, **fields):
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.update(fields)

    def _run(self, job_id, payload):
        self._update(job_id, status='downloading', message='Download startet …')

        def progress(status, percent=None, message=None):
            fields = {'status': status}
            if percent is not None:
                fields['progress'] = max(0, min(99, int(percent)))
            if message:
                fields['message'] = message
            self._update(job_id, **fields)

        try:
            ok, message, rel_path = self._run_fn(payload, progress)
        except Exception as e:
            ok, message, rel_path = False, str(e), None

        if ok:
            self._update(job_id, status='done', progress=100, message=message, path=rel_path,
                         finished=time.time())
            with self._lock:
                job = dict(self._jobs.get(job_id) or {})
                self._history.append({
                    'video_id': job.get('video_id'),
                    'title': job.get('title'),
                    'artist': job.get('artist'),
                    'album': job.get('album'),
                    'image': job.get('image'),
                    'path': rel_path,
                    'at': time.time(),
                })
                self._save_history()
        else:
            self._update(job_id, status='error', message=message or 'Download fehlgeschlagen',
                         finished=time.time())

    def list(self):
        with self._lock:
            jobs = [dict(j) for j in self._jobs.values()]
        return sorted(jobs, key=lambda j: -j['created'])

    def clear_finished(self):
        with self._lock:
            for job_id in [k for k, j in self._jobs.items() if j['status'] not in ACTIVE_STATES]:
                self._jobs.pop(job_id, None)
