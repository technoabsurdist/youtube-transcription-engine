from flask import Flask, request, Response, send_from_directory
from app.transcription import generate_transcription_steps

app = Flask(__name__, static_folder='static')

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
