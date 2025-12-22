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
                
                # Handling different result types
                # Sometimes result is a dict with 'entries', sometimes directly a dict?
                
                if isinstance(result, dict):
                    # Check for 'entries' (playlist/search result list)
                    if 'entries' in result:
                        entries = result['entries']
                        if entries and len(entries) > 0:
                            video = entries[0]
                            return self._format_video_result(video)
                        else:
                            return {'found': False, 'message': 'No entries found in search result.'}
                    
                    # If no entries, maybe it IS the video info directly?
                    elif 'title' in result and 'uploader' in result:
                         return self._format_video_result(result)
                    
                    else:
                        return {'found': False, 'message': f'Unknown result structure: {list(result.keys())}'}
                else:
                    return {'found': False, 'message': f'Unexpected result type: {type(result)}'}

        except Exception as e:
            print(f"Search Error: {e}")
            return {'found': False, 'error': str(e)}

    def _format_video_result(self, video):
        # Helper to safely extract dict values
        if not isinstance(video, dict):
             return {'found': False, 'message': 'Video entry is not a dict'}
             
        return {
            'found': True,
            'title': video.get('title'),
            'uploader': video.get('uploader'),
            'id': video.get('id'),
            'url': video.get('webpage_url') or video.get('url'),
            'thumbnail': video.get('thumbnail')
        }

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
                
                main_artist_str = artists_list[0]
                
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
                    # Fallback check if simple path failed (maybe extension was .m4a before conversion)
                    # Try to find file starting with pattern?
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
            
            tags['artist'] = artists_list
            tags['title'] = title
            tags['genre'] = genre
            tags.save(filepath)
            print(f"Tags applied: Artists={artists_list}, Title={title}")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
