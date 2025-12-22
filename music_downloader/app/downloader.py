import os
import yt_dlp
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError
import config

class MusicDownloader:
    def __init__(self):
        # yt-dlp configuration
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(config.DOWNLOAD_DIR, '%(uploader)s - %(title)s.%(ext)s'),
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

        # Check for local ffmpeg if configured (mostly for local testing)
        if hasattr(config, 'BIN_DIR') and config.BIN_DIR and os.path.exists(config.BIN_DIR):
             self.ydl_opts['ffmpeg_location'] = config.BIN_DIR

    def search_video(self, query):
        """
        Searches YouTube for the query and returns the top result metadata.
        """
        search_opts = {
            'quiet': True,
            'default_search': 'ytsearch1', 
            'skip_download': True,
            'extract_flat': True, # Fast extraction, minimal info
        }
        
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                print(f"Searching for: {query}")
                result = ydl.extract_info(query, download=False)
                
                if 'entries' in result and len(result['entries']) > 0:
                    video = result['entries'][0]
                    # Sometimes flat extraction misses thumbnail, we might need full extraction if missing
                    # But flat is fast. Let's see if we get what we need.
                    return {
                        'found': True,
                        'title': video.get('title'),
                        'uploader': video.get('uploader'),
                        'id': video.get('id'),
                        'url': video.get('url') or f"https://www.youtube.com/watch?v={video.get('id')}",
                        'thumbnail': video.get('thumbnail') # Might be none in flat
                    }
                else:
                    return {'found': False}
        except Exception as e:
            print(f"Search Error: {e}")
            return {'found': False, 'error': str(e)}

    def download_track(self, url):
        """
        Downloads a track from YouTube, converting to MP3 and tagging it.
        """
        try:
            # Re-evaluate DOWNLOAD_DIR in case it changed
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
            
            # Ensure outtmpl is set correctly
            self.ydl_opts['outtmpl'] = os.path.join(config.DOWNLOAD_DIR, '%(uploader)s - %(title)s.%(ext)s')

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # 1. Extract Info first to get metadata for tagging
                print(f"Fetching metadata for {url}...")
                info = ydl.extract_info(url, download=False)
                
                channel_name = info.get('uploader')
                video_title = info.get('title')
                
                if not channel_name or not video_title:
                     return False, "Could not extract metadata (Artist/Title)."

                print(f"Downloading: {channel_name} - {video_title}")
                
                # 2. Download
                ydl.download([url])
                
                # 3. Determine Filename
                filename_base = ydl.prepare_filename(info)
                final_path = os.path.splitext(filename_base)[0] + ".mp3"
                
                # 4. Update Tags strictly
                if os.path.exists(final_path):
                    self._tag_file(final_path, artist=channel_name, title=video_title)
                    return True, f"Saved: {channel_name} - {video_title}"
                else:
                    return False, "Download finished but file not found."

        except Exception as e:
            print(f"Error: {e}")
            return False, str(e)

    def _tag_file(self, filepath, artist, title):
        try:
            try:
                tags = EasyID3(filepath)
            except ID3NoHeaderError:
                tags = EasyID3()
            
            tags['artist'] = artist
            tags['title'] = title
            tags.save(filepath)
            print(f"Tags updated: Artist='{artist}', Title='{title}'")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
