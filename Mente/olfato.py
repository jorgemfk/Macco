from flask import Flask, request, jsonify
import redis, json, datetime, unicodedata

app = Flask(__name__)
r = redis.Redis(host='localhost', port=6379, db=0)

def sanitize_text(text):
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def generar_prompt_sc(emocion, nivel, raw):
    if nivel == "bajo":
        textura = "sonidos suaves, filtros pasa bajos y respiraciones lentas"
    elif nivel == "medio":
        textura = "ritmos pulsantes, capas analogas y modulaciones lentas"
    else:
        textura = "texturas densas, distorsion controlada y ritmos agresivos"

    if emocion == "Frenetica":
        ritmo = "tempo alto, glitches y impulsos caoticos"
    elif emocion == "Calma":
        ritmo = "tempo lento, drones largos y silencios amplios"
    else:
        ritmo = "tempo medio, estructuras estables"

    return (
        f"SuperCollider debe generar una composicion {emocion.lower()} "
        f"basada en el olfato. El nivel de contaminacion es {nivel} "
        f"(raw {raw}). Usar {ritmo} con {textura}."
    )

@app.route("/olfato", methods=["POST"])
def olfato():
    data = request.json

    raw = data.get("raw135", 0)
    velocidad = data.get("velocidad", "estable")
    nivel = data.get("nivel", "medio")

    if velocidad == "rapido+":
        emocion = "Frenetica"
    elif velocidad == "rapido-":
        emocion = "Calma"
    else:
        emocion = "Neutral"

    texto_emocional = f"Siento {emocion}, el aire me habla a traves del olfato. (o_o)"
    texto_sc = generar_prompt_sc(emocion, nivel, raw)

    payload = {
        "sentido": "olfato",
        "fecha": datetime.datetime.now().isoformat(),
        "raw135": raw,
        "velocidad": velocidad,
        "nivel": nivel,
        "respuesta_openai": sanitize_text(texto_emocional + "\n" + texto_sc)
    }

    r.publish("emociones", json.dumps(payload, ensure_ascii=False))
    print("Publicado en Redis desde OLFATO:", payload)

    return jsonify(payload)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5823)

