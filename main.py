from pytube import YouTube
import os
import time
import ssl
from yt_dlp import YoutubeDL
import subprocess
import openai
from openai import OpenAI
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import cProfile
from collections import deque
from threading import Thread, Lock

# Load your OpenAI API key
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Disable SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

client = OpenAI(api_key=OPENAI_API_KEY)

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
                'preferredquality': '128',  # Optimized for smaller size
            }],
            'outtmpl': 'downloads/transcript',
        }
        with YoutubeDL(options) as ydl:
            ydl.download([url])
        return "downloads/transcript.mp3"

def split_audio_ffmpeg(file_path, chunk_duration_sec=360):  # Reduced chunk size to 6 minutes
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
    print(f"Transcribing {chunk}...")
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

    num_workers = 32  # Increased parallelism
    threads = []

    for _ in range(num_workers):
        thread = Thread(target=pipeline_worker, args=(task_deque, result_list, lock))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    return result_list

def batch_post_process_transcripts(raw_transcriptions):
    system_prompt = """
    You are a helpful assistant. Your task is to correct 
    any spelling discrepancies in the transcribed text. Only add necessary 
    punctuation such as periods, commas, and capitalization, and use only the 
    context provided.
    """
    full_transcription = "\n".join(raw_transcriptions)
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_transcription}
        ]
    )
    return response.choices[0].message.content

def main(url):
    start_time = time.time()

    profiler = cProfile.Profile()
    profiler.enable()

    # Download the video
    video_path = download_video(url)
    
    # Split the audio into chunks using ffmpeg
    chunk_paths = split_audio_ffmpeg(video_path)
    
    # Transcribe the audio chunks using a pipelined approach
    raw_transcriptions = whisper_transcription_pipeline(chunk_paths)
    
    # Post-process the transcription in batch
    corrected_transcription = batch_post_process_transcripts(raw_transcriptions)
    
    # Save the corrected transcription
    with open(f"downloads/{os.path.basename(url)}_transcription.txt", "w") as f:
        f.write(corrected_transcription)

    profiler.disable()
    profiler.dump_stats("transcription_pipeline_profile.prof")
    
    print(f"Transcription for {url} completed. Check downloads/{os.path.basename(url)}_transcription.txt for the output.")
    end_time = time.time()
    elapsed_time = end_time - start_time  # Calculate elapsed time
    print(f"Elapsed time: {elapsed_time:.5f} seconds")

video_1h = "https://www.youtube.com/watch?v=139UPjoq7Kw&ab_channel=JaneStreet"
video_15m = "https://www.youtube.com/watch?v=UhG56kltfP4&ab_channel=QuantaMagazine"
video_30m = "https://www.youtube.com/watch?v=IQqtsm-bBRU&ab_channel=3Blue1Brown"

if __name__ == "__main__":
    main(video_15m)
    main(video_30m)
    main(video_1h)
