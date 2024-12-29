from pytube import YouTube
import os
from yt_dlp import YoutubeDL

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