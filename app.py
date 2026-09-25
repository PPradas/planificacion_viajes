from flask import Flask, render_template, request, send_from_directory
import os
import re
import html
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv
import anthropic
import pandas as pd

load_dotenv()

app = Flask(__name__)

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY no encontrada en las variables de entorno")

client = anthropic.Anthropic(api_key=api_key)
modelo_chat = "claude-haiku-4-5"


def obtener_imagen_por_tema(query, fallback=None, usadas=None):
    if usadas is None:
        usadas = set()

    excluir = (
        "flag", "icon", "logo", "coat", "coa_", "symbol", "seal", "blank",
        "locator", "outline", "relief", "escudo", "heraldic", "map", "mapa",
        "arms", "emblem", "shield", "stamp", "insignia", "badge", "blazon",
        "diagram", "chart", "schematic", "poster", "sign", "label",
        "typography", "lettering", "silhouette", "pictogram", "wikivoyage",
        "category", "collage", "montage", "composite",
    )

    def buscar(q):
        try:
            term = urllib.parse.quote(q)
            url = (
                f"https://commons.wikimedia.org/w/api.php?action=query"
                f"&generator=search&gsrsearch={term}&gsrnamespace=6&gsrlimit=50"
                f"&prop=imageinfo&iiprop=url|mediatype|size&iiurlwidth=900&format=json"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "PlanificadorViajes/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            pages = data.get("query", {}).get("pages", {})
            sorted_pages = sorted(pages.values(), key=lambda p: p.get("index", 999))
            for page in sorted_pages:
                info = page.get("imageinfo", [])
                if not info:
                    continue
                img_info = info[0]
                if img_info.get("mediatype") not in ("BITMAP", None, ""):
                    continue
                img_url = img_info.get("thumburl") or img_info.get("url", "")
                if ".jpg" not in img_url.lower() and ".jpeg" not in img_url.lower():
                    continue
                if img_url in usadas:
                    continue
                width = img_info.get("width", 0)
                height = img_info.get("height", 0)
                if width < 600:
                    continue
                if height > 0 and width > 0 and height > width:
                    continue
                filename = page.get("title", "").lower()
                if any(kw in filename for kw in excluir):
                    continue
                return img_url
        except Exception as e:
            print(f"Error Commons '{q}': {e}")
        return None

    result = (
        buscar(f"{query} photography")
        or buscar(query)
        or (buscar(f"{fallback} tourism") if fallback else None)
        or (buscar(fallback) if fallback else None)
    )
    if result:
        usadas.add(result)
    return result


def extraer_primer_lugar(texto):
    """Devuelve el nombre del primer lugar/actividad del texto de actividades."""
    if not texto:
        return None
    for line in texto.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("- "):
            continue
        line = line[2:]
        line = re.sub(r"\(https?://[^\)]+\)", "", line).strip()
        if "—" in line:
            line = line.split("—")[0].strip()
        line = re.sub(r"(?i)^restaurante:\s*", "", line).strip()
        if len(line) > 2:
            return line
    return None


def actividades_a_html(texto):
    if not texto:
        return ""
    lines = texto.strip().split("\n")
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:]
        url_match = re.search(r"\((https?://[^\s\)]+)\)", line)
        url = None
        if url_match:
            url = url_match.group(1)
            line = line[: url_match.start()].strip()
        line = html.escape(line)
        link_html = (
            f' <a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer" class="activity-link">↗</a>'
            if url
            else ""
        )
        items.append(f"<li>{line}{link_html}</li>")
    return '<ul class="activity-list">' + "".join(items) + "</ul>" if items else ""


def crear_tabla_planificacion(planificacion):
    patron_dia = re.compile(r"D[ií]a (\d+): (.*?)\n", re.IGNORECASE)
    patron_periodo = re.compile(
        r"\*\*(Mañana|Tarde|Noche|Restaurantes):\*\*", re.IGNORECASE
    )

    partes = patron_dia.split(planificacion)
    datos = []

    for i in range(1, len(partes), 3):
        dia = f"Día {partes[i].strip()} - {partes[i+1].strip()}"
        contenido = partes[i + 2].strip() if i + 2 < len(partes) else ""
        segmentos = patron_periodo.split(contenido)
        secciones = {"Mañana": "", "Tarde": "", "Noche": "", "Restaurantes": ""}

        for j in range(1, len(segmentos), 2):
            periodo = segmentos[j].strip()
            actividades = segmentos[j + 1].strip() if j + 1 < len(segmentos) else ""
            actividades = re.sub(r"\*\*", "", actividades)
            actividades = re.sub(r"^---\s*$", "", actividades, flags=re.MULTILINE)
            if periodo in secciones:
                secciones[periodo] = actividades.strip()

        datos.append([
            dia,
            secciones["Mañana"],
            secciones["Tarde"],
            secciones["Noche"],
            secciones["Restaurantes"],
        ])

    return pd.DataFrame(datos, columns=["Día", "Mañana", "Tarde", "Noche", "Restaurantes"])


def ejecutar_planificacion(lugar, dias):
    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3,
        },
        {
            "name": "generar_tabla",
            "description": "Crea la tabla final con la planificación del viaje. Llámala cuando tengas toda la información lista.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "planificacion": {
                        "type": "string",
                        "description": (
                            "Planificación completa en el formato exacto:\n"
                            "Día 1: Nombre descriptivo del día\n"
                            "**Mañana:**\n"
                            "- Lugar o actividad — descripción breve (https://web-oficial-si-existe)\n"
                            "**Tarde:**\n"
                            "- Lugar o actividad — descripción breve (https://web-oficial-si-existe)\n"
                            "**Noche:** (OMITIR esta sección si no hay nada relevante)\n"
                            "- Zona o actividad nocturna — descripción breve\n"
                            "**Restaurantes:**\n"
                            "- Nombre — tipo de cocina, zona o barrio (https://web-propia-si-existe)\n"
                            "- Nombre — tipo de cocina, zona o barrio (https://web-propia-si-existe)\n\n"
                            "Día 2: Nombre descriptivo del día\n"
                            "... (repetir para cada día)"
                        ),
                    }
                },
                "required": ["planificacion"],
            },
        },
    ]

    system = """Eres un experto planificador de viajes. Tu tarea es crear una planificación detallada de viaje.

Pasos obligatorios:
1. Usa la búsqueda web para encontrar los principales sitios turísticos del destino.
2. Usa la búsqueda web para encontrar restaurantes bien valorados en las mismas zonas que los sitios turísticos del día.
3. Con esa información, crea un planning día por día y llama a generar_tabla con este formato exacto:

Día 1: Nombre descriptivo del día
**Mañana:**
- Lugar o actividad — descripción breve (https://web-oficial-si-existe)
- Otro lugar — descripción breve
**Tarde:**
- Lugar o actividad — descripción breve (https://web-oficial-si-existe)
- Otro lugar — descripción breve
**Noche:**
- Zona o actividad nocturna — descripción breve (barrios de fiesta, paseos nocturnos, miradores, zonas iluminadas...)
**Restaurantes:**
- Nombre del restaurante — tipo de cocina, zona o barrio (https://web-propia-si-existe)
- Nombre del restaurante — tipo de cocina, zona o barrio (https://web-propia-si-existe)

Día 2: Nombre descriptivo del día
...

REGLAS SOBRE LA SECCIÓN **Noche:**:
- Inclúyela SOLO si hay algo interesante que ver o hacer de noche: vida nocturna, zonas iluminadas, paseos, miradores nocturnos, barrios con ambiente...
- NUNCA incluyas restaurantes en esta sección.
- Si no hay nada especial, OMITE completamente la sección **Noche:** de ese día.

REGLAS SOBRE LA SECCIÓN **Restaurantes:**:
- Incluye exactamente 2 restaurantes por día.
- Deben estar en la misma zona o barrio que las actividades del día, para no tener que desplazarse lejos.
- Uno puede ser para comer y otro para cenar, o ambos en horarios distintos.

REGLAS ESTRICTAS SOBRE ENLACES:
- Solo incluye un enlace si existe una web OFICIAL: web del monumento/museo, web propia del restaurante, plataforma de venta de entradas (getyourguide.com, tiqets.com).
- PROHIBIDO: blogs, TripAdvisor, Google Maps, Booking, periódicos, wikis, redes sociales.
- Si un lugar no tiene web oficial conocida, no pongas enlace. Es preferible ningún enlace a uno de mala calidad."""

    messages = [
        {
            "role": "user",
            "content": f"Planifica un viaje a {lugar} de {dias} días. Busca información actualizada sobre sitios turísticos y restaurantes.",
        }
    ]

    df_resultado = None

    while True:
        response = client.messages.create(
            model=modelo_chat,
            max_tokens=16000,
            system=system,
            tools=tools,
            messages=messages,
        )

        print(f"stop_reason: {response.stop_reason}")
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "pause_turn":
            continue
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "generar_tabla":
                    df_resultado = crear_tabla_planificacion(block.input["planificacion"])
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Tabla generada correctamente.",
                        }
                    )
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break
        else:
            break

    return df_resultado


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("imagenes", "1-9a4da820.ico", mimetype="image/x-icon")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/planificar", methods=["POST"])
def planificar():
    lugar = request.form.get("lugar", "").strip()
    dias = request.form.get("dias", "").strip()

    error = None
    if not lugar or not dias:
        error = "Introduce los datos solicitados."
    elif not all(c.isalpha() or c.isspace() for c in lugar):
        error = "Por favor, introduce un país o ciudad correcto."
    elif not dias.isdigit() or int(dias) <= 0:
        error = "La duración debe ser un número entero superior a 0."

    if error:
        return render_template("index.html", error=error)

    df = ejecutar_planificacion(lugar, dias)

    dias_data = []
    usadas_imgs = set()

    if df is not None:
        for idx, row in df.iterrows():
            primer_lugar = extraer_primer_lugar(row["Mañana"])
            if primer_lugar:
                query = f"{primer_lugar} {lugar}"
            else:
                tema_match = re.match(r"Día \d+ - (.+)", row["Día"])
                tema = tema_match.group(1) if tema_match else lugar
                query = f"{tema} {lugar}"

            img_url = obtener_imagen_por_tema(query, fallback=lugar, usadas=usadas_imgs)

            dias_data.append(
                {
                    "numero": idx + 1,
                    "titulo": row["Día"],
                    "manana": actividades_a_html(row["Mañana"]),
                    "tarde": actividades_a_html(row["Tarde"]),
                    "noche": actividades_a_html(row["Noche"]),
                    "restaurantes": actividades_a_html(row["Restaurantes"]),
                    "imagen": img_url,
                }
            )

    return render_template("resultado.html", lugar=lugar, dias=dias, dias_data=dias_data)


if __name__ == "__main__":
    import webbrowser
    import threading

    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(debug=False, port=5000)
