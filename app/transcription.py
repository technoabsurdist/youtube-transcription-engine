from dotenv import load_dotenv
import os
import ssl
from openai import OpenAI
import time
from collections import deque
from threading import Thread, Lock
from app.audio import create_streaming_pipeline, cleanup_files

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ssl._create_default_https_context = ssl._create_unverified_context
client = OpenAI(api_key=OPENAI_API_KEY)

def transcribe_chunk(chunk):
    with open(chunk, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    return transcription.text

def pipeline_worker(task_deque, result_dict, lock, progress_queue):
    while True:
        lock.acquire()
        if not task_deque:
            lock.release()
            break
        index, chunk_path = task_deque.popleft()
        lock.release()

        progress_queue.append(f"Transcribing {os.path.basename(chunk_path)}...")
        result = transcribe_chunk(chunk_path)
        lock.acquire()
        result_dict[index] = result
        lock.release()

def whisper_transcription_pipeline(chunk_paths, progress_queue):
    task_deque = deque((i, p) for i, p in enumerate(chunk_paths))
    result_dict = {}
    lock = Lock()
    threads = []
    for _ in range(16):
        thread = Thread(target=pipeline_worker, args=(task_deque, result_dict, lock, progress_queue))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    return [result_dict[i] for i in range(len(chunk_paths))]

def generate_transcription_steps(url: str):
    start = time.time()
    
    cleanup_files()
    
    try:
        # Use streaming pipeline instead of separate download and split
        chunk_paths, (video_title, video_author, video_length) = create_streaming_pipeline(url)
        
        if video_title is not None:
            yield f"Title: {video_title}\n"
        if video_author is not None:
            yield f"Creator: {video_author}\n"
        if video_length is not None:
            yield f"Length: {video_length} seconds\n"
        yield "\n"
        
        yield "Transcribing...\n"
        progress_queue = []
        raw_transcripts = whisper_transcription_pipeline(chunk_paths, progress_queue)
        
        elapsed = time.time() - start
        yield f"Elapsed time: {elapsed:.2f}s\n"
        
        combined = "\n".join(raw_transcripts)
        yield f"\n{combined}\n\n"
        
    finally:
        cleanup_files()