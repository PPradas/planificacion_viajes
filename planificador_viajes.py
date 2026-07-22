import pandas as pd
import os
from dotenv import load_dotenv
import anthropic
import tkinter as tk
from tkinter import *
from tkinter import ttk
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from PIL import Image, ImageTk
import re
import platform
import subprocess


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

        df_planificacion = ejecutar_planificacion(lugar_elegido, duracion_elegida)

        label_espera.destroy()

        pagina_planificacion = ctk.CTkToplevel(app)
        pagina_planificacion.geometry("600x500")
        pagina_planificacion.title("Planificador de viajes")
        pagina_planificacion.wm_iconbitmap("imagenes/1-9a4da820.ico")
        pagina_planificacion.lift()
        pagina_planificacion.focus_force()
        pagina_planificacion.attributes('-topmost', 1)
        pagina_planificacion.after(100, lambda: pagina_planificacion.attributes('-topmost', 0))

        frame_planificacion = ctk.CTkFrame(pagina_planificacion, fg_color="transparent")
        frame_planificacion.pack(pady="20")

        titulo_planificacion = ctk.CTkLabel(frame_planificacion, text="Planificación del viaje")
        titulo_planificacion.configure(fg_color="transparent", text_color="black", font=("Arial",20, "bold"))
        titulo_planificacion.pack(pady=(120,10))

        subtitulo_planificacion = ctk.CTkLabel(frame_planificacion, text=f"{lugar_elegido} | {duracion_elegida} días")
        subtitulo_planificacion.configure(fg_color="transparent", text_color="black", font=("Arial",15))
        subtitulo_planificacion.pack(pady=(0,10))

        # columns only lists the data columns; #0 is the implicit tree column (Día)
        tabla_planificacion = ttk.Treeview(frame_planificacion, columns=("Mañana", "Tarde", "Noche"), height=20)
        tabla_planificacion.pack()
        style = ttk.Style()
        style.map("Treeview", background=[('selected', "white")])

        tabla_planificacion.heading('#0', text="Día")
        tabla_planificacion.heading('#1', text="Mañana")
        tabla_planificacion.heading('#2', text="Tarde")
        tabla_planificacion.heading('#3', text="Noche")

        tabla_planificacion.column("#0", width=50)
        tabla_planificacion.column("#1", width=150)
        tabla_planificacion.column("#2", width=150)
        tabla_planificacion.column("#3", width=150)

        if df_planificacion is not None:
            for _, row in df_planificacion.iterrows():
                tabla_planificacion.insert("", "end", text=row["Día"], values=(row["Mañana"], row["Tarde"], row["Noche"]))


boton_envio = ctk.CTkButton(frame, text="Enviar", command=enviar)
boton_envio.configure(fg_color="#1CAC78", font=("Arial", 15), text_color="white", hover_color="#50C878")
boton_envio.pack(pady=(30,120))


#CLIENTE ANTHROPIC

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY no encontrada en las variables de entorno")

client = anthropic.Anthropic(api_key=api_key)
modelo_chat = "claude-opus-4-8"


#FUNCIONES

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
            actividades = re.sub(r"\*\*|---", "", actividades)
            actividades = "\n".join([a.strip() for a in actividades.split("-") if a.strip()])
            if periodo in secciones:
                secciones[periodo] = actividades

        datos.append([dia, secciones["Mañana"], secciones["Tarde"], secciones["Noche"]])

    return pd.DataFrame(datos, columns=["Día", "Mañana", "Tarde", "Noche"])


def ejecutar_planificacion(lugar, dias):
    """Ejecuta el agente planificador usando Claude con búsqueda web integrada."""

    tools = [
        {
            "type": "web_search_20260209",
            "name": "web_search"
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
                            "**Mañana:** actividades\n"
                            "**Tarde:** actividades\n"
                            "**Noche:** actividades\n\n"
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
3. Con esa información, crea un planning día por día separando mañana, tarde y noche.
4. Llama a la herramienta generar_tabla con la planificación en este formato exacto:

Día 1: Nombre descriptivo del día
**Mañana:** descripción de actividades matutinas
**Tarde:** descripción de actividades vespertinas
**Noche:** cena en restaurante típico y actividades nocturnas

Día 2: Nombre descriptivo del día
**Mañana:** ...
**Tarde:** ...
**Noche:** ...

(Repite la estructura para cada día del viaje.)"""

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
            # El bucle server-side de web_search alcanzó su límite; continuamos sin añadir mensaje
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
