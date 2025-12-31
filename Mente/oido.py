from flask import Flask, request
import openai, tempfile, os, redis, json, unicodedata, datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

# Configura Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Configura OpenAI (usa tu API key en variable de entorno)
openai.api_key = os.getenv("OPENAI_API_KEY")


def sanitize_text(text: str) -> str:
    """Quita acentos, tildes y caracteres no ASCII."""
    nfkd_form = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return text


def analyze_with_openai(texto, wav_path):
    """Analiza el texto transcrito y genera respuesta emocional tipo DJ."""
    prompt = (
        f"Analiza el siguiente texto transcrito de una voz humana:\n\n"
        f"\"{texto}\"\n\n"
        f"El archivo de sonido original se encuentra en: {wav_path}\n\n"
        "Debes responder con DOS enunciados unicos:\n"
        "1. El primer enunciado debe comenzar exactamente con 'Siento [Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]' "
        "(elige solo una de estas emociones de acuerdo al texto interpretado por el sonido). "
        "Haz que suene humano, divertido o poetico, trata de contestar el texto transcrito de manera emocional "
        "Termina el enunciado con un emoji ASCII pequeno adecuado a la emocion.\n"
        "2. El segundo enunciado debe describir como esa emocion se convertira en una sinfonia generativa en SuperCollider, "
        "mencionando ritmo, textura, instrumentos o tono, y debe incluir explicitamente el uso del archivo WAV "
        f"({wav_path}) como base sonora para cada melodia o sample. "
        #"Tambien debe mencionar el genero segun la emocion: "
        #"Tristeza-dark_wave, Felicidad-Synth_pop, Enojo-noise, Neutral-Techno, Asco-Gothic_techno, "
        #"Miedo-dark_ambient, Sorpresa-Techno_industrial.\n\n"
        "No uses acentos, emojis graficos ni menciones de IA o codigo. Solo texto plano.\n\n"
        "Ejemplo:\n"
        "Siento Tristeza, como si mi corazon se undiera en el olvido eterno. (U_U)\n"
        "Creare una sinfonia oscura ambiental con sonido melancolico y a menudo introspectivo, utilizando tonos menores y sintetizadores, "
        "usando el archivo WAV como fuente para los ecos de la melodia.\n\n"
        "Ahora genera tu respuesta."
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )

    return response.choices[0].message.content.strip()


@app.route("/upload", methods=["POST"])
def upload():
    """Recibe audio WAV, lo transcribe, interpreta y publica en Redis."""
    wav_path = tempfile.mktemp(suffix=".wav")
    with open(wav_path, "wb") as f:
        f.write(request.data)
    print(f"Archivo recibido ({len(request.data)} bytes):", wav_path)

    # --- Transcripción con Whisper ---
    with open(wav_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file,
            response_format="text"
        )

    texto = transcript.strip()
    texto = sanitize_text(texto)
    print("Transcripción:", texto)

    # --- Análisis emocional tipo DJ + referencia al WAV ---
    analisis = analyze_with_openai(texto, wav_path)
    analisis = sanitize_text(analisis)
    print("Interpretación emocional:", analisis)

    # --- Publicar en Redis ---
    data = {
        "sentido": "oido",
        "fecha": datetime.datetime.now().isoformat(),
        "wav_path": wav_path,  #  Nueva clave con la ruta del audio
        "texto_original": texto,
        "respuesta_openai": analisis + wav_path
    }

    r.publish("emociones", json.dumps(data, ensure_ascii=False))
    print("Publicado en Redis desde OIDO:", data)

    return texto


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5821)
