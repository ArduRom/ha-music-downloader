import os
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError
import config
import re

class MusicDownloader:
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            # We will set outtmpl dynamically per track to match our strict naming
            'outtmpl': os.path.join(config.DOWNLOAD_DIR, '%(title)s.%(ext)s'), 
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
        }
        
        if hasattr(config, 'BIN_DIR') and config.BIN_DIR and os.path.exists(config.BIN_DIR):
             self.ydl_opts['ffmpeg_location'] = config.BIN_DIR

    def search_video(self, query):
        search_opts = {
            'quiet': True,
            'default_search': 'ytsearch1', 
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                print(f"Searching for: {query}")
                result = ydl.extract_info(query, download=False)
                if 'entries' in result and len(result['entries']) > 0:
                    video = result['entries'][0]
                    return {
                        'found': True,
                        'title': video.get('title'),
                        'uploader': video.get('uploader'),
                        'id': video.get('id'),
                        'url': video.get('webpage_url') or video.get('url'),
                        'thumbnail': video.get('thumbnail')
                    }
                else:
                    return {'found': False}
        except Exception as e:
            print(f"Search Error: {e}")
            return {'found': False, 'error': str(e)}

    def clean_metadata(self, channel, title):
        """
        Parses title for Artist, Song, and Featured Artists.
        """
        main_artist = channel
        song_title = title
        featured_artists = []

        # 1. Separator Check: "MainArtist - SongTitle"
        if " - " in title:
            parts = title.split(" - ", 1)
            main_artist = parts[0].strip()
            song_title = parts[1].strip()

        # 2. Extract Featured Artists (feat. X / ft. Y)
        # Regex to find "feat. Name" or "ft. Name" inside brackets or just at sentence end
        # Capture group (feat. (.+?))
        feat_pattern = r"(?i)(?:feat\.?|ft\.?|featuring)\s+(.+?)(?=\)|\]|$)"
        
        matches = re.findall(feat_pattern, song_title)
        for match in matches:
            # Add to list (clean up leading/trailing symbols if regex captured too much)
            feat = match.strip()
            # sometimes regex captures "Rihanna )", remove trailing )
            if feat.endswith(')'): feat = feat[:-1]
            if feat.endswith(']'): feat = feat[:-1]
            
            # Split multiple featured artists? e.g. "feat. A, B & C"
            # Getting complicated, but let's try a simple split by comma/&
            sub_feats = re.split(r",|&", feat)
            for sub in sub_feats:
                sub = sub.strip()
                if sub and sub not in featured_artists:
                    featured_artists.append(sub)

        # 3. Clean Title removing the "feat. X" parts and other junk
        junk_patterns = [
            r"\(Official Video\)", r"\(Official Audio\)", r"\(Lyrics\)", 
            r"\[Official Video\]", r"\[Audio\]", 
            # Remove the whole feat part strictly now
            r"(?i)[\(\[]?(?:feat\.?|ft\.?|featuring)\s+.+?[\)\]]?" 
        ]
        
        for pattern in junk_patterns:
            song_title = re.sub(pattern, "", song_title, flags=re.IGNORECASE).strip()
            
        # Combine Artists
        # ID3 standard for multiple artists: list of strings or separated by /
        all_artists = [main_artist] + featured_artists
        
        return all_artists, song_title

    def download_track(self, url):
        try:
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                raw_channel = info.get('uploader', 'Unknown Artist')
                raw_title = info.get('title', 'Unknown Title')
                
                # SMART METADATA PARSING (Returns list of artists)
                artists_list, title = self.clean_metadata(raw_channel, raw_title)
                
                # For filename, use Main Artist only or "Main feat. All"
                # To keep it Spotify-like, filename is usually just "Artist - Title.mp3"
                # But tags contain the magic.
                
                main_artist_str = artists_list[0]
                # Join for Filename (safe string)
                if len(artists_list) > 1:
                    # Optional: "Eminem feat. Rihanna - Love..." for filename
                    # But user wanted strict filtering in App, which relies on TAGS.
                    pass 
                
                genre = "Unknown"
                if info.get('categories'):
                    genre = info['categories'][0]

                print(f"Metadata -> Artists: {artists_list}, Title: '{title}'")
                
                final_filename = f"{main_artist_str} - {title}.mp3".replace("/", "_").replace("\\", "_")
                self.ydl_opts['outtmpl'] = os.path.join(config.DOWNLOAD_DIR, f"{main_artist_str} - {title}.%(ext)s")
                
                ydl.download([url])
                
                final_path = os.path.join(config.DOWNLOAD_DIR, final_filename)
                
                if os.path.exists(final_path):
                    self._tag_file(final_path, artists_list, title, genre)
                    return True, f"Saved: {main_artist_str} - {title}"
                else:
                    return True, f"Downloaded logic finished."

        except Exception as e:
            print(f"Error: {e}")
            return False, str(e)

    def _tag_file(self, filepath, artists_list, title, genre):
        try:
            try:
                tags = EasyID3(filepath)
            except ID3NoHeaderError:
                tags = EasyID3()
            
            # Mutagen EasyID3 handles lists correctly for 'artist' frame
            # This creates multiple TPE1 frames or null-separated strings depending on version.
            # Most modern players (and Spotify import) read this as multiple artists.
            tags['artist'] = artists_list
            tags['title'] = title
            tags['genre'] = genre
            tags.save(filepath)
            print(f"Tags applied: Artists={artists_list}, Title={title}")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
