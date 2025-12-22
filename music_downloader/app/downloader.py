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
                        # PROPOSE METADATA on Search Result
                        artists, title = self.clean_metadata(video.get('uploader'), video.get('title'))
                        
                        return {
                            'found': True,
                            'title': video.get('title'), # Original Title
                            'uploader': video.get('uploader'), # Original Channel
                            'id': video.get('id'),
                            'url': video.get('webpage_url') or video.get('url'),
                            'thumbnail': video.get('thumbnail'),
                            # Proposal for Frontend Editor
                            'proposal_artists': artists,
                            'proposal_title': title
                        }
                    else:
                        return {'found': False, 'message': 'No entries found.'}
                elif isinstance(result, dict) and 'title' in result:
                     artists, title = self.clean_metadata(result.get('uploader'), result.get('title'))
                     return {
                        'found': True,
                        'title': result.get('title'),
                        'uploader': result.get('uploader'),
                        'id': result.get('id'),
                        'url': result.get('webpage_url') or result.get('url'),
                        'thumbnail': result.get('thumbnail'),
                        'proposal_artists': artists,
                        'proposal_title': title
                    }
                else:
                    return {'found': False}
        except Exception as e:
            print(f"Search Error: {e}")
            return {'found': False, 'error': str(e)}

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

    def download_track(self, url, manual_artists=None, manual_title=None):
        try:
            if not os.path.exists(config.DOWNLOAD_DIR):
                os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
            
            # Phase 1: Get Metadata (only to get Genre if not manually supplied)
            # Or just rely on Manual overrides if provided
            ydl_opts_info = {
                'quiet': True, 
                'skip_download': True,
                'format': 'bestaudio/best',
            }
            
            artists_list = manual_artists if manual_artists else ["Unknown"]
            title = manual_title if manual_title else "Unknown"
            genre = "Unknown"
            
            # If we don't have manual input, we would fetch it. 
            # But the new flow sends manual input ALWAYS (or user confirms auto).
            # We still need info for Genre.
            
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                print(f"Fetching metadata for {url}...")
                info = ydl.extract_info(url, download=False)
                
                # If manual metadata wasn't provided (fallback), calculate it
                if not manual_artists or not manual_title:
                     raw_channel = info.get('uploader', 'Unknown Artist')
                     raw_title = info.get('title', 'Unknown Title')
                     auto_artists, auto_title = self.clean_metadata(raw_channel, raw_title)
                     if not manual_artists: artists_list = auto_artists
                     if not manual_title: title = auto_title

                if info.get('categories') and isinstance(info['categories'], list) and len(info['categories']) > 0:
                    genre = info['categories'][0]
                
                print(f"Final Metadata -> Artists: {artists_list}, Title: '{title}', Genre: '{genre}'")
                
            # Phase 2: Download
            filename_artist_str = artists_list[0]
            
            final_filename = f"{filename_artist_str} - {title}.mp3".replace("/", "_").replace("\\", "_")
            
            dl_opts = copy.deepcopy(self.base_opts) # Safe Deep Copy
            dl_opts['outtmpl'] = os.path.join(config.DOWNLOAD_DIR, f"{filename_artist_str} - {title}.%(ext)s")
            
            print(f"Starting Download -> {final_filename}")
            
            with yt_dlp.YoutubeDL(dl_opts) as ydl_dl:
                ydl_dl.download([url])
                
            final_path = os.path.join(config.DOWNLOAD_DIR, final_filename)
            
            if os.path.exists(final_path):
                self._tag_file(final_path, artists_list, title, genre)
                return True, f"Saved & Tagged: {filename_artist_str} - {title}"
            else:
                return True, f"Downloaded (Check folder): {filename_artist_str} - {title}"

        except Exception as e:
            print(f"Download Error: {e}")
            import traceback
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
            print(f"Tags updated: Artists={artists_list}, Title='{title}'")
            
        except Exception as e:
            print(f"Tagging Error: {e}")
