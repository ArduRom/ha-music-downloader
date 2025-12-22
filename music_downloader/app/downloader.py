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
        }
        
        if hasattr(config, 'BIN_DIR') and config.BIN_DIR and os.path.exists(config.BIN_DIR):
             self.base_opts['ffmpeg_location'] = config.BIN_DIR

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
                
                if isinstance(result, dict):
                    if 'entries' in result:
                        entries = result['entries']
                        if entries and len(entries) > 0:
                            return self._format_video_result(entries[0])
                        else:
                            return {'found': False, 'message': 'No entries found in search result.'}
                    elif 'title' in result and 'uploader' in result:
                         return self._format_video_result(result)
                    else:
                        return {'found': False, 'message': f'Unknown result structure: {list(result.keys())}'}
                else:
                    return {'found': False, 'message': f'Unexpected result type: {type(result)}'}

        except Exception as e:
            print(f"Search Error: {e}")
            traceback.print_exc()
            return {'found': False, 'error': str(e)}

    def _format_video_result(self, video):
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
        main_artist = channel
        song_title = title
        featured_artists = []

        if " - " in title:
            parts = title.split(" - ", 1)
            main_artist = parts[0].strip()
            song_title = parts[1].strip()

        feat_pattern = r"(?i)(?:feat\.?|ft\.?|featuring)\s+(.+?)(?=\)|\]|$)"
        matches = re.findall(feat_pattern, song_title)
        for match in matches:
            feat = match.strip()
            if feat.endswith(')'): feat = feat[:-1]
            if feat.endswith(']'): feat = feat[:-1]
            sub_feats = re.split(r",|&", feat)
            for sub in sub_feats:
                sub = sub.strip()
                if sub and sub not in featured_artists:
                    featured_artists.append(sub)

        junk_patterns = [
            r"\(Official Video\)", r"\(Official Audio\)", r"\(Lyrics\)", 
            r"\[Official Video\]", r"\[Audio\]", 
            r"(?i)[\(\[]?(?:feat\.?|ft\.?|featuring)\s+.+?[\)\]]?" 
        ]
        
        for pattern in junk_patterns:
            song_title = re.sub(pattern, "", song_title, flags=re.IGNORECASE).strip()
            
        all_artists = [main_artist] + featured_artists
        return all_artists, song_title

    def download_track(self, url):
        try:
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
            
            # STEP 1: Extract Metadata (Info only)
            # Use basic options, no download
            info_opts = {'quiet': True, 'skip_download': True}
            
            artists_list = []
            title = "Unknown"
            genre = "Unknown"
            
            with yt_dlp.YoutubeDL(info_opts) as ydl_info:
                print(f"Fetching metadata for {url}...")
                info = ydl_info.extract_info(url, download=False)
                
                raw_channel = info.get('uploader', 'Unknown Artist')
                raw_title = info.get('title', 'Unknown Title')
                if info.get('categories'):
                    genre = info['categories'][0]

                artists_list, title = self.clean_metadata(raw_channel, raw_title)
                print(f"Metadata -> Artists: {artists_list}, Title: '{title}'")

            # STEP 2: Configure Download with Specific Filename
            main_artist_str = artists_list[0]
            # Sanitize for filesystem
            safe_artist = main_artist_str.replace("/", "_").replace("\\", "_").replace(":", "-")
            safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "-")
            
            final_filename = f"{safe_artist} - {safe_title}.mp3"
            final_path = os.path.join(config.DOWNLOAD_DIR, final_filename)
            
            # Create a NEW options dict for this specific download
            dl_opts = copy.deepcopy(self.base_opts)
            # IMPORTANT: Force filename
            dl_opts['outtmpl'] = os.path.join(config.DOWNLOAD_DIR, f"{safe_artist} - {safe_title}.%(ext)s")
            
            print(f"Starting Download -> {final_path}")
            
            with yt_dlp.YoutubeDL(dl_opts) as ydl_download:
                ydl_download.download([url])
                
            # STEP 3: Verification & Tagging
            if os.path.exists(final_path):
                self._tag_file(final_path, artists_list, title, genre)
                return True, f"Saved: {safe_artist} - {safe_title}"
            else:
                # File might differ slightly?
                print(f"WARNING: File not found at expected path: {final_path}")
                # List dir to debug
                print(f"Dir content: {os.listdir(config.DOWNLOAD_DIR)}")
                return True, "Downloaded, but filepath check failed (check folder)."

        except Exception as e:
            print(f"Download Error: {e}")
            traceback.print_exc()
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
            print(f"Tags updated successfully on {os.path.basename(filepath)}")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
            traceback.print_exc()
