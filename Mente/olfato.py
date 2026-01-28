from flask import Flask, request, jsonify
import redis, json, datetime, os, unicodedata
import openai

app = Flask(__name__)

# =============================
# REDIS
# =============================
r = redis.Redis(host='localhost', port=6379, db=0)

# =============================
# OPENAI
# =============================
openai.api_key = os.getenv("OPENAI_API_KEY")

# =============================
# UTILS
# =============================
def sanitize_text(text):
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

# =============================
# PROMPT GPT – OLFATO
# =============================
def analyze_olfato(velocidad, nivel, raw):
    descripcion = (
        f"Velocidad del estimulo olfativo: {velocidad}. "
        f"Nivel de intensidad: {nivel}. "
        f"Valor crudo del sensor: {raw}. una intensidad alta es menos calidad en aire, una velocidad rapida es un golpe de perfume "
    )

    prompt = (
        "Un robot percibe un estimulo a traves del sentido del olfato.\n\n"
        f"Descripcion del estimulo:\n\"{descripcion}\"\n\n"
        "Responde con EXACTAMENTE TRES enunciados en UNA sola linea, "
        "usando el siguiente formato estricto y sin saltos de linea:\n\n"
        "frase:<texto>\n"
        "descripcion_sonora:<texto>\n"
        "emocion:<una sola palabra>"
        " Reglas:\n"
        "- frase debe expresar una de estas emociones: "
        "[Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]\n"
        "- frase debe ser poetica y corporal\n"
        "- frase debe incluir la traduccion al ingles entre parentesis\n"
        "- descripcion_sonora debe describir como el estimulo olfativo "
        "se transforma en una sinfonia generativa en SuperCollider "
        "usando ritmo, textura y timbre corporal\n"
        "- emocion debe ser SOLO UNA PALABRA y SOLO puede ser una de: "
        "[Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]\n"
        "- No enumeres, no expliques, no agregues texto extra\n"
        "- No uses acentos ni emojis graficos\n\n"
        "Ejemplo de salida valida:\n"
        "frase:Un aroma inesperado irrumpe en mi interior como una sacudida invisible "
        "(An unexpected scent bursts inside me like an invisible jolt). "
        "descripcion_sonora:El aire se convierte en pulsos granulares con filtrado dinamico "
        "y capas respiratorias que se expanden y contraen. "
        "emocion:Sorpresa\n"
        "Ahora genera tu respuesta."
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )

    return sanitize_text(response.choices[0].message.content.strip())

# =============================
# ENDPOINT
# =============================
@app.route("/olfato", methods=["POST"])
def olfato():
    data = request.json or {}

    raw = data.get("raw135", 0)
    velocidad = data.get("velocidad", "estable")
    nivel = data.get("nivel", "medio")

    respuesta = analyze_olfato(velocidad, nivel, raw)

    payload = {
        "sentido": "olfato",
        "fecha": datetime.datetime.now().isoformat(),
        "raw135": raw,
        "velocidad": velocidad,
        "nivel": nivel,
        "respuesta_openai": respuesta
    }

    r.publish("emociones", json.dumps(payload, ensure_ascii=False))
    print("Publicado en Redis desde OLFATO:", payload)

    return jsonify(payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5823)
