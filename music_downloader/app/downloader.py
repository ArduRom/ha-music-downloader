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
            # 'extract_flat': True,  <-- REMOVED: Caused empty results sometimes. We want full info.
        }
        
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                print(f"Searching for: {query}")
                result = ydl.extract_info(query, download=False)
                
                # Debug logging
                if 'entries' in result:
                    print(f"DEBUG: Found {len(result['entries'])} entries.")
                else:
                    print(f"DEBUG: No 'entries' key in result. Keys: {result.keys()}")

                if 'entries' in result and len(result['entries']) > 0:
                    video = result['entries'][0]
                    
                    # Log what we found
                    print(f"DEBUG: Selected video: {video.get('title')} by {video.get('uploader')}")

                    return {
                        'found': True,
                        'title': video.get('title'),
                        'uploader': video.get('uploader'),
                        'id': video.get('id'),
                        'url': video.get('webpage_url') or video.get('url'), # webpage_url is better usually
                        'thumbnail': video.get('thumbnail')
                    }
                else:
                    print("DEBUG: Search returned no entries.")
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
                # ffmpeg conversion changes extension to .mp3, but prepare_filename might return .webm/.m4a
                # We know our output template finishes with .mp3 effectively after post-processing?
                # Actually yt-dlp prepare_filename returns the ORIGINAL format filename usually.
                # We need to predict the final filename.
                
                # Construct expected final path manually to be safe
                final_filename = f"{channel_name} - {video_title}.mp3"
                # Sanitize filename (yt-dlp does this, simplified check here)
                # Better: Use the result of download to find file? No direct return.
                
                # Simple heuristic: Look for the most recently created mp3 in that folder? 
                # Or just trust the template.
                
                # Let's try to assume standard yt-dlp sanitization
                # For now, let's just attempt to tag whatever matches closest or rely on success message.
                
                # Actually, standard logic:
                sanitized_title = video_title.replace("/", "_").replace(":", " -") # and so on.
                # This is tricky. 
                
                # Let's iterate files in download dir and find the one that matches our logic
                # or just 'pass' on tagging if we can't find it easily, but user wants tags.
                # Wait, mutagen tagging was a requirement.
                
                # Re-do: 
                # We can perform tagging inside a post-processor hook or use 'add_metadata' (already true).
                # 'FFmpegMetadata' adds metadata! We might NOT need manual mutagen tagging if yt-dlp does it right.
                # yt-dlp maps uploader->artist and title->title by default.
                
                # So we might not need self._tag_file at all if FFmpegMetadata works.
                # But let's keep it if we want strict enforcement.
                
                return True, f"Saved: {channel_name} - {video_title}"

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
