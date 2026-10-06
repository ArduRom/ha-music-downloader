import os
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
import config
import metadata
import traceback
import copy

NETWORK_OPTS = {
    # Fix 403 Forbidden: Force IPv4 and use Android client
    'source_address': '0.0.0.0',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        }
    },
}


def sanitize_name(name):
    """Make a string safe for Windows/SMB file and folder names."""
    name = (name or "")
    for bad, good in (("/", "_"), ("\\", "_"), (":", "-"), ("*", ""), ("?", ""), ("\"", "'"),
                      ("<", ""), (">", ""), ("|", "")):
        name = name.replace(bad, good)
    # Windows hates trailing dots/spaces on folders
    return name.strip().rstrip(". ")


class MusicDownloader:
    def __init__(self):
        # Base options
        self.base_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'overwrites': True,
        }
        self.base_opts.update(copy.deepcopy(NETWORK_OPTS))

        if hasattr(config, 'BIN_DIR') and config.BIN_DIR and os.path.exists(config.BIN_DIR):
             self.base_opts['ffmpeg_location'] = config.BIN_DIR

    def _get_ai_metadata(self, title, channel):
        """
        Uses OpenAI API (via requests) to intelligently parse metadata.
        Returns: (artists_list, song_title, album, year)
        """
        api_key = getattr(config, 'OPENAI_API_KEY', '')
        # Also check os.environ as fallback if config injection behaves differently
        if not api_key:
             print("DEBUG: No OpenAI API Key found.")
             return None

        try:
            import requests
            import json
            
            prompt = f"""
            Analyze the following YouTube video info and extract music metadata.
            Video Title: "{title}"
            Channel Name: "{channel}"
            
            Task:
            1. Identify the true Artist(s) and Song Title.
            2. Identify the Release Year.
            3. CLEAN the Title: Remove ALL junk like:
               - "(Official Video)", "(Lyrics)", "(Live)", "(HD)", "(4K)", "Official Audio"
               - "ft.", "feat.", "featuring" (Move these artists to the artist list instead)
            
            4. DETERMINE ALBUM:
               - If it is CLEARLY from a specific album (e.g. "from the album 'Cloud Nine'"), use that album name.
               - If it is a Single or the album is unknown, SET THE ALBUM NAME TO THE SONG TITLE.
               - DO NOT use "- Single" suffix.
               - Example: If Title is "Firestone", Album should be "Firestone".
            
            Return STRICTLY valid JSON with these keys:
            - "artist": List of strings (Main artist first, then featured guests)
            - "title": String (Cleaned song title)
            - "album": String (See Rule 4)
            - "year": String
            
            Example JSON:
            {{
              "artist": ["Martin Garrix", "Macklemore"],
              "title": "Summer Days",
              "album": "Summer Days",
              "year": "2019"
            }}
            """
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a music metadata expert. extract JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
            }
            
            print("DEBUG: Calling OpenAI API...")
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"DEBUG: OpenAI raw response: {content}")
            
            # Parse JSON from content
            meta = json.loads(content)
            
            artists = meta.get('artist', [])
            if isinstance(artists, str): artists = [artists]
            
            parsed_title = meta.get('title', title)
            parsed_album = meta.get('album', '')
            parsed_year = meta.get('year', '')
            
            # FORCE: If album is generic or empty, use the Song Title
            if not parsed_album or parsed_album.lower() in ['single', 'unknown', 'none', 'unknown album']:
                parsed_album = parsed_title
            
            return (artists, parsed_title, parsed_album, parsed_year)
            
        except Exception as e:
            print(f"OpenAI Error: {e}")
            return None

    def search_video(self, query, limit=20):
        search_opts = {
            'quiet': True,
            'skip_download': True,
            'ignoreerrors': True,
            # Flat extraction returns title, channel, duration, views and thumbnails
            # of all results in a single request (much faster than full extraction).
            'extract_flat': 'in_playlist',
        }
        search_opts.update(copy.deepcopy(NETWORK_OPTS))
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                print(f"Searching for: {query}")
                result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False) or {}

                results_list = []
                for entry in result.get('entries') or []:
                    if not entry or not entry.get('id'):
                        continue
                    if entry.get('live_status') in ('is_live', 'is_upcoming'):
                        continue
                    video_id = entry['id']
                    channel = entry.get('channel') or entry.get('uploader') or ""
                    results_list.append({
                        'id': video_id,
                        'title': entry.get('title') or "",
                        'channel': channel,
                        'uploader': channel,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'duration': entry.get('duration'),
                        'views': entry.get('view_count'),
                        'verified': bool(entry.get('channel_is_verified')),
                        'thumbnail': self._pick_thumbnail(entry),
                    })

                return {'found': bool(results_list), 'results': results_list}

        except Exception as e:
            print(f"Search Error: {e}")
            traceback.print_exc()
            return {'found': False, 'results': [], 'error': str(e)}

    @staticmethod
    def _pick_thumbnail(entry):
        thumbs = [t for t in (entry.get('thumbnails') or []) if t.get('url')]
        sized = [t for t in thumbs if t.get('width') and t['width'] <= 720]
        if sized:
            return max(sized, key=lambda t: t['width'])['url']
        # hqdefault always exists; the UI crops it to 16:9
        return f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg"

    def analyze_metadata(self, title, channel, duration=None):
        """
        Generates a metadata proposal for the selected video by comparing it
        with public music libraries (MusicBrainz, iTunes, Deezer).
        """
        ai_proposal = self._get_ai_metadata(title, channel)
        if ai_proposal:
            artists, song_title, ai_album, ai_year = ai_proposal
            parse_source = 'ai'
        else:
            artists, song_title = self.clean_metadata(channel, title)
            ai_album, ai_year = "", ""
            parse_source = 'parsed'
        artists = artists or ["Unknown Artist"]

        library = metadata.lookup(
            query=f"{artists[0]} {song_title}", artist=artists[0], title=song_title)
        matches = library['matches']
        for match in matches:
            match['deviation'] = metadata.deviation(duration, match.get('duration'))

        best_idx, confident = metadata.choose_for_video(matches, artists[0], song_title, duration)
        best = matches[best_idx] if best_idx is not None and confident else None

        if best:
            print(f"Using library metadata ({', '.join(s['label'] for s in best['sources'])}).")
            proposal = {
                'proposal_artists': best['artists'] or artists,
                'proposal_title': best['title'],
                'proposal_album': best['album'] or best['title'],
                'proposal_year': best['year'] or ai_year,
                'genre': best['genre'],
                'cover': best['cover'],
                'isrc': best['isrc'],
                'track_number': best['track_number'],
                'reference_duration': best['duration'],
                'deviation': best['deviation'],
                'source': 'library',
                'sources': best['sources'],
                'confidence': best['confidence'],
            }
        else:
            print(f"Using {parse_source} metadata proposal (no confident library match).")
            proposal = {
                'proposal_artists': artists,
                'proposal_title': song_title,
                # Singles use the song title as album name
                'proposal_album': ai_album or song_title,
                'proposal_year': ai_year,
                'genre': "",
                'cover': None,
                'isrc': None,
                'track_number': None,
                'reference_duration': None,
                'deviation': None,
                'source': parse_source,
                'sources': [],
                'confidence': 0,
            }

        proposal['matches'] = matches
        proposal['selected'] = best_idx if best else None
        proposal['errors'] = library['errors']
        return proposal

    def clean_metadata(self, channel, title):
        """
        Smart parsing to separate Artist and Title correctly.
        Returns: (artists_list, song_title)
        """
        return metadata.parse_video_title(title, channel)

    def build_target(self, artists, title, album):
        """Returns (directory, filename, relative path) for a track: Artist/Album/Artist - Title.mp3"""
        safe_artist = sanitize_name((artists or ["Unknown"])[0]) or "Unknown_Artist"
        safe_album = sanitize_name(album) or "Unknown_Album"
        safe_title = sanitize_name(title) or "Unknown"
        final_dir = os.path.join(config.DOWNLOAD_DIR, safe_artist, safe_album)
        filename = f"{safe_artist} - {safe_title}.mp3"
        return final_dir, filename, f"{safe_artist}/{safe_album}/{filename}"

    def target_exists(self, artists, title, album):
        final_dir, filename, rel = self.build_target(artists, title, album)
        return rel, os.path.exists(os.path.join(final_dir, filename))

    def download_track(self, url, manual_artists=None, manual_title=None, manual_album=None, manual_year=None,
                       genre=None, cover_url=None, isrc=None, track_number=None, progress_cb=None):
        """
        Downloads, converts and tags a track.
        Returns (ok, message, relative_path).
        """
        def report(status, percent=None, message=None):
            if progress_cb:
                try:
                    progress_cb(status, percent, message)
                except Exception:
                    pass

        try:
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)

            artists_list = manual_artists if manual_artists else None
            title = manual_title if manual_title else None
            year = manual_year if manual_year else ""

            if not artists_list or not title:
                # Fallback if the UI did not send metadata
                with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
                    print(f"Fetching metadata for {url}...")
                    info = ydl.extract_info(url, download=False)
                auto_artists, auto_title = self.clean_metadata(info.get('uploader'), info.get('title'))
                artists_list = artists_list or auto_artists
                title = title or auto_title

            album = manual_album if manual_album else title
            final_dir, final_filename, rel_path = self.build_target(artists_list, title, album)
            os.makedirs(final_dir, exist_ok=True)
            print(f"Final Plan -> Artists: {artists_list}, Title: '{title}', Album: '{album}'")

            cover_data, cover_mime = metadata.fetch_cover(cover_url) if cover_url else (None, None)

            dl_opts = copy.deepcopy(self.base_opts)
            dl_opts['outtmpl'] = os.path.join(final_dir, final_filename[:-4] + ".%(ext)s")
            postprocessors = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'},
                {'key': 'FFmpegMetadata', 'add_metadata': True},
            ]
            if not cover_data:
                # No library cover: embed the YouTube thumbnail instead
                dl_opts['writethumbnail'] = True
                postprocessors.insert(0, {'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg', 'when': 'before_dl'})
                postprocessors.append({'key': 'EmbedThumbnail', 'already_have_thumbnail': False})
            dl_opts['postprocessors'] = postprocessors

            def on_progress(d):
                if d.get('status') == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate')
                    if total:
                        report('downloading', 90.0 * d.get('downloaded_bytes', 0) / total, 'Lädt herunter …')
                elif d.get('status') == 'finished':
                    report('processing', 90, 'Konvertiere zu MP3 …')

            def on_postprocess(d):
                if d.get('status') == 'started':
                    report('processing', 93, 'Konvertiere zu MP3 …')

            dl_opts['progress_hooks'] = [on_progress]
            dl_opts['postprocessor_hooks'] = [on_postprocess]

            print(f"Starting Download -> {final_filename} in {final_dir}")
            report('downloading', 0, 'Lädt herunter …')
            with yt_dlp.YoutubeDL(dl_opts) as ydl_dl:
                info = ydl_dl.extract_info(url, download=True) or {}

            if not genre and isinstance(info.get('categories'), list) and info['categories']:
                genre = info['categories'][0]

            final_path = os.path.join(final_dir, final_filename)
            if not os.path.exists(final_path):
                return True, f"Heruntergeladen (Ordner prüfen): {rel_path}", rel_path

            report('processing', 97, 'Schreibe Tags …')
            self._tag_file(final_path, artists_list, title, album, year, genre,
                           isrc=isrc, track_number=track_number)
            if cover_data:
                self._embed_cover(final_path, cover_data, cover_mime)
            return True, f"Gespeichert: {rel_path}", rel_path

        except Exception as e:
            print(f"Download Error: {e}")
            traceback.print_exc()
            return False, str(e), None

    def _tag_file(self, filepath, artists_list, title, album, year, genre, isrc=None, track_number=None):
        try:
            try:
                tags = EasyID3(filepath)
            except ID3NoHeaderError:
                tags = EasyID3()

            tags['artist'] = artists_list
            tags['albumartist'] = artists_list[0]
            tags['title'] = title
            tags['album'] = album
            if genre:
                tags['genre'] = genre
            if year:
                tags['date'] = year
                tags['originaldate'] = year
            if isrc:
                tags['isrc'] = isrc
            if track_number:
                tags['tracknumber'] = str(track_number)

            tags.save(filepath)
            print(f"Tags updated: Artists={artists_list}, Title='{title}', Album='{album}'")

        except Exception as e:
            print(f"Tagging Error: {e}")

    def _embed_cover(self, filepath, data, mime):
        try:
            tags = ID3(filepath)
            tags.delall('APIC')
            tags.add(APIC(encoding=3, mime=mime or 'image/jpeg', type=3, desc='Cover', data=data))
            tags.save(filepath)
            print("Cover embedded from music library.")
        except Exception as e:
            print(f"Cover Error: {e}")
