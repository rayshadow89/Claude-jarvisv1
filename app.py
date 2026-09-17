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
from pathlib import Path

import openai
from flask import Flask, jsonify, render_template, request, send_from_directory, session

import gym
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


# Carpeta donde buscamos la imagen de la mascota.
CARPETA_STATIC = Path(__file__).parent / "static"

# Extensiones de imagen que aceptamos, para no depender de que el nombre sea
# EXACTAMENTE "joker.png" — Windows a veces oculta la extensión real al
# guardar ("joker.png.jpg"), o guarda en mayúsculas, o en otro formato.
EXTENSIONES_IMAGEN = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _buscar_imagen_mascota() -> str | None:
    """Busca en /static cualquier archivo que empiece por 'joker' y sea una
    imagen, sin importar mayúsculas/minúsculas ni la extensión exacta."""
    if not CARPETA_STATIC.is_dir():
        return None
    for archivo in sorted(CARPETA_STATIC.iterdir()):
        if (archivo.is_file()
                and archivo.name.lower().startswith("joker")
                and archivo.suffix.lower() in EXTENSIONES_IMAGEN):
            return archivo.name
    return None


@app.get("/mascota")
def mascota():
    """Sirve la imagen de la mascota la encuentre como la encuentre.
    Si no hay ninguna, devuelve 404 y la página muestra el emoji 🃏."""
    nombre = _buscar_imagen_mascota()
    if nombre is None:
        return "", 404
    return send_from_directory(CARPETA_STATIC, nombre)


@app.get("/favicon.ico")
def favicon():
    # Evita el 404 que el navegador pide solo por curiosidad; usamos la
    # misma imagen de la mascota si existe, o nada si no hay ninguna.
    nombre = _buscar_imagen_mascota()
    if nombre is None:
        return "", 204
    return send_from_directory(CARPETA_STATIC, nombre)


@app.get("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# J0KER GYM
# ---------------------------------------------------------------------------

@app.get("/gym")
def pagina_gym():
    return render_template("gym.html")


@app.get("/api/gym/opciones")
def gym_opciones():
    """Todo lo que necesita el formulario para pintarse (objetivos, niveles...)."""
    return jsonify({
        "objetivos": gym.OBJETIVOS,
        "niveles": gym.NIVELES,
        "actividades": {k: v[1] for k, v in gym.FACTORES_ACTIVIDAD.items()},
        "somatotipos": {k: v[1] for k, v in gym.AJUSTE_SOMATOTIPO.items()},
        "limitaciones": gym.LIMITACIONES,
    })


@app.get("/api/gym/plan")
def gym_plan():
    """Devuelve el plan completo, o avisa de que aún no hay perfil."""
    perfil = gym.leer_perfil()
    if not perfil:
        return jsonify({"hay_perfil": False})
    return jsonify({"hay_perfil": True, "plan": gym.plan_completo(perfil)})


@app.post("/api/gym/perfil")
def gym_guardar_perfil():
    """Guarda el perfil y devuelve el plan recién calculado."""
    datos = request.get_json(silent=True) or {}

    # Validamos lo imprescindible antes de calcular nada
    try:
        peso = float(datos.get("peso", 0))
        altura = float(datos.get("altura", 0))
        edad = int(datos.get("edad", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "El peso, la altura y la edad tienen que ser números."}), 400

    if not (25 <= peso <= 300):
        return jsonify({"error": "El peso debe estar entre 25 y 300 kg."}), 400
    if not (100 <= altura <= 250):
        return jsonify({"error": "La altura debe estar entre 100 y 250 cm."}), 400
    if not (14 <= edad <= 100):
        return jsonify({"error": "La edad debe estar entre 14 y 100 años."}), 400

    objetivo_peso = datos.get("peso_objetivo")
    if objetivo_peso not in (None, ""):
        try:
            objetivo_peso = float(objetivo_peso)
        except (TypeError, ValueError):
            return jsonify({"error": "El peso objetivo tiene que ser un número."}), 400
        if not (25 <= objetivo_peso <= 300):
            return jsonify({"error": "El peso objetivo debe estar entre 25 y 300 kg."}), 400
    else:
        objetivo_peso = None

    perfil = {
        "peso": peso,
        "altura": altura,
        "edad": edad,
        "sexo": datos.get("sexo", "hombre"),
        "somatotipo": datos.get("somatotipo", "no_lo_se"),
        "actividad": datos.get("actividad", "moderado"),
        "objetivo": datos.get("objetivo", "mantener"),
        "nivel": datos.get("nivel", "principiante"),
        "dias_semana": int(datos.get("dias_semana", 3)),
        "peso_objetivo": objetivo_peso,
        "limitaciones": [l for l in datos.get("limitaciones", []) if l in gym.LIMITACIONES],
    }

    gym.guardar_perfil(perfil)
    return jsonify({"hay_perfil": True, "plan": gym.plan_completo(perfil)})


@app.post("/api/gym/borrar")
def gym_borrar():
    gym.borrar_perfil()
    gym.borrar_rutina_personalizada()
    return jsonify({"ok": True})


# --- Registro de peso (la gráfica) ---

@app.post("/api/gym/peso")
def gym_registrar_peso():
    datos = request.get_json(silent=True) or {}
    fecha = (datos.get("fecha") or "").strip()
    try:
        kg = float(datos.get("kg"))
    except (TypeError, ValueError):
        return jsonify({"error": "El peso tiene que ser un número."}), 400

    if not (25 <= kg <= 300):
        return jsonify({"error": "El peso debe estar entre 25 y 300 kg."}), 400

    # La fecha tiene que ser una fecha de verdad, en formato AAAA-MM-DD
    from datetime import date
    try:
        date.fromisoformat(fecha)
    except ValueError:
        return jsonify({"error": "La fecha no es válida."}), 400

    gym.registrar_peso(fecha, kg)
    return jsonify({"ok": True, "pesos": gym.leer_pesos()})


@app.delete("/api/gym/peso/<fecha>")
def gym_borrar_peso(fecha):
    gym.borrar_peso(fecha)
    return jsonify({"ok": True, "pesos": gym.leer_pesos()})


# --- Rutina editable ---

@app.post("/api/gym/rutina")
def gym_guardar_rutina():
    """Guarda la rutina que el usuario ha editado a mano."""
    datos = request.get_json(silent=True) or {}
    rutina = datos.get("rutina")

    if not isinstance(rutina, list) or len(rutina) != 7:
        return jsonify({"error": "La rutina debe tener los 7 días de la semana."}), 400

    # Limpiamos lo que llega: solo nos quedamos con lo que esperamos, para que
    # nadie pueda colar campos raros en la base de datos.
    limpia = []
    for dia in rutina:
        if not isinstance(dia, dict):
            return jsonify({"error": "Formato de rutina incorrecto."}), 400
        ejercicios = [
            {"nombre": str(e.get("nombre", ""))[:120], "grupo": str(e.get("grupo", ""))[:30],
             "alternativa": (str(e["alternativa"])[:120] if e.get("alternativa") else None),
             "sustituye_a": (str(e["sustituye_a"])[:120] if e.get("sustituye_a") else None)}
            for e in (dia.get("ejercicios") or []) if isinstance(e, dict)
            and str(e.get("nombre", "")).strip()
        ]
        limpia.append({
            "dia": str(dia.get("dia", ""))[:20],
            "descanso": bool(dia.get("descanso")) or not ejercicios,
            "titulo": str(dia.get("titulo", "Descanso"))[:80],
            "series": dia.get("series"),
            "reps": dia.get("reps"),
            "tiempo_descanso": dia.get("tiempo_descanso"),
            "ejercicios": ejercicios,
        })

    gym.guardar_rutina_personalizada(limpia)
    perfil = gym.leer_perfil()
    return jsonify({"ok": True, "plan": gym.plan_completo(perfil) if perfil else None})


@app.delete("/api/gym/rutina")
def gym_restaurar_rutina():
    """Tira la rutina editada y vuelve a la que calcula JOKER."""
    gym.borrar_rutina_personalizada()
    perfil = gym.leer_perfil()
    return jsonify({"ok": True, "plan": gym.plan_completo(perfil) if perfil else None})


@app.get("/api/gym/ejercicios")
def gym_catalogo():
    """El catálogo completo, para el desplegable al editar la rutina."""
    limitaciones = gym.leer_perfil().get("limitaciones", []) if gym.leer_perfil() else []
    return jsonify([
        {
            "nombre": e["nombre"],
            "grupo": e["grupo"],
            "casa": e["casa"],
            "alternativa": e["alt"],
            "desaconsejado": [gym.LIMITACIONES[l] for l in limitaciones if l in e["evitar"]],
        }
        for e in gym.EJERCICIOS
    ])


# --- Limitaciones escritas a mano ---

@app.post("/api/gym/limitaciones")
def gym_interpretar_limitaciones():
    """Convierte 'me duele la rodilla' en las limitaciones del sistema."""
    datos = request.get_json(silent=True) or {}
    texto = str(datos.get("texto", ""))[:500]
    return jsonify(gym.interpretar_limitaciones(texto))


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
