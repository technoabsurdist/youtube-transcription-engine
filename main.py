from flask import Flask, request, Response, stream_with_context, send_from_directory
from pytube import YouTube
import os
import subprocess
import openai
from openai import OpenAI
from dotenv import load_dotenv
from collections import deque
from threading import Thread, Lock

# Load your OpenAI API key
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Disable SSL verification
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

def download_video(url):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        download_path = audio_stream.download(output_path='downloads')
        os.rename(download_path, 'downloads/transcript.mp3')
        return "downloads/transcript.mp3"
    except:
        with subprocess.Popen(["yt-dlp", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            proc.communicate()
        return "downloads/transcript.mp3"

def split_audio_ffmpeg(file_path, chunk_duration_sec=360): # 6m chunk size
    output_dir = "downloads/chunks"
    os.makedirs(output_dir, exist_ok=True)
    command = [
        "ffmpeg",
        "-i", file_path,
        "-f", "segment",
        "-segment_time", str(chunk_duration_sec),
        "-c", "copy",
        f"{output_dir}/chunk_%03d.mp3"
    ]
    subprocess.run(command, check=True)
    return [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".mp3")]

def transcribe_chunk(chunk):
    with open(chunk, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        return transcription.text

def pipeline_worker(task_deque, result_list, lock):
    while True:
        lock.acquire()
        if not task_deque:
            lock.release()
            break
        chunk_path = task_deque.popleft()
        lock.release()
        result = transcribe_chunk(chunk_path)
        lock.acquire()
        result_list.append(result)
        lock.release()

def whisper_transcription_pipeline(chunk_paths):
    task_deque = deque(chunk_paths)
    result_list = []
    lock = Lock()

    num_workers = 32
    threads = []

    for _ in range(num_workers):
        thread = Thread(target=pipeline_worker, args=(task_deque, result_list, lock))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    return result_list


@app.route('/')
def index():
    return send_from_directory('.', 'client.html')


@app.route('/transcribe', methods=['POST'])
def transcribe():
    youtube_url = request.json.get('youtube_url')
    if not youtube_url:
        return {"error": "youtube_url parameter is required"}, 400

    def generate():
        try:
            # Step 1: Download the video
            yield "Downloading video...\n"
            video_path = download_video(youtube_url)

            # Step 2: Split the audio into chunks
            yield "Splitting audio...\n"
            chunk_paths = split_audio_ffmpeg(video_path)

            # Step 3: Transcribe chunks and stream results
            yield "Transcribing audio...\n"
            for chunk_path in chunk_paths:
                transcription = transcribe_chunk(chunk_path)
                yield transcription + "\n"
        except Exception as e:
            yield f"Error: {str(e)}\n"

    return Response(stream_with_context(generate()), content_type='text/plain')

if __name__ == '__main__':
    app.run(debug=True)
