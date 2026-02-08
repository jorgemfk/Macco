from flask import Flask, request, jsonify
import redis, json, datetime, os
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
# MAPA DE PINES  PROMPTS
# =============================
TACTO_PROMPTS = {
    21: "Un toque suave en el costado derecho, como una caricia curiosa.",
    20: "Un toque frontal, directo y atento, buscando respuesta.",
}

def analyze_tacto(pin, descripcion):
    prompt = (
        f"Un robot siente un estimulo por el sentido del tacto.\n\n"
        f"Descripcion del toque:\n\"{descripcion}\"\n\n"
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
        "- descripcion_sonora debe describir como la sensacion tactil "
        "se transforma en una sinfonia generativa en SuperCollider "
        "usando ritmo, textura y timbre corporal\n"
        "- emocion debe ser SOLO UNA PALABRA y SOLO puede ser una de: "
        "[Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]\n"
        "- No enumeres, no expliques, no agregues texto extra\n"
        "- No uses acentos ni emojis graficos\n\n"

        "Ejemplo de salida valida:\n"
        "frase:Siento sorpresa al recibir ese toque, como un pulso que despierta mi cuerpo "
        "(I feel surprise at receiving that touch, like a pulse awakening my body). "
        "descripcion_sonora:La presion se convierte en una textura ritmica de pulsos lentos "
        "y resonancias suaves que crecen en capas. "
        "emocion:Sorpresa\n"

        "Ahora genera tu respuesta."
    )


    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )

    return response.choices[0].message.content.strip()

@app.route("/touch", methods=["POST"])
def touch():
    data = request.json
    pin = int(data.get("pin", -1))

    descripcion = TACTO_PROMPTS.get(
        pin,
        "Un contacto indefinido, ambiguo, electrico."
    )

    respuesta = analyze_tacto(pin, descripcion)

    payload = {
        "sentido": "tacto",
        "pin": pin,
        "fecha": datetime.datetime.now().isoformat(),
        "descripcion": descripcion,
        "respuesta_openai": respuesta
    }

    r.publish("emociones", json.dumps(payload, ensure_ascii=False))
    print("Publicado en Redis desde TACTO:", payload)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5822)

