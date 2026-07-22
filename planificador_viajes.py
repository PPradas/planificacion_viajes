import pandas as pd
import os
from dotenv import load_dotenv
import anthropic
import tkinter as tk
from tkinter import *
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from PIL import Image, ImageTk
import re
import platform
import subprocess
import webbrowser
import urllib.request
import urllib.parse
import json
from io import BytesIO


#FRONTAL SENCILLO

app = ctk.CTk()
app.geometry("600x500")
app.title("Planificador de viajes")
app.resizable(False, False)
app.iconbitmap("imagenes/1-9a4da820.ico")

frame = ctk.CTkFrame(app, width=600, height=500, fg_color="transparent")
frame.pack()

label_lugar = ctk.CTkLabel(frame, text="¿Qué país o ciudad quieres conocer?")
label_lugar.configure(fg_color="transparent", text_color="black", font=("Arial", 15))
label_lugar.pack(pady=(120,10))

lugar = tk.StringVar()
entrada_lugar = ctk.CTkEntry(frame, state="normal")
entrada_lugar.configure(fg_color="white", text_color="black", font=("Arial", 15), textvariable=lugar)
entrada_lugar.pack()

label_dias = ctk.CTkLabel(frame, text="¿Cuántos días tienes para realizar el viaje?")
label_dias.configure(fg_color="transparent", text_color="black", font=("Arial", 15))
label_dias.pack(pady=(30,10))

duracion = tk.IntVar()
entrada_dias = ctk.CTkEntry(frame, state="normal")
entrada_dias.configure(fg_color="white", text_color="black", font=("Arial", 15), textvariable=duracion)
entrada_dias.pack()

_link_counter = [0]
_link_urls = {}  # tag_id -> url (compartido entre todas las pestañas)

def enviar():
    lugar_elegido = entrada_lugar.get()
    duracion_elegida = entrada_dias.get()

    if not lugar_elegido or not duracion_elegida:
        CTkMessagebox(title="Error", message="Introduce los datos solicitados.", icon="cancel", fg_color="white", text_color="black", font=("Arial", 15), button_color="#1CAC78", button_hover_color="#50C878", button_text_color="white")

    elif not all(c.isalpha() or c.isspace() for c in lugar_elegido) or len(lugar_elegido) == 0:
        CTkMessagebox(title="Error", message="Por favor, introduce un país o ciudad correcto.", icon="cancel", fg_color="white", text_color="black", font=("Arial", 15), button_color="#1CAC78", button_hover_color="#50C878", button_text_color="white")

    elif not duracion_elegida.isdigit() or int(duracion_elegida) <= 0:
       CTkMessagebox(title="Error", message="La duración debe ser un número entero superior a 0.", icon="cancel", fg_color="white", text_color="black", font=("Arial", 15), button_color="#1CAC78", button_hover_color="#50C878", button_text_color="white")

    else:
        label_espera = ctk.CTkLabel(frame, text="Creando planificación...")
        label_espera.configure(fg_color="transparent", text_color="black", font=("Arial", 15))
        label_espera.pack()
        app.update()

        print(f"Lugar elegido: {lugar_elegido}")
        print(f"Duración del viaje (días): {duracion_elegida}")

        app.config(cursor="watch")
        app.update()
        df_planificacion = ejecutar_planificacion(lugar_elegido, duracion_elegida)

        # Pre-cargar imágenes por tema de cada día antes de crear la ventana
        imagenes_pil = {}
        if df_planificacion is not None:
            for idx, row in df_planificacion.iterrows():
                tema_match = re.match(r"Día \d+ - (.+)", row["Día"])
                tema = tema_match.group(1) if tema_match else lugar_elegido
                img_url = obtener_imagen_por_tema(f"{tema} {lugar_elegido}", fallback=lugar_elegido)
                if img_url:
                    pil_img = cargar_imagen_url(img_url, 580, 165)
                    if pil_img:
                        imagenes_pil[idx] = pil_img

        app.config(cursor="")

        label_espera.destroy()

        pagina_planificacion = ctk.CTkToplevel(app)
        pagina_planificacion.geometry("640x700")
        pagina_planificacion.title("Planificador de viajes")
        pagina_planificacion.wm_iconbitmap("imagenes/1-9a4da820.ico")

        frame_planificacion = ctk.CTkFrame(pagina_planificacion, fg_color="transparent")
        frame_planificacion.pack(fill="both", expand=True, padx=20, pady=15)

        titulo_planificacion = ctk.CTkLabel(frame_planificacion, text="Planificación del viaje")
        titulo_planificacion.configure(fg_color="transparent", text_color="black", font=("Arial", 20, "bold"))
        titulo_planificacion.pack(pady=(15, 5))

        subtitulo_planificacion = ctk.CTkLabel(frame_planificacion, text=f"{lugar_elegido} | {duracion_elegida} días")
        subtitulo_planificacion.configure(fg_color="transparent", text_color="black", font=("Arial", 15))
        subtitulo_planificacion.pack(pady=(0, 10))

        if df_planificacion is not None:
            tabview = ctk.CTkTabview(frame_planificacion, fg_color="white")
            tabview.pack(fill="both", expand=True)

            def insertar_con_tag(tw, texto, tag):
                inicio = tw.index("end-1c")
                tw.insert("end", texto)
                tw.tag_add(tag, inicio, "end-1c")

            textboxes_ajustar = []  # (CTkTextbox, Tk Text) para ajustar alto tras renderizado

            for idx, row in df_planificacion.iterrows():
                nombre_tab = f"Día {idx + 1}"
                tabview.add(nombre_tab)
                tab = tabview.tab(nombre_tab)

                # Imagen del día (ya pre-cargada)
                if idx in imagenes_pil:
                    ctk_img = ctk.CTkImage(light_image=imagenes_pil[idx], dark_image=imagenes_pil[idx], size=(580, 165))
                    ctk.CTkLabel(tab, image=ctk_img, text="", fg_color="transparent").pack(fill="x", padx=5, pady=(8, 4))

                # Contenido con texto y enlaces clicables
                textbox = ctk.CTkTextbox(tab, wrap="word", fg_color="white",
                                         border_width=0, font=("Arial", 11),
                                         text_color="#333333", activate_scrollbars=False)
                textbox.pack(fill="x", padx=5, pady=(0, 5))
                tw = textbox._textbox

                tw.tag_config("titulo", font=("Arial", 13, "bold"), foreground="black")
                tw.tag_config("manana", font=("Arial", 11, "bold"), foreground="#E07B00")
                tw.tag_config("tarde", font=("Arial", 11, "bold"), foreground="#B7950B")
                tw.tag_config("noche", font=("Arial", 11, "bold"), foreground="#1A5276")

                insertar_con_tag(tw, row["Día"] + "\n\n", "titulo")
                insertar_con_tag(tw, "MAÑANA\n", "manana")
                insertar_texto_con_enlaces(tw, row["Mañana"] + "\n\n")
                insertar_con_tag(tw, "TARDE\n", "tarde")
                insertar_texto_con_enlaces(tw, row["Tarde"] + "\n\n")
                insertar_con_tag(tw, "NOCHE\n", "noche")
                insertar_texto_con_enlaces(tw, row["Noche"] + "\n")

                textbox.configure(state="disabled")
                textboxes_ajustar.append((textbox, tw))

                # Bind de enlaces al widget entero (evita tag_bind, problemático en Python 3.14)
                def on_click(event, tw=tw):
                    idx = tw.index(f"@{event.x},{event.y}")
                    for tag in tw.tag_names(idx):
                        if tag in _link_urls:
                            webbrowser.open(_link_urls[tag])
                            return "break"

                def on_motion(event, tw=tw):
                    idx = tw.index(f"@{event.x},{event.y}")
                    on_link = any(t in _link_urls for t in tw.tag_names(idx))
                    tw.config(cursor="hand2" if on_link else "")

                tw.bind("<Button-1>", on_click)
                tw.bind("<Motion>", on_motion)

        # Ajustar altura de cada textbox a su contenido real tras el renderizado
        def ajustar_alturas():
            for tb, t in textboxes_ajustar:
                try:
                    n = int(t.count("1.0", "end", "displaylines")[0])
                    tb.configure(height=max(n * 19 + 10, 40))
                except Exception:
                    pass

        pagina_planificacion.after(150, ajustar_alturas)

        # Traer la ventana al frente después de crear todos los widgets
        pagina_planificacion.lift()
        pagina_planificacion.focus_force()
        pagina_planificacion.attributes('-topmost', 1)
        pagina_planificacion.after(100, lambda: pagina_planificacion.attributes('-topmost', 0))


boton_envio = ctk.CTkButton(frame, text="Enviar", command=enviar)
boton_envio.configure(fg_color="#1CAC78", font=("Arial", 15), text_color="white", hover_color="#50C878")
boton_envio.pack(pady=(30,120))


#CLIENTE ANTHROPIC

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY no encontrada en las variables de entorno")

client = anthropic.Anthropic(api_key=api_key)
modelo_chat = "claude-haiku-4-5"


#FUNCIONES

def obtener_imagen_por_tema(query, fallback=None):
    """Busca en Wikimedia Commons una fotografía (JPG) relevante para la query.
    Filtra escudos, mapas, iconos y cualquier imagen que no sea foto real."""
    excluir = ("flag", "icon", "logo", "coat", "coa_", "symbol", "seal", "blank",
               "locator", "outline", "relief", "escudo", "heraldic", "map", "mapa",
               "arms", "emblem", "shield", "stamp", "insignia", "badge", "blazon",
               "diagram", "chart", "schematic", "poster", "sign", "label",
               "typography", "lettering", "cartel", "silhouette", "pictogram")

    def buscar(q):
        try:
            term = urllib.parse.quote(q)
            url = (
                f"https://commons.wikimedia.org/w/api.php?action=query"
                f"&generator=search&gsrsearch={term}&gsrnamespace=6&gsrlimit=30"
                f"&prop=imageinfo&iiprop=url|mediatype&iiurlwidth=640&format=json"
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
                # Solo imágenes raster (BITMAP), no dibujos vectoriales ni audio
                if img_info.get("mediatype") not in ("BITMAP", None, ""):
                    continue
                img_url = img_info.get("thumburl") or img_info.get("url", "")
                # Solo JPG: indicador fuerte de fotografía real
                if ".jpg" not in img_url.lower() and ".jpeg" not in img_url.lower():
                    continue
                # Filtrar por nombre de archivo
                filename = page.get("title", "").lower()
                if any(kw in filename for kw in excluir):
                    continue
                return img_url
        except Exception as e:
            print(f"Error Commons '{q}': {e}")
        return None

    return buscar(query) or (buscar(fallback) if fallback else None)


def cargar_imagen_url(url, ancho, alto):
    """Descarga una imagen desde una URL y la devuelve como PIL Image redimensionada."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PlanificadorViajes/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        img = Image.open(BytesIO(data)).convert("RGB")
        # Recorte centrado para mantener proporción
        orig_w, orig_h = img.size
        ratio = max(ancho / orig_w, alto / orig_h)
        new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - ancho) // 2
        top = (new_h - alto) // 2
        img = img.crop((left, top, left + ancho, top + alto))
        return img
    except Exception as e:
        print(f"Error cargando imagen {url}: {e}")
        return None


def insertar_texto_con_enlaces(tw, texto):
    """Inserta texto en un widget Tk Text convirtiendo patrones (https://...) en [enlace] clicable.
    Las URLs se almacenan en _link_urls; el click se gestiona con bind a nivel de widget."""
    patron = re.compile(r'\((https?://[^\s\)]+)\)')
    pos = 0
    for match in patron.finditer(texto):
        antes = texto[pos:match.start()]
        if antes:
            tw.insert("end", antes)
        url = match.group(1)
        tag_id = f"enlace_{_link_counter[0]}"
        _link_counter[0] += 1
        _link_urls[tag_id] = url
        tw.insert("end", " [enlace]", tag_id)
        tw.tag_config(tag_id, foreground="#1CAC78", underline=True)
        pos = match.end()
    if pos < len(texto):
        tw.insert("end", texto[pos:])


def crear_tabla_planificacion(planificacion):
    """
    Genera un DataFrame con la planificación del viaje, separando las actividades
    en mañana, tarde y noche de cada día.
    """
    print("Texto recibido para generar tabla:\n", planificacion)

    patron_dia = re.compile(r"D[ií]a (\d+): (.*?)\n", re.IGNORECASE)
    patron_periodo = re.compile(r"\*\*(Mañana|Tarde|Noche):\*\*", re.IGNORECASE)

    partes = patron_dia.split(planificacion)
    datos = []

    print("\nPartes separadas por días:", partes)

    for i in range(1, len(partes), 3):
        dia = f"Día {partes[i].strip()} - {partes[i+1].strip()}"
        contenido = partes[i + 2].strip() if i + 2 < len(partes) else ""

        segmentos = patron_periodo.split(contenido)
        secciones = {"Mañana": "", "Tarde": "", "Noche": ""}

        print(f"\nContenido Día {partes[i].strip()}:\n", contenido)
        print("\nSegmentos detectados por período del día:", segmentos)

        for j in range(1, len(segmentos), 2):
            periodo = segmentos[j].strip()
            actividades = segmentos[j + 1].strip() if j + 1 < len(segmentos) else ""
            actividades = re.sub(r"\*\*", "", actividades)
            actividades = re.sub(r"^---\s*$", "", actividades, flags=re.MULTILINE)
            actividades = actividades.strip()
            if periodo in secciones:
                secciones[periodo] = actividades

        datos.append([dia, secciones["Mañana"], secciones["Tarde"], secciones["Noche"]])

    return pd.DataFrame(datos, columns=["Día", "Mañana", "Tarde", "Noche"])


def ejecutar_planificacion(lugar, dias):
    """Ejecuta el agente planificador usando Claude con búsqueda web integrada."""

    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3
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
                            "Día 1: Nombre del día\n"
                            "**Mañana:**\n"
                            "- Lugar o actividad — descripción (https://url-real)\n"
                            "**Tarde:**\n"
                            "- Lugar o actividad — descripción (https://url-real)\n"
                            "**Noche:**\n"
                            "- Restaurante: Nombre — tipo de cocina (https://url-real)\n\n"
                            "Día 2: Nombre del día\n"
                            "... (repetir para cada día)"
                        )
                    }
                },
                "required": ["planificacion"]
            }
        }
    ]

    system = """Eres un experto planificador de viajes. Tu tarea es crear una planificación detallada de viaje.

Pasos obligatorios:
1. Usa la búsqueda web para encontrar los principales sitios turísticos del destino.
2. Usa la búsqueda web para encontrar restaurantes típicos bien valorados del destino.
3. Con esa información, crea un planning día por día.
4. Llama a la herramienta generar_tabla con la planificación en este formato exacto:

Día 1: Nombre descriptivo del día
**Mañana:**
- Nombre del lugar o actividad — descripción breve (https://web-oficial-si-existe)
- Otro lugar sin web oficial conocida
**Tarde:**
- Nombre del lugar o actividad — descripción breve (https://web-oficial-si-existe)
**Noche:**
- Restaurante: Nombre — tipo de cocina (https://web-propia-del-restaurante-si-existe)

Día 2: Nombre descriptivo del día
**Mañana:**
- ...

REGLAS ESTRICTAS SOBRE ENLACES:
- Solo incluye un enlace si existe una web OFICIAL del propio lugar: web oficial del monumento/museo, web propia del restaurante, plataforma oficial de venta de entradas (ej: getyourguide.com, tiqets.com para ese sitio concreto).
- PROHIBIDO incluir enlaces de: blogs, TripAdvisor, Google Maps, Booking, periódicos, wikis, redes sociales o cualquier web de terceros.
- Si un lugar no tiene web oficial conocida, simplemente no pongas enlace. No todos los puntos necesitan enlace.
- Es preferible no poner ningún enlace que poner uno de mala calidad."""

    messages = [
        {
            "role": "user",
            "content": f"Planifica un viaje a {lugar} de {dias} días. Busca información actualizada sobre sitios turísticos y restaurantes."
        }
    ]

    df_resultado = None

    while True:
        response = client.messages.create(
            model=modelo_chat,
            max_tokens=16000,
            system=system,
            tools=tools,
            messages=messages
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
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Tabla generada correctamente."
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break
        else:
            break

    return df_resultado


app.mainloop()
