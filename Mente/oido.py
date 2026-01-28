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
    "Un robot escucha una voz humana y percibe su carga emocional.\n\n"
    f"Texto transcrito de la voz:\n\"{texto}\"\n\n"
    f"El archivo de sonido original se encuentra en: {wav_path}\n\n"
    "Responde con EXACTAMENTE TRES enunciados en UNA sola linea, "
    "usando el siguiente formato estricto y sin saltos de linea:\n\n"
    "frase:<texto>\n"
    "descripcion_sonora:<texto>\n"
    "emocion:<una sola palabra>"
    " Reglas:\n"
    "- frase debe expresar una de estas emociones: "
    "[Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]\n"
    "- frase debe reaccionar emocionalmente al texto transcrito, "
    "como si el robot respondiera corporalmente a esa voz\n"
    "- frase debe ser poetica, humana o ludica, retadora\n"
    "- frase debe incluir la traduccion al ingles entre parentesis\n"
    "- descripcion_sonora debe describir como esa emocion se transforma "
    "en una sinfonia generativa en SuperCollider\n"
    "- descripcion_sonora debe mencionar explicitamente el uso del archivo WAV "
    f"({wav_path}) como base sonora para ritmos, melodias o samples\n"
    "- descripcion_sonora debe hablar de ritmo, textura y timbre emocional\n"
    "- emocion debe ser SOLO UNA PALABRA y SOLO puede ser una de: "
    "[Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]\n"
    "- No enumeres, no expliques, no agregues texto extra\n"
    "- No uses acentos ni emojis graficos\n\n"
    "Ejemplo de salida valida:\n"
    f"frase:Tu voz \"{texto}\" me atraviesa con una tristeza suave que pesa en el pecho "
    "(Your voice pierces me with a soft sadness that weighs on my chest). "
    "descripcion_sonora:La grabacion se fragmenta en SuperCollider en capas lentas, "
    f"con estiramientos temporales y resonancias graves, usando el archivo WAV {wav_path} "
    "como fuente principal para drones y ecos respiratorios. "
    "emocion:Tristeza\n"
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
    print("Interpretacion emocional:", analisis)

    # --- Publicar en Redis ---
    data = {
        "sentido": "oido",
        "fecha": datetime.datetime.now().isoformat(),
        "wav_path": wav_path,  #  Nueva clave con la ruta del audio
        "texto_original": texto,
        "respuesta_openai": analisis 
    }

    r.publish("emociones", json.dumps(data, ensure_ascii=False))
    print("Publicado en Redis desde OIDO:", data)

    return texto


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5821)
