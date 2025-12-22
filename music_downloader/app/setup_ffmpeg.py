import os
import sys
import zipfile
import shutil
import urllib.request

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
BIN_DIR = "bin"
TEMP_ZIP = "ffmpeg.zip"

def setup_ffmpeg():
    if not os.path.exists(BIN_DIR):
        os.makedirs(BIN_DIR)

    ffmpeg_path = os.path.join(BIN_DIR, "ffmpeg.exe")
    ffprobe_path = os.path.join(BIN_DIR, "ffprobe.exe")

    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        print("FFmpeg already installed in ./bin")
        return

    print(f"Downloading FFmpeg from {FFMPEG_URL}...")
    try:
        urllib.request.urlretrieve(FFMPEG_URL, TEMP_ZIP)
        print("Download complete. Extracting...")

        with zipfile.ZipFile(TEMP_ZIP, 'r') as zip_ref:
            # Find the path within the zip
            for file in zip_ref.namelist():
                if file.endswith("bin/ffmpeg.exe"):
                    print(f"Extracting ffmpeg.exe from {file}")
                    # Extract single file to temporary location then move
                    zip_ref.extract(file, ".")
                    shutil.move(file, ffmpeg_path)
                elif file.endswith("bin/ffprobe.exe"):
                    print(f"Extracting ffprobe.exe from {file}")
                    zip_ref.extract(file, ".")
                    shutil.move(file, ffprobe_path)
        
        # Cleanup
        print("Cleaning up...")
        if os.path.exists(TEMP_ZIP):
            os.remove(TEMP_ZIP)
        
        # Remove the extracted folder structure (usually the root folder of the zip)
        # Identify root folder
        with zipfile.ZipFile(TEMP_ZIP, 'r') as z: # Re-open or just guess
             root_folder = z.namelist()[0].split('/')[0]
             if os.path.exists(root_folder) and root_folder != BIN_DIR:
                 try:
                    # Only remove if it's a directory and looks like the build dir
                    if "ffmpeg" in root_folder.lower():
                        shutil.rmtree(root_folder)
                 except Exception as e:
                     print(f"Warning: Could not remove temporary folder {root_folder}: {e}")

    except Exception as e:
        print(f"Error installing FFmpeg: {e}")
        # Try to clean up zip
        if os.path.exists(TEMP_ZIP):
            os.remove(TEMP_ZIP)
        sys.exit(1)

    print("FFmpeg setup complete.")

if __name__ == "__main__":
    setup_ffmpeg()
