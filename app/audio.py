import os
import subprocess

def split_audio_ffmpeg(file_path, chunk_duration_sec=360):
    output_dir = "downloads/chunks"
    os.makedirs(output_dir, exist_ok=True)
    command = [
        "ffmpeg", "-i", file_path,
        "-f", "segment", "-segment_time", str(chunk_duration_sec),
        "-c", "copy", f"{output_dir}/chunk_%03d.mp3"
    ]
    subprocess.run(command, check=True)
    return sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".mp3")])