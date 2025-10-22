from flask import Flask, request, jsonify
from tinydb import TinyDB, Query
from openai import OpenAI
import redis, json, time, datetime, os

# ---------------------------
# Clase Vista
# ---------------------------

class Vista:
    def __init__(self):
        # --- Configuración base ---
        self.app = Flask(__name__)
        self.client = OpenAI()
        self.db = TinyDB("emociones_diarias.json")
        self.r = redis.Redis(host='localhost', port=6379, db=0)
        self.last_request_time = None

        self.emociones = ["Enojo", "Asco", "Miedo", "Feliz", "Triste", "Sorpresa", "Neutral"]

        # --- Definir ruta principal ---
        self.app.add_url_rule("/emociones", "emociones", self.handle_emociones, methods=["POST"])

    # ---------------------------
    # Métodos internos
    # ---------------------------

    def _get_today_record(self):
        """Obtiene o crea el registro diario en TinyDB."""
        today = datetime.date.today().isoformat()
        Emocion = Query()
        result = self.db.search(Emocion.fecha == today)
        if not result:
            record = {
                "fecha": today,
                "ultima_actualizacion": None,
                "emociones": {e: 0 for e in self.emociones}
            }
            self.db.insert(record)
            return record
        return result[0]

    def _update_today_record(self, emocion_data):
        """Actualiza conteos e inserta hora de última invocación."""
        today = datetime.date.today().isoformat()
        Emocion = Query()
        record = self._get_today_record()

        # Actualizar conteos
        for e, c in emocion_data.items():
            if e in self.emociones:
                record["emociones"][e] += c

        # Actualizar hora
        record["ultima_actualizacion"] = datetime.datetime.now().isoformat()

        # Guardar cambios
        self.db.update(record, Emocion.fecha == today)
        return record

    def _get_time_since_last_request(self):
        """Devuelve segundos desde la última petición."""
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return None
        now = time.time()
        delta = now - self.last_request_time
        self.last_request_time = now
        return delta

    def _analyze_with_openai(self, totals):
        """Envía totales diarios a OpenAI."""

        # Emoji ASCII por emoci�n
        ascii_emojis = {
            "Enojo": "(>_<)",
            "Asco": "(*_*)",
            "Miedo": "(0_0;)",
            "Feliz": "(^_^)",
            "Triste": "(T_T)",
            "Sorpresa": "(@_@)",
            "Neutral": "(-_-)"
        }

        """Genera el mood (estado emocional) y su instruccion musical en lenguaje natural."""
        prompt = (
            "Analiza las siguientes emociones detectadas hoy en el publico:\n\n"
            + "\n".join([f"{e}: {totals['emociones'][e]}" for e in self.emociones])
            + "\n\n"
            "Debes responder con DOS enunciados unicos:\n"
            "1. El primer enunciado debe comenzar exactamente con 'Siento [Enojo, Asco, Miedo, Feliz, Triste, Sorpresa, Neutral]' "
            "(elige solo una de estas emociones). Haz que suene humano, divertido o poetico, como si fueras un DJ que siente la energia del publico. "
            "Termina el enunciado con un emoji ASCII pequeno adecuado a la emocion.\n"
            "2. El segundo enunciado debe describir como esa emocion se convertira en una sinfonia generativa en SuperCollider, "
            "mencionando ritmo, textura, instrumentos o tono.\n\n"
            "No uses acentos, emojis graficos ni menciones de IA o codigo. Solo texto plano.\n\n"
            "Ejemplo:\n"
            "Siento Feliz, como si las notas saltaran en una pista de baile. (^_^)\n"
            "Creare una sinfonia brillante con arpegios ascendentes y percusion ligera.\n\n"
            "Ahora genera tu respuesta."
        )


        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )

        return response.choices[0].message.content.strip()

    def _sanitize_text(self, text: str) -> str:
        """Decodifica caracteres escapados tipo \\u00e1 y elimina acentos."""
        # Primero decodificamos cualquier secuencia tipo \u00e1
        text = text.encode('utf-8').decode('unicode_escape')

        # Diccionario de reemplazos usando c�digos Unicode (sin escribir acentos directamente)
        replacements = {
            '\u00e1': 'a',  #
            '\u00e9': 'e',  #
            '\u00ed': 'i',  #
            '\u00f3': 'o',  #
            '\u00fa': 'u',  #
            '\u00c1': 'A',  #
            '\u00c9': 'E',  # �
            '\u00cd': 'I',  # �
            '\u00d3': 'O',  # �
            '\u00da': 'U',  # �
            '\u00f1': 'n',  # �
            '\u00d1': 'N',  # �
            '\u00fc': 'u',  # �
            '\u00dc': 'U',  # �
        }

        for k, v in replacements.items():
            text = text.replace(k, v)

        return text

    def _publish_to_redis(self, record, respuesta):
        """Publica en Redis el JSON actualizado con la respuesta."""
        tokens = respuesta.split()
        segundo = tokens[1].replace(",", "").replace(".", "").replace(":", "")
        data = {
            "fecha": record["fecha"],
            "ultima_actualizacion": record["ultima_actualizacion"],
            "emociones": record["emociones"],
            "respuesta_openai": respuesta,
            "emocion": segundo
        }
        self.r.publish("emociones", json.dumps(data))

    # ---------------------------
    # Servicio Flask
    # ---------------------------

    def handle_emociones(self):
        """Servicio POST principal."""
        try:
            data = request.get_json()
            emocion_data = data.get("emociones", {})
            print(emocion_data)
            tiempo = self._get_time_since_last_request()

            record = self._update_today_record(emocion_data)
            analisis = self._analyze_with_openai(record)
            analisis = self._sanitize_text(analisis)
            self._publish_to_redis(record, analisis)

            return jsonify({
                "tiempo_desde_ultima_peticion_seg": tiempo,
                "emociones_recibidas": emocion_data,
                "registro_actualizado": record,
                "respuesta_openai": analisis
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # ---------------------------
    # Ejecutar servidor
    # ---------------------------

    def run(self, host="0.0.0.0", port=5820):
        self.app.run(host=host, port=port)


# ---------------------------
# Ejecución principal
# ---------------------------

if __name__ == "__main__":
    vista = Vista()
    vista.run()