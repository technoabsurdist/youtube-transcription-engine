from dotenv import load_dotenv
import os
import ssl
from openai import OpenAI
import time
import cProfile
from dotenv import load_dotenv
from collections import deque
from threading import Thread, Lock
from app.download import download_video
from app.audio import split_audio_ffmpeg

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

def generate_transcription_steps(url):
    profiler = cProfile.Profile()
    profiler.enable()
    start = time.time()
    # yield "Starting transcription...\n"

    yield "Fetching video...\n"
    video_path = download_video(url)

    chunk_paths = split_audio_ffmpeg(video_path)

    yield "Transcribing...\n"
    progress_queue = []
    raw_transcripts = whisper_transcription_pipeline(chunk_paths, progress_queue)

    combined = "\n".join(raw_transcripts)
    yield f"\n\nFull transcription:\n{combined}\n\n"

    yield "\n\n"

    profiler.disable()
    profiler.dump_stats("transcription_pipeline_profile.prof")

    elapsed = time.time() - start
    yield f"\n\n\nElapsed time: {elapsed:.2f}s\n"