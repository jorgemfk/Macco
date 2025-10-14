from flask import Flask, request, jsonify
import time, json, os, datetime
from openai import OpenAI

# ---------------------------
# Clase Vista
# ---------------------------

class Vista:
    def __init__(self):
        self.app = Flask(__name__)
        self.client = OpenAI()
        self.last_request_time = None
        self.data_file = "emociones_diarias.json"
        self.emociones = ["Enojo", "Asco", "Miedo", "Feliz", "Triste", "Sorpresa", "Neutral"]

        # Cargar datos previos
        self._load_data()

        # Definir rutas
        self.app.add_url_rule("/emociones", "emociones", self.handle_emociones, methods=["POST"])

    def _load_data(self):
        """Carga o inicializa el archivo diario de emociones."""
        today = datetime.date.today().isoformat()
        if os.path.exists(self.data_file):
            with open(self.data_file, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {}

        if today not in self.data:
            self.data[today] = {e: 0 for e in self.emociones}

    def _save_data(self):
        """Guarda los totales diarios."""
        with open(self.data_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def _get_time_since_last_request(self):
        """Devuelve segundos desde la última petición."""
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return None
        now = time.time()
        delta = now - self.last_request_time
        self.last_request_time = now
        return delta

    def _update_daily_counts(self, emocion_data):
        """Suma los rostros recibidos a los totales del día."""
        today = datetime.date.today().isoformat()
        for emocion, cantidad in emocion_data.items():
            if emocion in self.emociones:
                self.data[today][emocion] += cantidad
        self._save_data()

    def _analyze_with_openai(self):
        """Envía los totales diarios a OpenAI para obtener interpretación."""
        today = datetime.date.today().isoformat()
        totals = self.data[today]

        prompt = (
            "Analiza las siguientes ocurrencias de emociones detectadas hoy:\n\n"
            + "\n".join([f"{e}: {totals[e]}" for e in self.emociones])
            + "\n\nDetermina cómo se siente el grupo en general, "
              "limitando tu respuesta a una de estas emociones: "
              '["Enojo", "Asco", "Miedo", "Feliz", "Triste", "Sorpresa", "Neutral"]. '
              "Inicia con: Siento [Enojo, Asco, Miedo, Feliz, Triste, Sorpresa, Neutral] solo una de estas emociones como respuesta al estado del grupo y explica porque te sientes asi"
        )

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )

        return response.choices[0].message.content.strip()

    def handle_emociones(self):
        """Servicio POST principal."""
        try:
            data = request.get_json()
            emocion_data = data.get("emociones", {})
            tiempo = self._get_time_since_last_request()

            self._update_daily_counts(emocion_data)
            analisis = self._analyze_with_openai()

            return jsonify({
                "tiempo_desde_ultima_peticion_seg": tiempo,
                "emociones_recibidas": emocion_data,
                "respuesta_openai": analisis
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def run(self, host="0.0.0.0", port=5820):
        self.app.run(host=host, port=port)


# ---------------------------
# Ejecución principal
# ---------------------------

if __name__ == "__main__":
    vista = Vista()
    vista.run()

