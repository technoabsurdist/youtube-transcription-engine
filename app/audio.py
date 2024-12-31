import os
import subprocess
from typing import List, Tuple, Dict, Optional
import threading
from queue import Queue
from pathlib import Path
from yt_dlp import YoutubeDL

class ChunkProcessor:
    def __init__(self, output_dir: str, chunk_duration: int = 180):
        self.output_dir = Path(output_dir)
        self.chunk_duration = chunk_duration
        self.processed_chunks = set()
        self.download_complete = threading.Event()
        self.chunk_queue: Queue[str] = Queue()
        self.error: Optional[Exception] = None
        
    def download_and_split(self, url: str) -> None:
        """Download and split audio in a separate thread."""
        try:
            ytdlp_cmd = [
                'yt-dlp',
                '-f', 'worstaudio[ext=m4a]',  
                '--no-continue',  
                '--rm-cache-dir',  
                '-o', '-',  
                url
            ]
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', 'pipe:0',  
                '-ar', '16000',   
                '-ac', '1',       
                '-f', 'segment',
                '-segment_time', str(self.chunk_duration),
                f'{self.output_dir}/chunk_%03d.mp3'
            ]
            
            ytdlp_process = subprocess.Popen(
                ytdlp_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10 * 1024 * 1024  # 10MB buffer
            )
            
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=ytdlp_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10 * 1024 * 1024  # 10MB buffer
            )
            
            if ytdlp_process.stdout:
                ytdlp_process.stdout.close()
            
            ffmpeg_stderr = ffmpeg_process.communicate()[1]
            if ffmpeg_process.returncode != 0:
                raise Exception(f"FFmpeg error: {ffmpeg_stderr.decode()}")
            
            if ytdlp_process.wait() != 0:
                raise Exception(f"yt-dlp error: {ytdlp_process.stderr.read().decode()}")
            
            chunk_files = sorted(self.output_dir.glob('chunk_*.mp3'))
            if not chunk_files:
                raise Exception("No audio chunks were created")
                
            for chunk_file in chunk_files:
                self.chunk_queue.put(str(chunk_file))
                
        except Exception as e:
            self.error = e
        finally:
            self.download_complete.set()

def create_streaming_pipeline(url: str, chunk_duration_sec: int = 180) -> Tuple[List[str], Tuple[str, str, int]]:
    """
    Creates an optimized streaming pipeline that downloads YouTube audio and splits it into chunks.
    Returns a list of chunk paths and video metadata (title, author, length).
    """
    # Create output directory
    output_dir = "downloads/chunks"
    os.makedirs(output_dir, exist_ok=True)
    
    # First, get video metadata
    with YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title')
        author = info.get('uploader')
        length = info.get('duration')
    
    # Initialize the chunk processor
    processor = ChunkProcessor(output_dir, chunk_duration_sec)
    
    # Start download and split process in a separate thread
    download_thread = threading.Thread(
        target=processor.download_and_split,
        args=(url,)
    )
    download_thread.start()
    
    # Wait for completion
    processor.download_complete.wait()
    
    # Check for errors
    if processor.error:
        raise processor.error
    
    # Get all chunk paths
    chunk_paths = []
    while not processor.chunk_queue.empty():
        chunk_paths.append(processor.chunk_queue.get())
    
    if not chunk_paths:
        raise Exception("No audio chunks were created")
    
    return chunk_paths, (title, author, length)

def cleanup_files():
    """
    Clean up downloaded files and chunks.
    """
    chunks_dir = "downloads/chunks"
    if os.path.exists(chunks_dir):
        for file in os.listdir(chunks_dir):
            try:
                os.remove(os.path.join(chunks_dir, file))
            except OSError:
                pass
        try:
            os.rmdir(chunks_dir)
        except OSError:
            pass