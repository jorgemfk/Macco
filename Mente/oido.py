from flask import Flask, request, jsonify
import base64, os
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key="TU_API_KEY_DE_OPENAI")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json()
    filename = data["filename"]
    filepath = os.path.join(UPLOAD_DIR, filename)

    # Guardar el archivo WAV recibido
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(data["data"]))
    print(f"Archivo {filename} recibido y guardado en {filepath}")

    # Enviar a OpenAI para transcripción
    with open(filepath, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )

    texto = transcript.text
    print("Transcripción:", texto)

    return jsonify({"status": "ok", "text": texto})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5821)
