from flask import Flask, request
import openai, tempfile, base64, os
import unicodedata

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024 
# Configura tu clave de OpenAI
def sanitize_text(text: str) -> str:
    """Quita acentos, tildes y caracteres no ASCII."""
    nfkd_form = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return text

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
    texto = sanitize_text(texto)
    print("Transcripción:", texto)
    return texto

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5821)
