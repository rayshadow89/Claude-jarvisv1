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

# ---------------------------------------------------------------------------
# Copyright (c) 2026 Roberto (github.com/rayshadow89)
# Todos los derechos reservados. Software propietario de código visible:
# puedes leerlo y estudiarlo; usarlo, copiarlo o modificarlo necesita
# permiso por escrito. Los términos completos están en LICENSE.
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

import openai
from flask import (Flask, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)

import acceso
import copia
import gastos
import gym
import inversiones
import joker
import mesa
import tools

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
        "grupos": gym.GRUPOS,
        # Lo que necesita la página para adelantar el título de un día mientras
        # lo editas. El título bueno lo pone el servidor al guardar; esto es
        # solo para que lo veas cambiar sobre la marcha.
        "grupos_corto": gym.GRUPOS_CORTO,
        # El orden importa: es el desempate cuando dos grupos tienen los mismos
        # ejercicios. Va como lista porque el JSON ordena las claves alfabética-
        # mente y entonces la página titularía distinto que el servidor.
        "grupos_orden": list(gym.GRUPOS),
        "grupos_superior": sorted(gym.GRUPOS_SUPERIOR),
        "grupos_inferior": sorted(gym.GRUPOS_INFERIOR),
        "dias_semana_nombres": gym.DIAS_SEMANA,
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
    gym.borrar_completados()
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
        ejercicios = []
        for e in (dia.get("ejercicios") or []):
            if not isinstance(e, dict) or not str(e.get("nombre", "")).strip():
                continue
            # El grupo tiene que ser uno de los nuestros. Si el usuario añade un
            # ejercicio suyo y elige mal (o no elige), miramos si el nombre está
            # en el catálogo; y si tampoco, lo dejamos sin grupo antes que
            # guardar una categoría inventada que luego descuadre el título.
            grupo = str(e.get("grupo", ""))
            if grupo not in gym.GRUPOS:
                ficha = next((c for c in gym.EJERCICIOS
                              if c["nombre"] == str(e.get("nombre", "")).strip()), None)
                grupo = ficha["grupo"] if ficha else ""
            ejercicios.append({
                "nombre": str(e.get("nombre", "")).strip()[:120],
                "grupo": grupo,
                "alternativa": (str(e["alternativa"])[:120] if e.get("alternativa") else None),
                "sustituye_a": (str(e["sustituye_a"])[:120] if e.get("sustituye_a") else None),
            })

        # El nombre del día NO viene del navegador: lo recalculamos aquí a
        # partir de los ejercicios que han quedado. Así un lunes que ya no
        # tiene ni un ejercicio de pecho deja de llamarse "día de pecho".
        limpia.append({
            "dia": str(dia.get("dia", ""))[:20],
            "descanso": bool(dia.get("descanso")) or not ejercicios,
            "titulo": gym.titulo_de_sesion(ejercicios),
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
            "grupo_nombre": gym.GRUPOS[e["grupo"]],
            "casa": e["casa"],
            "alternativa": e["alt"],
            "desaconsejado": [gym.LIMITACIONES[l] for l in limitaciones if l in e["evitar"]],
        }
        for e in gym.EJERCICIOS
    ])


# --- Días completados ---

@app.post("/api/gym/completado")
def gym_marcar_completado():
    """Marca (o desmarca) un día de esta semana como hecho."""
    datos = request.get_json(silent=True) or {}
    dia = str(datos.get("dia", ""))
    if dia not in gym.DIAS_SEMANA:
        return jsonify({"error": "Ese día no existe."}), 400

    hechos = gym.marcar_dia(dia, bool(datos.get("hecho")))
    return jsonify({"ok": True, "dias_hechos": hechos, "semana_iso": gym.semana_actual()})


# --- Otro menú (la rotación de comidas) ---

@app.get("/api/gym/menu")
def gym_otro_menu():
    """
    Otro menú del día, del mismo grupo de menús que cuadran con tus números.

    Las comidas rotan solas cada día; esto es para cuando hoy no te apetece
    lo que ha tocado y quieres ver el siguiente sin esperar a mañana.
    """
    perfil = gym.leer_perfil()
    if not perfil:
        return jsonify({"error": "Aún no hay perfil."}), 400

    try:
        rotacion = int(request.args.get("v", 0))
    except ValueError:
        rotacion = 0

    metricas = gym.calcular_metricas(perfil)
    nutricion = gym.calcular_nutricion(perfil, metricas)
    return jsonify(gym.sugerir_menu(nutricion["calorias"], nutricion["proteina_g"], rotacion))


# --- Limitaciones escritas a mano ---

@app.post("/api/gym/limitaciones")
def gym_interpretar_limitaciones():
    """Convierte 'me duele la rodilla' en las limitaciones del sistema."""
    datos = request.get_json(silent=True) or {}
    texto = str(datos.get("texto", ""))[:500]
    return jsonify(gym.interpretar_limitaciones(texto))


# ---------------------------------------------------------------------------
# J0KER GASTOS  (el dinero)
# ---------------------------------------------------------------------------

@app.get("/gastos")
def pagina_gastos():
    return render_template("gastos.html")


@app.get("/api/gastos/opciones")
def gastos_opciones():
    """Reglas de reparto y categorías, para pintar el formulario."""
    return jsonify({
        "reglas": {
            clave: {
                "nombre": r["nombre"], "autor": r["autor"], "resumen": r["resumen"],
                "para_quien": r["para_quien"],
                "partes": [
                    {"clave": p["clave"], "nombre": p["nombre"], "pct": p["pct"],
                     "tipo": p["tipo"], "explica": p["explica"],
                     "categorias": [gastos.CATEGORIAS[c] for c in p["categorias"]]}
                    for p in r["partes"]
                ],
            }
            for clave, r in gastos.REGLAS.items()
        },
        "categorias": gastos.CATEGORIAS,
        "categorias_fijas": sorted(gastos.CATEGORIAS_FIJAS),
        "mes_actual": gastos.mes_actual(),
    })


@app.get("/api/gastos/panel")
def gastos_panel():
    """Todo el panel: reparto, avisos, deudas y datos de las gráficas."""
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"hay_perfil": False, "mes_actual": gastos.mes_actual()})

    mes = request.args.get("mes") or None
    if mes and not _mes_valido(mes):
        return jsonify({"error": "Ese mes no tiene buena pinta (formato AAAA-MM)."}), 400

    try:
        extra = max(0.0, float(request.args.get("extra", 0) or 0))
    except ValueError:
        extra = 0.0

    return jsonify({"hay_perfil": True,
                    "panel": gastos.panel_completo(perfil, mes, extra)})


def _mes_valido(mes: str) -> bool:
    from datetime import date
    try:
        anio, numero = (int(x) for x in str(mes).split("-"))
        date(anio, numero, 1)
        return 1970 <= anio <= 2200
    except (ValueError, TypeError):
        return False


@app.post("/api/gastos/perfil")
def gastos_guardar_perfil():
    """Cuánto entra al mes y con qué regla se reparte."""
    datos = request.get_json(silent=True) or {}

    try:
        ingreso = float(datos.get("ingreso", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "El ingreso tiene que ser un número."}), 400

    if not (0 < ingreso <= 10_000_000):
        return jsonify({"error": "El ingreso mensual tiene que ser mayor que 0."}), 400

    regla = str(datos.get("regla", "50_30_20"))
    if regla not in gastos.REGLAS:
        return jsonify({"error": "Esa regla de reparto no existe."}), 400

    # Los repartos que ya hubiera tocado a mano se conservan: cambiar de sueldo
    # no debería borrarte los porcentajes que ajustaste.
    anterior = gastos.leer_perfil() or {}
    perfil = {
        "ingreso": round(ingreso, 2),
        "regla": regla,
        "repartos": anterior.get("repartos", {}),
    }
    gastos.guardar_perfil(perfil)
    return jsonify({"hay_perfil": True, "panel": gastos.panel_completo(perfil)})


@app.post("/api/gastos/reparto")
def gastos_guardar_reparto():
    """
    Cambia los porcentajes de la regla actual.

    La única condición es que sumen 100: si quieres ahorrar el 99% y vivir con
    el 1%, allá tú, pero el dinero que repartes no puede ser más (ni menos) del
    que entra.
    """
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"error": "Primero dime cuánto ingresas al mes."}), 400

    datos = request.get_json(silent=True) or {}
    clave_regla = perfil.get("regla", "50_30_20")
    partes_validas = {p["clave"] for p in gastos.REGLAS[clave_regla]["partes"]}

    recibido = datos.get("porcentajes") or {}
    if not isinstance(recibido, dict):
        return jsonify({"error": "Formato de porcentajes incorrecto."}), 400

    limpio = {}
    for clave, valor in recibido.items():
        if clave not in partes_validas:
            return jsonify({"error": f"La parte '{clave}' no es de esta regla."}), 400
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return jsonify({"error": "Los porcentajes tienen que ser números."}), 400
        if not (0 <= numero <= 100):
            return jsonify({"error": "Cada porcentaje va entre 0 y 100."}), 400
        limpio[clave] = round(numero, 2)

    if set(limpio) != partes_validas:
        return jsonify({"error": "Faltan partes por repartir."}), 400

    suma = round(sum(limpio.values()), 2)
    if abs(suma - 100) > 0.01:
        return jsonify({
            "error": f"Tus porcentajes suman {suma:g}%, y tienen que sumar 100%. "
                     f"{'Te sobra' if suma > 100 else 'Te falta'} {abs(suma - 100):g}%."
        }), 400

    perfil.setdefault("repartos", {})[clave_regla] = limpio
    gastos.guardar_perfil(perfil)
    return jsonify({"ok": True, "panel": gastos.panel_completo(perfil)})


@app.delete("/api/gastos/reparto")
def gastos_restaurar_reparto():
    """Vuelve a los porcentajes originales de la regla."""
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"error": "Aún no hay perfil."}), 400
    (perfil.get("repartos") or {}).pop(perfil.get("regla", "50_30_20"), None)
    gastos.guardar_perfil(perfil)
    return jsonify({"ok": True, "panel": gastos.panel_completo(perfil)})


@app.post("/api/gastos/gasto")
def gastos_apuntar():
    """Apunta un gasto de un día concreto."""
    from datetime import date

    datos = request.get_json(silent=True) or {}
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"error": "Primero dime cuánto ingresas al mes."}), 400

    fecha = (datos.get("fecha") or "").strip()
    try:
        date.fromisoformat(fecha)
    except ValueError:
        return jsonify({"error": "La fecha no es válida."}), 400

    categoria = str(datos.get("categoria", ""))
    if categoria not in gastos.CATEGORIAS:
        return jsonify({"error": "Esa categoría no existe."}), 400

    try:
        importe = float(datos.get("importe"))
    except (TypeError, ValueError):
        return jsonify({"error": "El importe tiene que ser un número."}), 400

    if not (0 < importe <= 1_000_000):
        return jsonify({"error": "El importe tiene que ser mayor que 0."}), 400

    concepto = str(datos.get("concepto", "")).strip()[:80]
    gastos.apuntar_gasto(fecha, categoria, concepto, importe)

    mes = fecha[:7]
    return jsonify({"ok": True, "panel": gastos.panel_completo(perfil, mes)})


@app.delete("/api/gastos/gasto/<int:id_gasto>")
def gastos_borrar_gasto(id_gasto):
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"error": "Aún no hay perfil."}), 400
    mes = request.args.get("mes") if _mes_valido(request.args.get("mes") or "") else None
    gastos.borrar_gasto(id_gasto)
    return jsonify({"ok": True, "panel": gastos.panel_completo(perfil, mes)})


@app.post("/api/gastos/deuda")
def gastos_guardar_deuda():
    datos = request.get_json(silent=True) or {}
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"error": "Primero dime cuánto ingresas al mes."}), 400

    nombre = str(datos.get("nombre", "")).strip()[:60]
    if not nombre:
        return jsonify({"error": "Ponle nombre a la deuda."}), 400

    try:
        saldo = float(datos.get("saldo"))
        interes = float(datos.get("interes", 0))
        minimo = float(datos.get("pago_minimo", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "El saldo, el interés y el pago tienen que ser números."}), 400

    if not (0 < saldo <= 100_000_000):
        return jsonify({"error": "El saldo pendiente tiene que ser mayor que 0."}), 400
    if not (0 <= interes <= 200):
        return jsonify({"error": "El interés anual va entre 0 y 200%."}), 400
    if not (0 <= minimo <= 10_000_000):
        return jsonify({"error": "El pago mensual no puede ser negativo."}), 400

    gastos.guardar_deuda(nombre, saldo, interes, minimo)
    return jsonify({"ok": True, "panel": gastos.panel_completo(perfil)})


@app.delete("/api/gastos/deuda/<int:id_deuda>")
def gastos_borrar_deuda(id_deuda):
    perfil = gastos.leer_perfil()
    if not perfil:
        return jsonify({"error": "Aún no hay perfil."}), 400
    gastos.borrar_deuda(id_deuda)
    return jsonify({"ok": True, "panel": gastos.panel_completo(perfil)})


@app.post("/api/gastos/borrar")
def gastos_borrar_todo():
    """Empezar de cero: perfil, gastos y deudas."""
    gastos.borrar_todo()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# J0KER INVERSIONES  (la cartera cifrada y el mercado)
# ---------------------------------------------------------------------------
# La contraseña de la cartera NO se guarda en ningún sitio: ni en disco, ni en
# la cookie del navegador. Vive aquí, en la memoria del servidor, atada a la
# pestaña que la escribió, y se olvida sola por dos caminos:
#
#   - al cerrar el servidor (se va toda la memoria),
#   - y a los 30 minutos sin tocar nada, por si dejas el portátil abierto.
#
# Meterla en la cookie sería mandarla al navegador en cada petición, y guardarla
# en disco sería tirar el cifrado a la basura: con la contraseña al lado, el
# fichero cifrado no protege de nada.

CLAVES_CARTERA: dict[str, tuple] = {}     # sid -> (clave, último uso)
MINUTOS_SIN_TOCAR = 30


def _sid() -> str:
    """El identificador de esta pestaña, el mismo que usa el chat."""
    if "sid" not in session:
        session["sid"] = secrets.token_hex(16)
    return session["sid"]


def _clave_cartera() -> str | None:
    """La contraseña de esta sesión, si sigue viva."""
    import time
    sid = _sid()
    guardada = CLAVES_CARTERA.get(sid)
    if not guardada:
        return None

    clave, ultimo_uso = guardada
    if time.time() - ultimo_uso > MINUTOS_SIN_TOCAR * 60:
        CLAVES_CARTERA.pop(sid, None)
        return None

    CLAVES_CARTERA[sid] = (clave, time.time())   # sigue en uso: se renueva
    return clave


def _recordar_clave(clave: str) -> None:
    import time
    CLAVES_CARTERA[_sid()] = (clave, time.time())


def _olvidar_clave() -> None:
    CLAVES_CARTERA.pop(_sid(), None)


def _cartera_abierta():
    """
    Devuelve (clave, cartera) o lanza el 401 correspondiente.

    401 y no 403: no es que no tengas permiso, es que aún no te has
    identificado. El navegador lo usa para saber que tiene que pedir la
    contraseña otra vez.
    """
    clave = _clave_cartera()
    if clave is None:
        return None, None
    try:
        return clave, inversiones.leer_cartera(clave)
    except (inversiones.ClaveIncorrecta, inversiones.SinCartera):
        # La contraseña guardada ya no abre nada (te la han cambiado desde otra
        # pestaña, o han borrado la cartera). Mejor olvidarla que insistir.
        _olvidar_clave()
        return None, None


@app.get("/inversiones")
def pagina_inversiones():
    return render_template("inversiones.html")


@app.get("/api/inversiones/estado")
def inv_estado():
    """Lo único que se puede saber sin la contraseña."""
    info = inversiones.info_cartera()
    return jsonify({
        "existe": info["existe"],
        "abierta": _clave_cartera() is not None,
        "creada": info.get("creada"),
        "minutos_sin_tocar": MINUTOS_SIN_TOCAR,
        "clave_minima": inversiones.CLAVE_MINIMA,
    })


@app.post("/api/inversiones/crear")
def inv_crear():
    """La primera vez: se elige la contraseña y se crea la cartera vacía."""
    datos = request.get_json(silent=True) or {}
    clave = str(datos.get("clave", ""))
    repetida = str(datos.get("repetida", ""))

    if clave != repetida:
        return jsonify({"error": "Las dos contraseñas no coinciden."}), 400

    try:
        inversiones.crear_cartera(clave)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    _recordar_clave(clave)
    return jsonify({"ok": True, "cartera": _valoracion(clave)})


@app.post("/api/inversiones/abrir")
def inv_abrir():
    datos = request.get_json(silent=True) or {}
    clave = str(datos.get("clave", ""))

    try:
        inversiones.leer_cartera(clave)
    except inversiones.SinCartera:
        return jsonify({"error": "Todavía no hay ninguna cartera."}), 404
    except inversiones.ClaveIncorrecta as e:
        return jsonify({"error": str(e)}), 401

    _recordar_clave(clave)
    return jsonify({"ok": True, "cartera": _valoracion(clave)})


@app.post("/api/inversiones/cerrar")
def inv_cerrar():
    """Bloquear a mano, sin esperar a los 30 minutos."""
    _olvidar_clave()
    return jsonify({"ok": True})


def _valoracion(clave: str, con_precios: bool = True) -> dict:
    cartera = inversiones.leer_cartera(clave)
    valoracion = inversiones.valorar(cartera, con_precios=con_precios)
    return {
        **valoracion,
        "avisos": inversiones.avisos_cartera(valoracion),
    }


@app.get("/api/inversiones/cartera")
def inv_cartera():
    clave, cartera = _cartera_abierta()
    if clave is None:
        return jsonify({"bloqueada": True}), 401
    return jsonify({"bloqueada": False, "cartera": _valoracion(clave)})


@app.post("/api/inversiones/posicion")
def inv_guardar_posicion():
    """Añade una posición nueva, o cambia una que ya estaba (por su id)."""
    clave, cartera = _cartera_abierta()
    if clave is None:
        return jsonify({"bloqueada": True}), 401

    datos = request.get_json(silent=True) or {}
    try:
        posicion = inversiones._limpiar_posicion(datos)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    posiciones = cartera.get("posiciones", [])
    for i, existente in enumerate(posiciones):
        if existente["id"] == posicion["id"]:
            posiciones[i] = posicion
            break
    else:
        posiciones.append(posicion)

    if len(posiciones) > 200:
        return jsonify({"error": "200 posiciones son muchas. ¿Seguro?"}), 400

    cartera["posiciones"] = posiciones
    inversiones.guardar_cartera(clave, inversiones.normalizar_cartera(cartera))
    return jsonify({"ok": True, "cartera": _valoracion(clave)})


@app.delete("/api/inversiones/posicion/<id_posicion>")
def inv_borrar_posicion(id_posicion):
    clave, cartera = _cartera_abierta()
    if clave is None:
        return jsonify({"bloqueada": True}), 401

    cartera["posiciones"] = [p for p in cartera.get("posiciones", [])
                             if p["id"] != id_posicion]
    inversiones.guardar_cartera(clave, inversiones.normalizar_cartera(cartera))
    return jsonify({"ok": True, "cartera": _valoracion(clave)})


@app.post("/api/inversiones/clave")
def inv_cambiar_clave():
    datos = request.get_json(silent=True) or {}
    vieja = str(datos.get("vieja", ""))
    nueva = str(datos.get("nueva", ""))
    repetida = str(datos.get("repetida", ""))

    if nueva != repetida:
        return jsonify({"error": "Las dos contraseñas nuevas no coinciden."}), 400

    try:
        inversiones.cambiar_clave(vieja, nueva)
    except inversiones.ClaveIncorrecta as e:
        return jsonify({"error": str(e)}), 401
    except (ValueError, inversiones.SinCartera) as e:
        return jsonify({"error": str(e)}), 400

    _recordar_clave(nueva)
    return jsonify({"ok": True})


@app.post("/api/inversiones/borrar")
def inv_borrar_todo():
    """
    Borra la cartera entera. Pide la contraseña: si no, cualquiera que se
    siente delante del portátil podría cargársela sin poder ni leerla.
    """
    datos = request.get_json(silent=True) or {}
    try:
        inversiones.leer_cartera(str(datos.get("clave", "")))
    except inversiones.ClaveIncorrecta as e:
        return jsonify({"error": str(e)}), 401
    except inversiones.SinCartera:
        return jsonify({"ok": True})

    inversiones.borrar_cartera()
    _olvidar_clave()
    return jsonify({"ok": True})


@app.get("/api/inversiones/mercado")
def inv_mercado():
    """Los índices de referencia. Es información pública: no pide contraseña."""
    return jsonify({"indices": inversiones.mercado_hoy()})


@app.get("/api/inversiones/historico")
def inv_historico():
    simbolo = (request.args.get("s") or "").strip()[:20]
    if not simbolo:
        return jsonify({"error": "Falta el símbolo."}), 400
    try:
        dias = max(10, min(int(request.args.get("dias", 60)), 365))
    except ValueError:
        dias = 60
    return jsonify({"simbolo": simbolo, "puntos": inversiones.historico(simbolo, dias)})


# ---------------------------------------------------------------------------
# EL PIN DE LA CASA
# ---------------------------------------------------------------------------
# Una cortina delante de todo JOKER, para que quien abra el portátil no vea de
# entrada tu peso y tus deudas. No es cifrado (eso lo tiene la cartera): es una
# puerta. La diferencia está explicada en la propia pantalla.

# Lo que sigue abierto aunque haya PIN: la propia pantalla de bloqueo, lo que
# necesita para funcionar, y los ficheros estáticos. Sin esto, la pantalla que
# pide el PIN no podría ni pintarse.
SIN_PIN = {"pagina_bloqueo", "acceso_entrar", "acceso_estado", "static",
           "favicon", "mascota"}


@app.before_request
def _guardar_la_puerta():
    if request.endpoint in SIN_PIN:
        return None
    if not acceso.hay_pin() or session.get("pin_ok"):
        return None

    # A una llamada de la API se le contesta con un 401 para que el navegador
    # sepa qué ha pasado; a una página, se la manda a la pantalla de bloqueo.
    if request.path.startswith("/api/"):
        return jsonify({"bloqueado": True,
                        "error": "JOKER está bloqueado. Escribe tu PIN."}), 401
    return redirect(url_for("pagina_bloqueo"))


@app.get("/bloqueo")
def pagina_bloqueo():
    if not acceso.hay_pin() or session.get("pin_ok"):
        return redirect(url_for("pagina_mesa"))
    return render_template("bloqueo.html")


@app.get("/api/acceso/estado")
def acceso_estado():
    return jsonify({"hay_pin": acceso.hay_pin(),
                    "abierto": bool(session.get("pin_ok")) or not acceso.hay_pin(),
                    "minimo": acceso.PIN_MINIMO})


@app.post("/api/acceso/entrar")
def acceso_entrar():
    datos = request.get_json(silent=True) or {}
    if not acceso.comprobar_pin(str(datos.get("pin", ""))):
        return jsonify({"error": "Ese PIN no es el bueno."}), 401
    session["pin_ok"] = True
    return jsonify({"ok": True})


@app.post("/api/acceso/salir")
def acceso_salir():
    """Echar la cortina a mano. También cierra la cartera, por si acaso."""
    session.pop("pin_ok", None)
    _olvidar_clave()
    return jsonify({"ok": True})


@app.post("/api/acceso/poner")
def acceso_poner():
    datos = request.get_json(silent=True) or {}
    pin, repetido = str(datos.get("pin", "")), str(datos.get("repetido", ""))

    if acceso.hay_pin() and not acceso.comprobar_pin(str(datos.get("actual", ""))):
        return jsonify({"error": "El PIN actual no es el bueno."}), 401
    if pin != repetido:
        return jsonify({"error": "Los dos PIN no coinciden."}), 400

    try:
        acceso.poner_pin(pin)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session["pin_ok"] = True
    return jsonify({"ok": True, "hay_pin": True})


@app.post("/api/acceso/quitar")
def acceso_quitar():
    datos = request.get_json(silent=True) or {}
    try:
        acceso.quitar_pin(str(datos.get("pin", "")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    return jsonify({"ok": True, "hay_pin": False})


# ---------------------------------------------------------------------------
# COPIA DE SEGURIDAD
# ---------------------------------------------------------------------------

@app.get("/api/copia/exportar")
def copia_exportar():
    """Se descarga un .json con todo. La cartera va cifrada dentro."""
    from datetime import date
    from flask import Response

    datos = copia.exportar()
    nombre = f"joker-copia-{date.today().isoformat()}.json"
    return Response(
        json.dumps(datos, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@app.post("/api/copia/mirar")
def copia_mirar():
    """Qué trae una copia, SIN restaurarla. Para poder decidir con información."""
    datos = request.get_json(silent=True)
    if datos is None:
        return jsonify({"error": "Ese fichero no es un JSON válido."}), 400
    try:
        copia.comprobar(datos)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "resumen": copia.resumen(datos)})


@app.post("/api/copia/restaurar")
def copia_restaurar():
    """
    Deja joker.db como estaba en la copia. Lo que haya ahora se pierde.

    Se comprueba el fichero ANTES de borrar nada: si no es una copia de JOKER,
    el error llega con los datos buenos todavía en su sitio.
    """
    datos = request.get_json(silent=True)
    if datos is None:
        return jsonify({"error": "Ese fichero no es un JSON válido."}), 400

    try:
        copia.comprobar(datos)
        copia.preparar_tablas()
        puestas = copia.restaurar(datos)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"No he podido restaurar la copia: {e}"}), 500

    # Todo lo abierto deja de valer: la cartera se cifró con otra contraseña y
    # el PIN puede ser otro. Se cierra la sesión entera y se vuelve a empezar.
    _olvidar_clave()
    session.pop("pin_ok", None)
    return jsonify({"ok": True, "puestas": puestas})


# ---------------------------------------------------------------------------
# LA MESA  (el resumen de las cuatro salas)
# ---------------------------------------------------------------------------

@app.get("/mesa")
def pagina_mesa():
    return render_template("mesa.html")


@app.get("/api/mesa")
def mesa_resumen():
    return jsonify(mesa.resumen(_clave_cartera()))


# ---------------------------------------------------------------------------
# Por qué no salen las cotizaciones
# ---------------------------------------------------------------------------

@app.get("/api/inversiones/diagnostico")
def inv_diagnostico():
    """
    Qué pasa exactamente al pedir un precio, fuente por fuente.

    "La cinta sale vacía" no dice si es que no hay internet, si una fuente ha
    cambiado o si el símbolo está mal. Esto lo separa.
    """
    return jsonify(inversiones.diagnostico())


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

    # Si el usuario tiene la cartera desbloqueada en esta pestaña, JOKER puede
    # leerla durante este turno. La contraseña se deja y se quita aquí mismo:
    # fuera de la conversación, la tool no tiene forma de abrir nada.
    tools.poner_clave_cartera(_clave_cartera())

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
    finally:
        tools.poner_clave_cartera(None)

    _recortar(messages)

    texto = respuesta.content or "(no he sabido qué responder)"
    return jsonify({"respuesta": texto})


if __name__ == "__main__":
    print("\n  JOKER está en marcha.")
    print("  Abre esta dirección en tu navegador:  http://127.0.0.1:5000")
    print("  Para pararlo, pulsa Ctrl+C en esta ventana.\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
