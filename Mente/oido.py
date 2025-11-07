from flask import Flask, request
import openai, tempfile, base64, os

app = Flask(__name__)

# Configura tu clave de OpenAI

@app.route("/upload", methods=["POST"])
def upload():
    wav_path = tempfile.mktemp(suffix=".wav")
    with open(wav_path, "wb") as f:
        f.write(request.data)
    print(f"Archivo recibido ({len(request.data)} bytes):", wav_path)

    # Enviar a OpenAI Whisper
    with open(wav_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    texto = transcript.strip()
    print("Transcripción:", texto)
    return texto

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5821)
