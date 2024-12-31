from flask import Flask, request, Response, send_from_directory, jsonify
from werkzeug.exceptions import ClientDisconnected
from app.transcription import generate_transcription_steps, benchmark_transcription, cleanup_files

app = Flask(__name__, static_folder='static')

@app.route('/')
def serve_client():
    return send_from_directory(app.static_folder, 'client.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    youtube_url = request.form.get('url', '')
    if not youtube_url:
        return "No URL provided.", 400
        
    try:
        return Response(generate_transcription_steps(youtube_url), mimetype='text/plain')
    except ClientDisconnected:
        cleanup_files()
        return "Transcription cancelled", 499
    except Exception as e:
        cleanup_files()
        return str(e), 500

@app.route('/transcribe_benchmark', methods=['POST'])
def transcribe_benchmark():
    youtube_url = request.form.get('url', '')
    if not youtube_url:
        return "No URL provided.", 400
        
    try:
        result = benchmark_transcription(youtube_url)
        return jsonify(result)
    except Exception as e:
        cleanup_files()
        return str(e), 500

if __name__ == "__main__":
    app.run(port=8080, debug=True)