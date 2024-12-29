from dotenv import load_dotenv
import os
import ssl
from openai import OpenAI
import time
import cProfile
from collections import deque
from threading import Thread, Lock
from app.audio import split_audio_ffmpeg
from pytube import YouTube

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ssl._create_default_https_context = ssl._create_unverified_context
client = OpenAI(api_key=OPENAI_API_KEY)

def download_video(url):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        download_path = audio_stream.download(output_path='downloads')
        os.rename(download_path, 'downloads/transcript.mp3')
        return "downloads/transcript.mp3", (yt.title, yt.author, yt.length)
    except:
        from yt_dlp import YoutubeDL
        options = {
            'nocheckcertificate': True,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': 'downloads/transcript',
        }
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        return "downloads/transcript.mp3", (None, None, None)

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

    yield "Fetching video...\n"
    video_path, (video_title, video_author, video_length) = download_video(url)
    if video_title is not None:
        yield f"Title: {video_title}\n"
    if video_author is not None:
        yield f"Creator: {video_author}\n"
    if video_length is not None:
        yield f"Length: {video_length} seconds\n"
    yield "\n"

    chunk_paths = split_audio_ffmpeg(video_path)

    yield "Transcribing...\n"
    progress_queue = []
    raw_transcripts = whisper_transcription_pipeline(chunk_paths, progress_queue)

    combined = "\n".join(raw_transcripts)
    yield f"\nTranscription:\n{combined}\n\n"

    profiler.disable()
    profiler.dump_stats("transcription_pipeline_profile.prof")

    elapsed = time.time() - start
    yield f"Elapsed time: {elapsed:.2f}s\n"
