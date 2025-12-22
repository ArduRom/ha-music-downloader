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
                    'key': 'EmbedThumbnail', # This ensures the Cover Art is in the file
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
                # Fixing TypeError: Check correct response structure
                if isinstance(result, dict) and 'entries' in result:
                    search_results = result['entries']
                    if search_results and len(search_results) > 0:
                        video = search_results[0]
                        return {
                            'found': True,
                            'title': video.get('title'),
                            'uploader': video.get('uploader'),
                            'id': video.get('id'),
                            'url': video.get('webpage_url') or video.get('url'),
                            'thumbnail': video.get('thumbnail')
                        }
                    else:
                        print("DEBUG: Entries list was empty")
                        return {'found': False, 'message': 'No entries found.'}
                elif isinstance(result, dict) and 'title' in result:
                    # Direct video result fallback
                     return {
                        'found': True,
                        'title': result.get('title'),
                        'uploader': result.get('uploader'),
                        'id': result.get('id'),
                        'url': result.get('webpage_url') or result.get('url'),
                        'thumbnail': result.get('thumbnail')
                    }
                else:
                    print(f"DEBUG: Unknown result type: {type(result)} - {result}")
                    return {'found': False}
        except Exception as e:
            print(f"Search Error: {e}")
            return {'found': False, 'error': str(e)}

    def clean_metadata(self, channel, title):
        """
        Smart parsing to separate Artist and Title correctly.
        Common formats: 
        1. "Artist - Title" (in Title)
        2. "Artist - Title (Official Video)"
        """
        artist = channel
        song_title = title
        
        # 1. Clean up "VEVO" or "Official" from channel name if needed, 
        # but usually "Artist - Title" in the video title is the most accurate source.
        
        # Check if " - " is in the title (Separator)
        if " - " in title:
            parts = title.split(" - ", 1)
            artist = parts[0].strip()
            song_title = parts[1].strip()
        
        # Clean junk from Title (e.g. " (Official Video)", " [Lyrics]")
        # Regex to remove brackets with common keywords or just all brackets at the end
        junk_patterns = [
            r"\(Official Video\)", r"\(Official Audio\)", r"\(Lyrics\)", 
            r"\[Official Video\]", r"\[Audio\]", r"ft\..*", r"feat\..*"
        ]
        
        for pattern in junk_patterns:
            song_title = re.sub(pattern, "", song_title, flags=re.IGNORECASE).strip()
            
        # Also clean artist if it came from the split
        return artist, song_title

    def download_track(self, url):
        try:
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                raw_channel = info.get('uploader', 'Unknown Artist')
                raw_title = info.get('title', 'Unknown Title')
                
                # SMART METADATA PARSING
                artist, title = self.clean_metadata(raw_channel, raw_title)
                
                # Check for Genre (YouTube Categories)
                genre = "Unknown"
                if info.get('categories'):
                    genre = info['categories'][0] # e.g. "Music" - not great, but something.
                
                print(f"Metadata Plan -> Artist: '{artist}', Title: '{title}', Genre: '{genre}'")
                
                # Set filename to "Artist - Title.mp3"
                final_filename = f"{artist} - {title}.mp3".replace("/", "_").replace("\\", "_")
                self.ydl_opts['outtmpl'] = os.path.join(config.DOWNLOAD_DIR, f"{artist} - {title}.%(ext)s")
                
                # DOWNLOAD
                ydl.download([url])
                
                # PATH CALCULATION
                final_path = os.path.join(config.DOWNLOAD_DIR, final_filename)
                
                # STRICT TAGGING (Mutagen)
                if os.path.exists(final_path):
                    self._tag_file(final_path, artist, title, genre)
                    return True, f"Saved & Tagged: {artist} - {title}"
                else:
                    return True, f"Downloaded, but check filename: {artist} - {title}"

        except Exception as e:
            print(f"Error: {e}")
            return False, str(e)

    def _tag_file(self, filepath, artist, title, genre):
        try:
            try:
                tags = EasyID3(filepath)
            except ID3NoHeaderError:
                tags = EasyID3()
            
            tags['artist'] = artist
            tags['title'] = title
            tags['genre'] = genre
            tags.save(filepath)
            print(f"Tags updated: Artist='{artist}', Title='{title}'")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
