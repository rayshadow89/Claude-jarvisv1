"""
JOKER — servidor web
=====================

Levanta una página web local con la interfaz de chat de JOKER. Por dentro
reutiliza exactamente el mismo motor que la versión de terminal (joker.py)
y las mismas habilidades (tools.py) — aquí solo añadimos la capa visual.

Cómo funciona:
  1. El navegador pide "/" y le servimos la página (templates/index.html).
  2. Cuando escribes un mensaje, el navegador lo manda a "/api/chat".
  3. Aquí ejecutamos el loop agéntico de siempre y devolvemos la respuesta.
  4. El navegador la pinta en pantalla.

Cada pestaña del navegador tiene su propia conversación, guardada en la
memoria del servidor. Al reiniciar el servidor se borran todas.

Ejecutar:
  pip install -r requirements.txt
  python app.py
Y abre http://127.0.0.1:5000 en el navegador.
"""

from __future__ import annotations

import os
import secrets

import openai
from flask import Flask, jsonify, render_template, request, session

import joker

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


app = Flask(__name__)
# Clave para firmar la cookie de sesión. Se regenera en cada arranque, así que
# al reiniciar el servidor las conversaciones empiezan de cero (que es lo que
# queremos en una app personal que corre en tu propio ordenador).
app.secret_key = secrets.token_hex(32)

# Conversaciones en memoria: {id_de_sesion: [mensajes...]}
CONVERSACIONES: dict[str, list] = {}

TOOL_DEFS = joker.construir_tools()

# Máximo de mensajes que guardamos por conversación, para que el historial no
# crezca sin límite y acabe gastando demasiados tokens en cada petición.
MAX_MENSAJES = 40


def _historial() -> list:
    """Devuelve (creándola si hace falta) la conversación de esta pestaña."""
    if "sid" not in session:
        session["sid"] = secrets.token_hex(16)
    sid = session["sid"]
    if sid not in CONVERSACIONES:
        CONVERSACIONES[sid] = [{"role": "system", "content": joker.SYSTEM_PROMPT}]
    return CONVERSACIONES[sid]


def _recortar(messages: list) -> None:
    """
    Si la conversación se hace muy larga, tira los mensajes más antiguos.
    El primero (el de 'system') se conserva siempre porque define quién es JOKER.
    """
    if len(messages) <= MAX_MENSAJES:
        return
    sobrantes = len(messages) - MAX_MENSAJES
    del messages[1:1 + sobrantes]

    # Un mensaje de tipo "tool" no puede quedar huérfano (sin la petición que
    # lo originó), o la API lo rechaza. Los quitamos si han quedado sueltos.
    while len(messages) > 1 and messages[1].get("role") == "tool":
        del messages[1]


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/nueva")
def nueva_conversacion():
    """Borra el historial de esta pestaña y empieza de cero."""
    sid = session.get("sid")
    if sid:
        CONVERSACIONES.pop(sid, None)
    return jsonify({"ok": True})


@app.post("/api/chat")
def chat():
    datos = request.get_json(silent=True) or {}
    mensaje = (datos.get("mensaje") or "").strip()

    if not mensaje:
        return jsonify({"error": "No has escrito nada."}), 400

    try:
        client = joker.crear_cliente()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    messages = _historial()
    messages.append({"role": "user", "content": mensaje})

    try:
        respuesta = joker.run_turn(client, messages, TOOL_DEFS)
    except openai.AuthenticationError:
        messages.pop()  # deshacemos el mensaje del usuario para no dejar basura
        return jsonify({"error": "La clave de la API no es válida. Revisa GROQ_API_KEY."}), 401
    except openai.RateLimitError:
        messages.pop()
        return jsonify({
            "error": "He llegado al límite de peticiones gratuitas. "
                     "Espera un minuto y vuelve a intentarlo."
        }), 429
    except openai.APIConnectionError:
        messages.pop()
        return jsonify({"error": "No pude conectar con la API. Revisa tu conexión."}), 502
    except openai.APIStatusError as e:
        messages.pop()
        return jsonify({"error": f"Error de la API ({e.status_code}): {e.message}"}), 502
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    _recortar(messages)

    texto = respuesta.content or "(no he sabido qué responder)"
    return jsonify({"respuesta": texto})


if __name__ == "__main__":
    print("\n  JOKER está en marcha.")
    print("  Abre esta dirección en tu navegador:  http://127.0.0.1:5000")
    print("  Para pararlo, pulsa Ctrl+C en esta ventana.\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
