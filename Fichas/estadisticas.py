from flask import Flask, Response, request
import json
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import os
import glob
from datetime import datetime
import calendar

app = Flask(__name__)

LOG_DIR = "/home/jorge/logMacco"


def procesar_mes(mes, anio):
    conteo = defaultdict(lambda: defaultdict(int))

    patron = os.path.join(LOG_DIR, f"{anio}-{mes:02d}-*.log")
    archivos = sorted(glob.glob(patron))

    for archivo in archivos:
        try:
            nombre = os.path.basename(archivo)
            fecha = datetime.strptime(nombre.replace(".log", ""), "%Y-%m-%d")
            dia = fecha.day

            with open(archivo, "r") as f:
                for linea in f:
                    try:
                        data = json.loads(linea)
                        sentido = data.get("sentido")

                        if sentido:
                            conteo[sentido][dia] += 1

                    except:
                        continue

        except:
            continue

    return conteo


def generar_grafica(conteo, mes, anio):
    plt.figure(figsize=(12, 5))

    dias_mes = calendar.monthrange(anio, mes)[1]
    x = list(range(1, dias_mes + 1))

    totales = [0] * dias_mes  # acumulador por día

    # colores opcionales
    colores = {
        "oido": "blue",
        "vista": "green",
        "tacto": "red",
        "olfato": "orange"
    }

    for sentido, dias in conteo.items():
        y = [dias.get(d, 0) for d in x]

        # acumular totales
        for i in range(dias_mes):
            totales[i] += y[i]

        plt.plot(
            x, y,
            marker='o',
            label=sentido,
            color=colores.get(sentido)
        )

    # 🔥 línea de totales
    plt.plot(
        x, totales,
        linestyle='--',
        linewidth=2,
        color='black',
        label='total'
    )

    plt.title(f"Eventos por sentido - {mes}/{anio}")
    plt.xlabel("Día")
    plt.ylabel("Eventos")
    plt.legend()
    plt.grid()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)

    return img


@app.route("/")
def index():
    return """
    <h1>Reporte mensual</h1>
    <p>Ejemplo: /grafica?mes=6&anio=2026</p>
    <img src="/grafica">
    """


@app.route("/grafica")
def grafica():
    now = datetime.now()

    mes = int(request.args.get("mes", now.month))
    anio = int(request.args.get("anio", now.year))

    conteo = procesar_mes(mes, anio)
    img = generar_grafica(conteo, mes, anio)

    return Response(img.getvalue(), mimetype='image/png')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    
