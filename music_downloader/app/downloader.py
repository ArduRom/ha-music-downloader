import os
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError
import config
import re
import traceback
import copy

class MusicDownloader:
    def __init__(self):
        # Base options
        self.base_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                },
                {
                    'key': 'EmbedThumbnail', 
                },
                {
                    'key': 'FFmpegMetadata', 
                    'add_metadata': True,
                }
            ],
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
            # Fix 403 Forbidden: Force IPv4 and use Android client
            'source_address': '0.0.0.0', 
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            }, 
        }
        
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

    def search_video(self, query):
        search_opts = {
            'quiet': True,
            'default_search': 'ytsearch15', 
            'skip_download': True,
            'ignoreerrors': True,
            'extract_flat': False, # Changed to False to ensure we get 'uploader' and other metadata
            # Copy robust network options
            'source_address': '0.0.0.0',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                print(f"Searching for: {query}")
                result = ydl.extract_info(query, download=False)
                
                results_list = []
                
                if 'entries' in result:
                    for entry in result['entries']:
                        if not entry: continue
                        # Filter out obviously bad results if needed (e.g., extremely long/short)
                        results_list.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'uploader': entry.get('uploader'),
                            'url': entry.get('url') or entry.get('webpage_url'),
                            'duration': entry.get('duration'),
                            # 'thumbnail': entry.get('thumbnail') # flat extraction might not have good thumbnails
                        })
                
                return {'found': True, 'results': results_list}

        except Exception as e:
            print(f"Search Error: {e}")
            traceback.print_exc()
            return {'found': False, 'error': str(e)}

    def analyze_metadata(self, title, channel):
        """
        Generates metadata proposal for the selected video.
        """
        # Try AI first
        ai_proposal = self._get_ai_metadata(title, channel)
        
        if ai_proposal:
            artists, final_title, album, year = ai_proposal
            print("Using AI Metadata Proposal.")
        else:
            print("Using Regex Metadata Proposal.")
            artists, final_title = self.clean_metadata(channel, title)
            album = ""
            year = ""
        
        return {
            'proposal_artists': artists,
            'proposal_title': final_title,
            'proposal_album': album,
            'proposal_year': year
        }

    def clean_metadata(self, channel, title):
        """
        Smart parsing to separate Artist and Title correctly.
        Returns: (artists_list, song_title)
        """
        artist_str = channel
        song_title = title
        
        # 1. Separator Check: "MainArtist - SongTitle"
        if " - " in title:
            parts = title.split(" - ", 1)
            artist_str = parts[0].strip()
            song_title = parts[1].strip()
        
        # 2. Extract featured artists from Title (e.g. "Song (feat. X)")
        featured_artists = []
        # Look for feat. patterns
        feat_pattern = r"(?i)(?:feat\.?|ft\.?|featuring)\s+(.+?)(?=\)|\]|$)"
        matches = re.findall(feat_pattern, song_title)
        for match in matches:
            # Clean match (remove trailing brackets if regex got greedy)
            feat_name = match.strip()
            if feat_name.endswith(')'): feat_name = feat_name[:-1]
            if feat_name.endswith(']'): feat_name = feat_name[:-1]
            featured_artists.append(feat_name)

        # 3. Clean junk from Title
        junk_patterns = [
            r"\(Official Video\)", r"\(Official Audio\)", r"\(Lyrics\)", 
            r"\[Official Video\]", r"\[Audio\]", 
            r"(?i)[\(\[]?(?:feat\.?|ft\.?|featuring)\s+.+?[\)\]]?",
            # Extra Cleaners
            r"(?i)\[HD\]", r"(?i)\[HQ\]", r"(?i)\(HD\)", r"(?i)\(HQ\)",
            r"(?i)\(Video\)", r"(?i)\[Video\]",
            r"(?i)\(Official\)", r"(?i)\[Official\]",
            r"(?i)4K", r"(?i)HD"
        ]
        for pattern in junk_patterns:
            song_title = re.sub(pattern, "", song_title, flags=re.IGNORECASE).strip()

        # 4. Split Artists String (e.g. "Martin Garrix, Macklemore & Patrick Stump")
        # We split by comma (,) and Ampersand (&) and " x "
        artist_str = re.sub(r"(?i)\s+x\s+", " & ", artist_str)
        primary_artists = re.split(r",|&", artist_str)
        
        # Clean and collect final list
        final_artists = []
        for a in primary_artists:
            a = a.strip()
            if a and a not in final_artists:
                final_artists.append(a)
                
        # Parse featured artists string too
        for f in featured_artists:
            subs = re.split(r",|&", f)
            for s in subs:
                s = s.strip()
                if s and s not in final_artists:
                    final_artists.append(s)

        if not final_artists:
            final_artists = ["Unknown Artist"]

        return final_artists, song_title

    def download_track(self, url, manual_artists=None, manual_title=None, manual_album=None, manual_year=None):
        try:
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
            
            # Phase 1: Meta
            ydl_opts_info = { 'quiet': True, 'skip_download': True, 'format': 'bestaudio/best' }
            
            artists_list = manual_artists if manual_artists else ["Unknown"]
            title = manual_title if manual_title else "Unknown"
            album = manual_album if manual_album else "Unknown"
            year = manual_year if manual_year else ""
            genre = "Unknown"
            
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                print(f"Fetching metadata for {url}...")
                info = ydl.extract_info(url, download=False)
                
                if not manual_artists or not manual_title:
                     # Fallback if somehow not passed (should not happen with new UI)
                     raw_channel = info.get('uploader', 'Unknown Artist')
                     raw_title = info.get('title', 'Unknown Title')
                     auto_artists, auto_title = self.clean_metadata(raw_channel, raw_title)
                     if not manual_artists: artists_list = auto_artists
                     if not manual_title: title = auto_title

                if info.get('categories') and isinstance(info['categories'], list) and len(info['categories']) > 0:
                    genre = info['categories'][0]
                
                print(f"Final Plan -> Artists: {artists_list}, Title: '{title}', Album: '{album}'")

            # Phase 2: Download
            filename_artist_str = artists_list[0]
            
            # Helper to sanitize for Windows filenames
            def sanitize_name(name):
                # Replace bad chars with _ or -
                return name.replace("/", "_").replace("\\", "_").replace(":", "-").replace("*", "").replace("?", "").replace("\"", "'").replace("<", "").replace(">", "").replace("|", "").strip()

            safe_artist = sanitize_name(filename_artist_str)
            # Remove trailing dots manually (windows hates them at end of folders)
            if safe_artist.endswith('.'): safe_artist = safe_artist[:-1]
            if not safe_artist: safe_artist = "Unknown_Artist"
            
            safe_title = sanitize_name(title)
            
            # Construct final paths
            artist_dir = os.path.join(config.DOWNLOAD_DIR, safe_artist)
            if not os.path.exists(artist_dir):
                os.makedirs(artist_dir, exist_ok=True)

            final_filename = f"{safe_artist} - {safe_title}.mp3"
            
            dl_opts = copy.deepcopy(self.base_opts)
            # We explicitly set the path including the artist folder
            dl_opts['outtmpl'] = os.path.join(artist_dir, f"{safe_artist} - {safe_title}.%(ext)s")
            
            print(f"Starting Download -> {final_filename} in {artist_dir}")
            
            with yt_dlp.YoutubeDL(dl_opts) as ydl_dl:
                ydl_dl.download([url])
                
            final_path = os.path.join(artist_dir, final_filename)
            
            if os.path.exists(final_path):
                self._tag_file(final_path, artists_list, title, album, year, genre)
                return True, f"Saved: {safe_artist}/{final_filename}"
            else:
                return True, f"Downloaded (Check folder): {safe_artist}/{final_filename}"

        except Exception as e:
            print(f"Download Error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)

    def _tag_file(self, filepath, artists_list, title, album, year, genre):
        try:
            try:
                tags = EasyID3(filepath)
            except ID3NoHeaderError:
                tags = EasyID3()
            
            tags['artist'] = artists_list
            tags['title'] = title
            tags['album'] = album
            tags['genre'] = genre
            if year:
                tags['date'] = year
                tags['originaldate'] = year
            
            tags.save(filepath)
            print(f"Tags updated: Artists={artists_list}, Title='{title}', Album='{album}'")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
