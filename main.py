import os
import time
import ssl
import cProfile
import subprocess
from pytube import YouTube
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
from collections import deque
from threading import Thread, Lock
from flask import Flask, request, Response, send_from_directory
import openai
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ssl._create_default_https_context = ssl._create_unverified_context
client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__, static_folder='static')

def download_video(url):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        download_path = audio_stream.download(output_path='downloads')
        os.rename(download_path, 'downloads/transcript.mp3')
        return "downloads/transcript.mp3"
    except:
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
        return "downloads/transcript.mp3"

def split_audio_ffmpeg(file_path, chunk_duration_sec=360):
    output_dir = "downloads/chunks"
    os.makedirs(output_dir, exist_ok=True)
    command = [
        "ffmpeg", "-i", file_path,
        "-f", "segment", "-segment_time", str(chunk_duration_sec),
        "-c", "copy", f"{output_dir}/chunk_%03d.mp3"
    ]
    subprocess.run(command, check=True)
    return [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".mp3")]

def transcribe_chunk(chunk):
    with open(chunk, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    return transcription.text

def pipeline_worker(task_deque, result_list, lock, progress_queue):
    while True:
        lock.acquire()
        if not task_deque:
            lock.release()
            break
        chunk_path = task_deque.popleft()
        lock.release()
        progress_queue.append(f"Transcribing {os.path.basename(chunk_path)}...")
        result = transcribe_chunk(chunk_path)
        lock.acquire()
        result_list.append(result)
        lock.release()

def whisper_transcription_pipeline(chunk_paths, progress_queue):
    task_deque = deque(chunk_paths)
    result_list = []
    lock = Lock()
    threads = []
    for _ in range(32):
        thread = Thread(target=pipeline_worker, args=(task_deque, result_list, lock, progress_queue))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    return result_list

def generate_transcription_steps(url):
    profiler = cProfile.Profile()
    profiler.enable()
    start = time.time()
    yield "Starting transcription...\n"

    yield "Downloading video...\n"
    video_path = download_video(url)
    yield "Video downloaded.\n"

    yield "Splitting audio...\n"
    chunk_paths = split_audio_ffmpeg(video_path)
    yield f"Split into {len(chunk_paths)} chunks.\n"

    yield "Transcribing...\n"
    progress_queue = []
    raw_transcripts = whisper_transcription_pipeline(chunk_paths, progress_queue)
    for msg in progress_queue:
        yield msg + "\n"

    yield "All chunks transcribed.\n"
    combined = "\n".join(raw_transcripts)
    yield f"Full transcription:\n{combined}\n"

    profiler.disable()
    profiler.dump_stats("transcription_pipeline_profile.prof")

    elapsed = time.time() - start
    yield f"Elapsed time: {elapsed:.2f}s\n"

@app.route('/')
def serve_client():
    return send_from_directory(app.static_folder, 'client.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    youtube_url = request.form.get('url', '')
    if not youtube_url:
        return "No URL provided.", 400
    return Response(generate_transcription_steps(youtube_url), mimetype='text/plain')

if __name__ == "__main__":
    app.run(debug=True)
