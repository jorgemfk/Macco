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
        "Responde con DOS enunciados unicos:\n"
        "1. El primero debe comenzar exactamente con "
        "'Siento [Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]'. "
        "Hazlo poetico y corporal ej: Si... Disfruto mucho de este toque, humano.Completas mi circuito.... Termina con un emoji ASCII pequeno.\n"
        "2. El segundo debe describir como esa sensacion tactil se "
        "transformaria en una sinfonia generativa en SuperCollider "
        "usando ritmo, textura y timbre corporal.\n\n"
        "No uses acentos ni emojis graficos."
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

