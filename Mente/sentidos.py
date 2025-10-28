from flask import Flask, request, jsonify
from tinydb import TinyDB, Query
from openai import OpenAI
import redis, json, time, datetime, os
from collections import deque
import copy
import unicodedata
import re

class Vista:
    def __init__(self):
        # --- Configuración base ---
        self.app = Flask(__name__)
        self.client = OpenAI()
        self.db = TinyDB("emociones_diarias.json")
        self.r = redis.Redis(host='localhost', port=6379, db=0)
        self.last_request_time = None

        # --- Lista de emociones reconocidas ---
        self.emociones = ["Enojo", "Asco", "Miedo", "Felicidad", "Tristeza", "Sorpresa", "Neutral"]

        # --- Buffer para acumular las últimas 3 recepciones ---
        self.ultimas_tres = deque(maxlen=3)

        # --- Guardar última emoción publicada para evitar repeticiones ---
        self.ultima_emocion_publicada = None

        # --- Definir ruta principal ---
        self.app.add_url_rule("/emociones", "emociones", self.handle_emociones, methods=["POST"])

    # ------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------

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
        record = copy.deepcopy(self._get_today_record())

        # Actualizar conteos acumulativos
        for e, c in emocion_data.items():
            if e in self.emociones:
                record["emociones"][e] += c

        record["ultima_actualizacion"] = datetime.datetime.now().isoformat()
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

    def _sumar_ultimas_tres(self):
        """Suma las emociones de las últimas tres recepciones."""
        total = {e: 0 for e in self.emociones}
        for rec in self.ultimas_tres:
            for e, c in rec.items():
                if e in total:
                    total[e] += c
        return total

    def _analyze_with_openai(self, totals):
        """Envía totales diarios a OpenAI para generar un resumen poético."""
        prompt = (
            "Analiza las siguientes emociones detectadas recientemente:\n\n"
            + "\n".join([f"{e}: {totals[e]}" for e in self.emociones])
            + "\n\n"
            "Debes responder con DOS enunciados unicos:\n"
            "1. El primer enunciado debe comenzar exactamente con 'Siento [Enojo, Asco, Miedo, Felicidad, Tristeza, Sorpresa, Neutral]' "
            "(elige solo una de estas emociones). Haz que suene humano, divertido o poetico, como si fueras un DJ que siente la energia del publico. "
            "Termina el enunciado con un emoji ASCII pequeno adecuado a la emocion.\n"
            "2. El segundo enunciado debe describir como esa emocion se convertira en una sinfonia generativa en SuperCollider , "
            "mencionando ritmo, textura, instrumentos o tono y explicitamente el genero de acuerdo ala emocion por ejemplo Tristeza-dark_wave, Felicidad-Synth_pop, Enojo-noise, Neutral-Techno, Asco-Gothic_techno, Miedo-dark_ambient, Sorpresa-Techno_industrial .\n\n"
            "No uses acentos, emojis graficos ni menciones de IA o codigo. Solo texto plano.\n\n"
            "Ejemplo:\n"
            "Siento Tristeza, como si si mi corazon se undiera en el olvido eterno. (U_U)\n"
            "Creare una sinfonia dark wave con sonido melancolico y a menudo introspectivo, utilizando tonos menores y sintetizadores.\n\n"
            "Ahora genera tu respuesta."
        )


        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9
        )

        return response.choices[0].message.content.strip()

    def _sanitize_text(self, text: str) -> str:
        """Quita acentos, tildes y caracteres no ASCII."""
        # Normalizar texto (descompone á → a + ´)
        nfkd_form = unicodedata.normalize('NFKD', text)
        # Eliminar marcas diacríticas
        text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        # Convertir ñ → n y Ñ → N si deseas evitar caracteres fuera de ASCII
        text = text.replace("ñ", "n").replace("Ñ", "N")
        # Opcional: eliminar cualquier carácter no imprimible o no ASCII
        #text = re.sub(r"[^A-Za-z0-9.,;:!?()\"' \n]", "", text)
        return text

    def _extract_emocion(self, respuesta):
        """Extrae la emoción principal del texto devuelto por OpenAI."""
        for e in self.emociones:
            if e in respuesta:
                return e
        return "Neutral"

    def _publish_to_redis(self, record, respuesta, totals):
        """Publica en Redis solo si hay una emoción nueva."""
        emocion_actual = self._extract_emocion(respuesta)

        if emocion_actual == self.ultima_emocion_publicada:
            print(f" Misma emoción detectada ({emocion_actual}), no se publica en Redis.")
            return  # Evita publicaciones repetidas

        data = {
            "fecha": record["fecha"],
            "ultima_actualizacion": record["ultima_actualizacion"],
            "emociones_diarias": record["emociones"],
            "emociones_recientes": totals,
            "respuesta_openai": respuesta,
            "emocion_predominante": emocion_actual
        }

        self.r.publish("emociones", json.dumps(data, ensure_ascii=False))
        self.ultima_emocion_publicada = emocion_actual
        print(f" Publicado en Redis con emoción: {emocion_actual}")

    # ------------------------------------------------------------
    # Servicio Flask
    # ------------------------------------------------------------

    def handle_emociones(self):
        """Servicio POST principal."""
        try:
            data = request.get_json()
            emocion_data = data.get("emociones", {})

            tiempo = self._get_time_since_last_request()

            # Acumular en buffer de últimas tres recepciones
            self.ultimas_tres.append(emocion_data)

            # Actualizar en TinyDB (acumulado diario)
            record = self._update_today_record(emocion_data)

            # Sumar las tres últimas recepciones
            totales_recientes = self._sumar_ultimas_tres()

            # Enviar a OpenAI solo el resumen de las últimas 3
            analisis = self._analyze_with_openai(totales_recientes)
            analisis = self._sanitize_text(analisis)

            # Publicar en Redis si cambia la emoción
            self._publish_to_redis(record, analisis, totales_recientes)

            return jsonify({
                "tiempo_desde_ultima_peticion_seg": tiempo,
                "emociones_recibidas": emocion_data,
                "emociones_ultimas_tres": totales_recientes,
                "registro_actualizado": record,
                "respuesta_openai": analisis
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # ------------------------------------------------------------
    # Ejecutar servidor
    # ------------------------------------------------------------
    def run(self, host="0.0.0.0", port=5820):
        self.app.run(host=host, port=port)


# ------------------------------------------------------------
# Ejecución principal
# ------------------------------------------------------------
if __name__ == "__main__":
    vista = Vista()
    vista.run()
