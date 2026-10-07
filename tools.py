"""
Tools de JOKER — la "lógica" real del asistente.
==================================================

Este módulo no sabe nada de Groq, Gemini ni Claude: son funciones de Python
normales y corrientes. Eso permite que joker.py (Groq), joker_gemini.py y
joker_claude.py compartan exactamente las mismas capacidades.

Para añadirle una habilidad nueva a JOKER:
  1. Escribe la función aquí abajo.
  2. Añade su esquema a TOOL_SCHEMAS.
  3. Regístrala en TOOL_FUNCTIONS.
No hace falta tocar nada más.
"""

# ---------------------------------------------------------------------------
# Copyright (c) 2026 Roberto (github.com/rayshadow89)
# Todos los derechos reservados. Software propietario de código visible:
# puedes leerlo y estudiarlo; usarlo, copiarlo o modificarlo necesita
# permiso por escrito. Los términos completos están en LICENSE.
# ---------------------------------------------------------------------------

from __future__ import annotations

import ast
import math
import operator
import os
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


class ToolError(Exception):
    """Fallo esperado dentro de una tool (input inválido, falta una clave, etc.)."""


# ---------------------------------------------------------------------------
# Tool 1: get_datetime — hora actual de una ubicación
# ---------------------------------------------------------------------------

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Nombres en español que no coinciden con el nombre de la zona horaria oficial
# (que siempre está en inglés). Ej: la zona de Tokio se llama "Asia/Tokyo".
_ALIAS_CIUDADES = {
    "tokio": "tokyo",
    "londres": "london",
    "nueva_york": "new_york",
    "moscu": "moscow",
    "roma": "rome",
    "atenas": "athens",
    "lisboa": "lisbon",
    "copenhague": "copenhagen",
    "estocolmo": "stockholm",
    "varsovia": "warsaw",
    "praga": "prague",
    "viena": "vienna",
    "bruselas": "brussels",
    "bucarest": "bucharest",
    "el_cairo": "cairo",
    "argel": "algiers",
    "tunez": "tunis",
    "singapur": "singapore",
    "sidney": "sydney",
    "ciudad_de_mexico": "mexico_city",
    "la_habana": "havana",
    "pekin": "shanghai",
    "shangai": "shanghai",
    "seul": "seoul",
    "estambul": "istanbul",
}

# Países -> zona horaria de su capital, para cuando se pregunta por el país.
_ALIAS_PAISES = {
    "espana": "Europe/Madrid",
    "portugal": "Europe/Lisbon",
    "francia": "Europe/Paris",
    "italia": "Europe/Rome",
    "alemania": "Europe/Berlin",
    "reino_unido": "Europe/London",
    "inglaterra": "Europe/London",
    "irlanda": "Europe/Dublin",
    "paises_bajos": "Europe/Amsterdam",
    "holanda": "Europe/Amsterdam",
    "belgica": "Europe/Brussels",
    "suiza": "Europe/Zurich",
    "austria": "Europe/Vienna",
    "grecia": "Europe/Athens",
    "polonia": "Europe/Warsaw",
    "suecia": "Europe/Stockholm",
    "noruega": "Europe/Oslo",
    "dinamarca": "Europe/Copenhagen",
    "finlandia": "Europe/Helsinki",
    "rusia": "Europe/Moscow",
    "turquia": "Europe/Istanbul",
    "marruecos": "Africa/Casablanca",
    "egipto": "Africa/Cairo",
    "sudafrica": "Africa/Johannesburg",
    "nigeria": "Africa/Lagos",
    "japon": "Asia/Tokyo",
    "china": "Asia/Shanghai",
    "corea_del_sur": "Asia/Seoul",
    "india": "Asia/Kolkata",
    "tailandia": "Asia/Bangkok",
    "indonesia": "Asia/Jakarta",
    "australia": "Australia/Sydney",
    "nueva_zelanda": "Pacific/Auckland",
    "mexico": "America/Mexico_City",
    "cuba": "America/Havana",
    "argentina": "America/Argentina/Buenos_Aires",
    "colombia": "America/Bogota",
    "peru": "America/Lima",
    "chile": "America/Santiago",
    "brasil": "America/Sao_Paulo",
    "uruguay": "America/Montevideo",
    "venezuela": "America/Caracas",
    "ecuador": "America/Guayaquil",
    "bolivia": "America/La_Paz",
    "paraguay": "America/Asuncion",
    "canada": "America/Toronto",
    "estados_unidos": "America/New_York",
    "eeuu": "America/New_York",
}


def _normalizar(texto: str) -> str:
    """Quita acentos, pasa a minúsculas y cambia espacios por guiones bajos."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return sin_acentos.strip().lower().replace(" ", "_")


def _zona_sin_internet(nombre: str) -> str | None:
    """
    Intenta resolver la zona horaria sin salir a internet, comparando con la
    lista de zonas que trae Python (Europe/Madrid, Asia/Tokyo, etc.).
    Cubre las ciudades principales del mundo y es instantáneo.
    """
    clave = _normalizar(nombre)

    if clave in _ALIAS_PAISES:
        return _ALIAS_PAISES[clave]

    clave = _ALIAS_CIUDADES.get(clave, clave)

    try:
        zonas = available_timezones()
    except Exception:
        return None

    for zona in zonas:
        if zona.split("/")[-1].lower() == clave:
            return zona
    return None


def _buscar_ubicacion(query: str) -> dict | None:
    """Busca una ubicación con la API de Open-Meteo. Devuelve el mejor resultado o None."""
    import requests

    for idioma in ("es", "en"):  # algunos nombres solo se resuelven bien en inglés
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1, "language": idioma, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results")
        if resultados:
            return resultados[0]
    return None


def _resolver_lugar(location: str) -> dict:
    """
    Encuentra una ubicación probando varias formas de escribirla.

    El modelo a veces manda "Ciudad, País" (ej. "Madrid, España") y esa
    cadena completa no siempre encaja con el buscador, así que probamos
    también solo con el trozo anterior a la coma. Lo usan tanto la tool
    de la hora como la del clima.

    Lanza ToolError si no la encuentra o si falla la red.
    """
    location = location.strip()
    intentos = [location]
    if "," in location:
        intentos.append(location.split(",", 1)[0].strip())

    error_red = None
    for query in intentos:
        try:
            lugar = _buscar_ubicacion(query)
        except Exception as e:  # fallo de red, timeout, respuesta rara...
            error_red = e
            continue
        if lugar:
            return lugar

    if error_red is not None:
        raise ToolError(
            f"No pude consultar el servicio de ubicaciones para '{location}' "
            f"(problema de red: {error_red})."
        )
    raise ToolError(f"No encontré ninguna ubicación llamada '{location}'.")


def get_datetime(location: str) -> str:
    """
    Devuelve la fecha y hora actual de cualquier ciudad o país del mundo.

    Lo intenta en dos fases:
      1. Sin internet, comparando con las zonas horarias que trae Python.
         Cubre las ciudades y países principales y es instantáneo.
      2. Si no la encuentra, busca la ubicación en la API de Open-Meteo
         (gratis, sin clave), que conoce hasta pueblos pequeños.
    """
    location = location.strip()

    # El modelo a veces manda "Ciudad, País" (ej. "Madrid, España"). Probamos
    # la cadena completa y también solo el trozo antes de la coma.
    intentos = [location]
    if "," in location:
        intentos.append(location.split(",", 1)[0].strip())

    tz_name = None
    nombre_bonito = location

    # Fase 1: sin internet
    for query in intentos:
        tz_name = _zona_sin_internet(query)
        if tz_name:
            nombre_bonito = query
            break

    # Fase 2: buscando en internet
    if not tz_name:
        lugar = _resolver_lugar(location)
        tz_name = lugar.get("timezone")
        if not tz_name:
            raise ToolError(f"Encontré '{location}' pero no tengo su zona horaria.")
        pais = lugar.get("country")
        nombre = lugar.get("name", location)
        nombre_bonito = f"{nombre}, {pais}" if pais else nombre

    try:
        ahora = datetime.now(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError as e:
        # Pasa en Windows, que no trae la base de datos de zonas horarias.
        raise ToolError(
            "Falta la base de datos de zonas horarias del mundo (Windows no la "
            "incluye de serie). Se arregla ejecutando en la terminal:  "
            "pip install tzdata"
        ) from e

    dia = DIAS[ahora.weekday()]
    mes = MESES[ahora.month - 1]

    return (
        f"En {nombre_bonito} son las {ahora:%H:%M} del {dia} "
        f"{ahora.day} de {mes} de {ahora.year} ({tz_name})."
    )


# ---------------------------------------------------------------------------
# Tool 2: get_weather — clima actual (Open-Meteo, gratis y sin clave)
# ---------------------------------------------------------------------------

# Descripción de cada código de tiempo de la OMM (el estándar que devuelve
# la API). Los códigos que no estén aquí se agrupan por su primer dígito.
_CODIGOS_TIEMPO = {
    0:  "despejado",
    1:  "mayormente despejado",
    2:  "parcialmente nublado",
    3:  "nublado",
    45: "con niebla",
    48: "con niebla helada",
    51: "con llovizna ligera",
    53: "con llovizna",
    55: "con llovizna intensa",
    56: "con llovizna helada ligera",
    57: "con llovizna helada intensa",
    61: "con lluvia ligera",
    63: "lloviendo",
    65: "con lluvia fuerte",
    66: "con lluvia helada ligera",
    67: "con lluvia helada fuerte",
    71: "nevando ligeramente",
    73: "nevando",
    75: "con nevada intensa",
    77: "con granizo fino",
    80: "con chubascos ligeros",
    81: "con chubascos",
    82: "con chubascos muy fuertes",
    85: "con chubascos de nieve ligeros",
    86: "con chubascos de nieve fuertes",
    95: "con tormenta",
    96: "con tormenta y algo de granizo",
    99: "con tormenta y granizo fuerte",
}


def _describir_tiempo(codigo) -> str:
    """Traduce el código numérico de la API a algo legible en castellano."""
    try:
        codigo = int(codigo)
    except (TypeError, ValueError):
        return "con el cielo en estado desconocido"
    return _CODIGOS_TIEMPO.get(codigo, "con el cielo en estado desconocido")


def get_weather(location: str, unit: str = "celsius") -> str:
    """
    Devuelve el clima actual de cualquier ciudad del mundo.

    Usa Open-Meteo, que es gratis y NO necesita ninguna clave: primero
    busca las coordenadas de la ciudad y luego pide el tiempo en ese punto.
    """
    import requests

    lugar = _resolver_lugar(location)

    fahrenheit = unit == "fahrenheit"
    parametros = {
        "latitude": lugar["latitude"],
        "longitude": lugar["longitude"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "weather_code,wind_speed_10m",
        "timezone": "auto",
    }
    if fahrenheit:
        parametros["temperature_unit"] = "fahrenheit"
        parametros["wind_speed_unit"] = "mph"

    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast", params=parametros, timeout=10
        )
        resp.raise_for_status()
        actual = resp.json().get("current")
    except requests.RequestException as e:
        raise ToolError(f"Error de red al consultar el clima de '{location}': {e}") from e
    except ValueError as e:
        raise ToolError(f"La API del clima devolvió una respuesta ilegible: {e}") from e

    if not actual:
        raise ToolError(f"La API del clima no devolvió datos para '{location}'.")

    pais = lugar.get("country")
    nombre = lugar.get("name", location)
    sitio = f"{nombre}, {pais}" if pais else nombre

    grados = "°F" if fahrenheit else "°C"
    viento_unidad = "mph" if fahrenheit else "km/h"

    partes = [f"En {sitio} está {_describir_tiempo(actual.get('weather_code'))}"]

    temp = actual.get("temperature_2m")
    if temp is not None:
        partes.append(f", {temp}{grados}")

    sensacion = actual.get("apparent_temperature")
    if sensacion is not None and sensacion != temp:
        partes.append(f" (sensación térmica {sensacion}{grados})")

    humedad = actual.get("relative_humidity_2m")
    if humedad is not None:
        partes.append(f", humedad {humedad}%")

    viento = actual.get("wind_speed_10m")
    if viento is not None:
        partes.append(f", viento {viento} {viento_unidad}")

    return "".join(partes) + "."


# ---------------------------------------------------------------------------
# Tool 3: calculate — matemáticas, con evaluador seguro (nunca usa eval())
# ---------------------------------------------------------------------------

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
}
_NAMES = {"pi": math.pi, "e": math.e}


def _eval_node(node: ast.AST):
    """Recorre el árbol sintáctico permitiendo solo operaciones matemáticas."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in _FUNCS and not node.keywords:
            return _FUNCS[node.func.id](*[_eval_node(a) for a in node.args])
        raise ValueError(f"función no permitida: {node.func.id}")
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    raise ValueError("expresión no permitida")


def calculate(expression: str) -> str:
    """Evalúa una expresión matemática de forma segura."""
    try:
        resultado = _eval_node(ast.parse(expression, mode="eval").body)
    except Exception as e:
        raise ToolError(f"No pude evaluar '{expression}': {e}") from e
    return f"{expression} = {resultado}"


# ---------------------------------------------------------------------------
# Tool 4: search_web — búsqueda de información en internet (API de Wikipedia)
# ---------------------------------------------------------------------------

# API pública de MediaWiki: no requiere clave, es la misma que usan miles de
# bots de Wikipedia desde hace años. Limitación honesta: solo encuentra lo
# que hay en Wikipedia, así que sirve para "qué es X" o "quién fue X", pero
# no para noticias del día. Si más adelante quieres búsqueda web de verdad,
# esto es lo que habría que sustituir (por ejemplo por Tavily o Serper).
def search_web(query: str, lang: str = "es") -> str:
    """Busca un término en Wikipedia y devuelve un resumen breve."""
    import requests

    api_url = f"https://{lang}.wikipedia.org/w/api.php"

    try:
        busqueda = requests.get(
            api_url,
            params={
                "action": "query", "list": "search", "srsearch": query,
                "format": "json", "srlimit": 1,
            },
            timeout=10,
            headers={"User-Agent": "JOKER-v1-proyecto-personal"},
        )
        busqueda.raise_for_status()
    except requests.RequestException as e:
        raise ToolError(f"Error de red al buscar '{query}': {e}") from e

    resultados = busqueda.json().get("query", {}).get("search", [])
    if not resultados:
        raise ToolError(f"No encontré nada sobre '{query}' en Wikipedia.")

    titulo = resultados[0]["title"]

    try:
        extracto = requests.get(
            api_url,
            params={
                "action": "query", "prop": "extracts", "exintro": True,
                "explaintext": True, "format": "json", "titles": titulo,
            },
            timeout=10,
            headers={"User-Agent": "JOKER-v1-proyecto-personal"},
        )
        extracto.raise_for_status()
    except requests.RequestException as e:
        raise ToolError(f"Error de red al leer '{titulo}': {e}") from e

    paginas = extracto.json().get("query", {}).get("pages", {})
    texto = next(iter(paginas.values()), {}).get("extract", "").strip()
    if not texto:
        raise ToolError(f"Encontré '{titulo}' pero no pude leer su contenido.")

    # Recortamos para no gastar de más en tokens de salida.
    resumen = texto[:800] + ("..." if len(texto) > 800 else "")
    return f"Según Wikipedia ({titulo}): {resumen}"


# ---------------------------------------------------------------------------
# Tool 6: buscar_noticias — lo que está pasando hoy
# ---------------------------------------------------------------------------
# Wikipedia es una enciclopedia: sabe quién fue Nikola Tesla, no sabe qué pasó
# ayer. Para lo del día a día hace falta otra fuente, y aquí se usa el RSS de
# Google Noticias: es gratis, no pide ninguna clave, devuelve titulares de
# medios de verdad con su fecha, y se puede pedir en español de España.
#
# Lo que devuelve son TITULARES con su medio y su fecha, no el artículo entero.
# Es a propósito: con el titular, el medio y la fecha, JOKER puede contarte lo
# que hay sin inventarse el contenido de una noticia que no ha leído.

FUENTE_NOTICIAS = "https://news.google.com/rss"


def _texto_rss(elemento, etiqueta: str, por_defecto: str = "") -> str:
    """Saca el texto de una etiqueta hija, o el valor por defecto si no está."""
    hijo = elemento.find(etiqueta)
    if hijo is None or hijo.text is None:
        return por_defecto
    return hijo.text.strip()


def _fecha_legible(pub_date: str) -> str:
    """
    Convierte la fecha del RSS (formato de correo) en algo que se lea.

    Si no se puede interpretar, se devuelve tal cual: más vale una fecha fea
    que perder el dato o reventar por una noticia con la fecha mal puesta.
    """
    from email.utils import parsedate_to_datetime

    try:
        momento = parsedate_to_datetime(pub_date)
    except (TypeError, ValueError):
        return pub_date

    from datetime import datetime, timezone

    ahora = datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)

    horas = (ahora - momento).total_seconds() / 3600
    if horas < 1:
        cuando = "hace menos de una hora"
    elif horas < 24:
        cuando = f"hace {int(horas)} h"
    elif horas < 48:
        cuando = "ayer"
    else:
        cuando = f"hace {int(horas / 24)} días"

    return f"{momento.strftime('%d/%m/%Y %H:%M')} ({cuando})"


def _partir_titular(titulo: str, medio: str) -> tuple:
    """
    Google Noticias pone "Titular - Medio" en el título. Separamos las dos
    cosas para poder enseñarlas ordenadas, sin repetir el medio dos veces.
    """
    if medio and titulo.endswith(f" - {medio}"):
        return titulo[: -len(f" - {medio}")].strip(), medio
    if " - " in titulo:
        cabeza, _, cola = titulo.rpartition(" - ")
        # Solo lo tratamos como medio si es corto: "Madrid - Barcelona" no lo es
        if len(cola) <= 40:
            return cabeza.strip(), cola.strip()
    return titulo.strip(), medio


def _analizar_noticias(xml_texto: str, tope: int) -> list:
    """
    Saca los titulares del XML del RSS.

    Está separado de la descarga a propósito: así se puede probar el análisis
    con un ejemplo guardado, sin depender de que haya internet.
    """
    import xml.etree.ElementTree as ET

    try:
        raiz = ET.fromstring(xml_texto)
    except ET.ParseError as e:
        raise ToolError(f"La respuesta de Google Noticias no se pudo leer: {e}") from e

    noticias = []
    for item in raiz.iter("item"):
        titulo_bruto = _texto_rss(item, "title")
        if not titulo_bruto:
            continue
        medio = _texto_rss(item, "source")
        titular, medio = _partir_titular(titulo_bruto, medio)
        noticias.append({
            "titular": titular,
            "medio": medio or "sin medio",
            "fecha": _fecha_legible(_texto_rss(item, "pubDate")),
            "enlace": _texto_rss(item, "link"),
        })
        if len(noticias) >= tope:
            break
    return noticias


def buscar_noticias(tema: str = "", dias: int = 7, cuantas: int = 8) -> str:
    """
    Titulares de actualidad sobre un tema, o la portada si no se pide ninguno.

    Es lo que le falta a search_web: Wikipedia sabe de historia, esto sabe de
    hoy. Sale del RSS de Google Noticias, que es gratis y no pide clave.
    """
    import requests
    import urllib.parse

    cuantas = max(1, min(int(cuantas), 15))
    dias = max(1, min(int(dias), 365))
    tema = (tema or "").strip()

    if tema:
        consulta = urllib.parse.quote(f"{tema} when:{dias}d")
        url = f"{FUENTE_NOTICIAS}/search?q={consulta}&hl=es&gl=ES&ceid=ES:es"
        de_que = f"sobre '{tema}' (últimos {dias} días)"
    else:
        url = f"{FUENTE_NOTICIAS}?hl=es&gl=ES&ceid=ES:es"
        de_que = "de portada"

    try:
        respuesta = requests.get(
            url, timeout=12,
            headers={"User-Agent": "JOKER-v1-proyecto-personal"},
        )
        respuesta.raise_for_status()
    except requests.RequestException as e:
        raise ToolError(
            f"No pude conectar con Google Noticias para buscar {de_que}: {e}. "
            "Puede ser que no haya internet, o que la fuente esté caída."
        ) from e

    noticias = _analizar_noticias(respuesta.text, cuantas)
    if not noticias:
        if tema:
            raise ToolError(
                f"No hay titulares {de_que}. Prueba con menos palabras, o amplía "
                f"los días (ahora está en {dias})."
            )
        raise ToolError("Google Noticias no ha devuelto ningún titular de portada.")

    lineas = [f"Titulares {de_que} (fuente: Google Noticias, hora de España):"]
    for i, n in enumerate(noticias, start=1):
        lineas.append(f"{i}. {n['titular']}  [{n['medio']}, {n['fecha']}]")
    lineas.append(
        "IMPORTANTE: esto son titulares, no artículos. Cuenta lo que dicen los "
        "titulares y cita el medio; no te inventes detalles que no aparezcan aquí."
    )
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Tool 5: consultar_gym — el plan de entrenamiento del usuario
# ---------------------------------------------------------------------------

def consultar_gym() -> str:
    """
    Devuelve el plan de J0KER GYM del usuario: sus números, su rutina de la
    semana, el menú y los plazos. Así JOKER puede hablar de ello por el chat
    sin inventarse nada: lee exactamente lo mismo que muestra la página /gym.
    """
    import gym  # import diferido: solo se carga si se usa esta tool

    perfil = gym.leer_perfil()
    if not perfil:
        raise ToolError(
            "Todavía no hay ningún perfil de gimnasio guardado. Dile al usuario que "
            "entre en la página /gym y rellene sus datos (peso, altura, edad y objetivo) "
            "para que pueda calcularle el plan."
        )

    return gym.resumen_texto(gym.plan_completo(perfil))


# ---------------------------------------------------------------------------
# Tool 7: consultar_gastos — las cuentas del mes
# ---------------------------------------------------------------------------

def consultar_gastos() -> str:
    """
    Devuelve el reparto del mes del usuario: cuánto ingresa, cuánto lleva
    gastado, cómo va cada parte de su regla, sus deudas y los avisos. Lo mismo
    que muestra la página /gastos, para que JOKER pueda hablarlo por el chat
    sin inventarse una cifra.
    """
    import gastos  # import diferido: solo se carga si se usa esta tool

    perfil = gastos.leer_perfil()
    if not perfil:
        raise ToolError(
            "Todavía no hay cuentas guardadas. Dile al usuario que entre en la página "
            "/gastos, ponga cuánto ingresa al mes y elija una regla de reparto."
        )

    return gastos.resumen_texto(gastos.panel_completo(perfil))


# ---------------------------------------------------------------------------
# Tool 8: cotizacion_bolsa — cuánto vale algo hoy
# ---------------------------------------------------------------------------

def cotizacion_bolsa(simbolo: str) -> str:
    """
    El precio de una acción, un índice, una divisa o una cripto.

    Sale de Stooq: gratis, sin clave y sin registro. A cambio llega con
    retraso, así que se dice la fecha y la hora del dato en vez de dejar que
    parezca tiempo real.
    """
    import inversiones  # import diferido

    simbolo = (simbolo or "").strip()
    if not simbolo:
        raise ToolError("Dime qué símbolo quieres mirar (por ejemplo AAPL.US o ^IBEX).")

    dato = inversiones.cotizacion(simbolo)
    if not dato:
        raise ToolError(
            f"No he podido leer '{simbolo}'. Los símbolos llevan sufijo de mercado: "
            f"AAPL.US para EE. UU., ITX.ES para España, ^SPX o ^IBEX para índices, "
            f"EURUSD para divisas, BTCUSD para bitcoin. Comprueba que sea uno de esos, "
            f"o puede que no haya internet."
        )

    partes = [f"{dato['simbolo']}: {dato['precio']}"]
    if dato["variacion_dia"] is not None:
        partes.append(f"({dato['variacion_dia']:+.2f}% en el día)")
    if dato["minimo"] is not None and dato["maximo"] is not None:
        partes.append(f"rango del día {dato['minimo']}-{dato['maximo']}")
    partes.append(f"dato del {dato['fecha']} {dato['hora']}".rstrip())

    return (" · ".join(partes) +
            ". Es una cotización gratuita con retraso, no tiempo real: dilo si el "
            "usuario va a tomar una decisión con ella.")


# ---------------------------------------------------------------------------
# Tool 9: consultar_cartera — dónde tiene metido el dinero
# ---------------------------------------------------------------------------
# Esta tool es distinta a las demás: los datos están CIFRADOS, y solo se pueden
# leer si el usuario ha desbloqueado su cartera en la página. La contraseña
# vive en la memoria del servidor, nunca aquí.

import threading

_CONTEXTO = threading.local()


def poner_clave_cartera(clave: str | None) -> None:
    """
    El servidor deja aquí la contraseña de la cartera ANTES de cada turno, y la
    quita después. Va en threading.local y no en una variable normal porque el
    servidor puede atender a varias pestañas a la vez, y la contraseña de una
    no puede acabar sirviendo a otra.
    """
    _CONTEXTO.clave_cartera = clave


def consultar_cartera() -> str:
    """
    Qué tiene el usuario invertido, cuánto puso y cuánto vale hoy.

    Solo funciona con la cartera desbloqueada. Si está cerrada no hay forma de
    leerla, y eso no es un fallo: es justo lo que se pidió al cifrarla.
    """
    import inversiones  # import diferido

    clave = getattr(_CONTEXTO, "clave_cartera", None)
    if not clave:
        if not inversiones.hay_cartera():
            raise ToolError(
                "El usuario todavía no ha creado su cartera. Dile que entre en la "
                "página /inversiones y la cree: le pedirá una contraseña, y lo que "
                "apunte quedará cifrado en su ordenador."
            )
        raise ToolError(
            "La cartera está cerrada con llave y no puedo abrirla: está cifrada con "
            "una contraseña que solo sabe el usuario. Dile que la desbloquee en la "
            "página /inversiones y que vuelva a preguntarte. NO le pidas la "
            "contraseña por el chat."
        )

    try:
        cartera = inversiones.leer_cartera(clave)
    except (inversiones.ClaveIncorrecta, inversiones.SinCartera):
        raise ToolError("La cartera ya no se puede abrir con la sesión actual. "
                        "Dile al usuario que vuelva a desbloquearla en /inversiones.")

    return inversiones.resumen_texto(inversiones.valorar(cartera))


# ---------------------------------------------------------------------------
# Tool 10: convertir_moneda — cuánto es esto en euros
# ---------------------------------------------------------------------------

def convertir_moneda(cantidad: float, desde: str, hasta: str = "EUR") -> str:
    """
    Pasa una cantidad de una moneda a otra con los cambios del Banco Central
    Europeo, que son los oficiales y no cuestan nada.
    """
    import requests

    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        raise ToolError("La cantidad tiene que ser un número.")

    desde = (desde or "").strip().upper()[:3]
    hasta = (hasta or "EUR").strip().upper()[:3]
    if len(desde) != 3 or len(hasta) != 3:
        raise ToolError("Las monedas van en código de tres letras: EUR, USD, GBP, JPY...")

    if desde == hasta:
        return f"{cantidad:g} {desde} son {cantidad:g} {hasta}, obviamente."

    try:
        r = requests.get("https://api.frankfurter.app/latest",
                         params={"amount": cantidad, "from": desde, "to": hasta},
                         timeout=10)
        if r.status_code == 404:
            raise ToolError(f"No conozco el par {desde}/{hasta}. El Banco Central "
                            f"Europeo no publica todas las monedas del mundo.")
        r.raise_for_status()
        datos = r.json()
    except requests.RequestException as e:
        raise ToolError(f"No he podido consultar el cambio: {e}") from e

    resultado = (datos.get("rates") or {}).get(hasta)
    if resultado is None:
        raise ToolError(f"No he obtenido el cambio de {desde} a {hasta}.")

    unidad = resultado / cantidad if cantidad else 0
    return (f"{cantidad:g} {desde} = {resultado:,.2f} {hasta} "
            f"(1 {desde} = {unidad:.4f} {hasta}, cambio del Banco Central Europeo "
            f"del {datos.get('date', 'hoy')}).")


# ---------------------------------------------------------------------------
# Tools 11 y 12: la libreta
# ---------------------------------------------------------------------------
# Un asistente que se olvida de todo en cuanto cierras la ventana sirve de poco.
# Esto es lo más simple que arregla eso: apuntar cosas y volver a leerlas. Se
# guarda en la misma base local que lo demás, sin salir del ordenador.

def _tabla_notas(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha  TEXT NOT NULL,
            texto  TEXT NOT NULL
        )
    """)


def _conexion_notas():
    import sqlite3
    from pathlib import Path
    con = sqlite3.connect(Path(__file__).parent / "joker.db")
    con.row_factory = sqlite3.Row
    return con


def guardar_nota(texto: str) -> str:
    """Apunta algo para que no se pierda al cerrar la conversación."""
    from datetime import datetime

    texto = (texto or "").strip()
    if not texto:
        raise ToolError("No me has dicho qué apuntar.")
    if len(texto) > 1000:
        raise ToolError("La nota es demasiado larga (más de 1000 caracteres). "
                        "Resúmela antes de guardarla.")

    ahora = datetime.now().isoformat(timespec="seconds")
    with _conexion_notas() as con:
        _tabla_notas(con)
        cur = con.execute("INSERT INTO notas (fecha, texto) VALUES (?, ?)", (ahora, texto))
        numero = cur.lastrowid

    return (f"Apuntado (nota {numero}). Está guardada en el ordenador del usuario, "
            f"no en internet.")


def leer_notas(buscar: str = "", cuantas: int = 10) -> str:
    """Lee lo apuntado, de lo último a lo primero."""
    cuantas = max(1, min(int(cuantas or 10), 50))
    buscar = (buscar or "").strip()

    with _conexion_notas() as con:
        _tabla_notas(con)
        if buscar:
            filas = con.execute(
                "SELECT * FROM notas WHERE texto LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{buscar}%", cuantas)).fetchall()
        else:
            filas = con.execute(
                "SELECT * FROM notas ORDER BY id DESC LIMIT ?", (cuantas,)).fetchall()

    if not filas:
        if buscar:
            raise ToolError(f"No hay ninguna nota que hable de '{buscar}'.")
        raise ToolError("La libreta está vacía: el usuario todavía no ha apuntado nada.")

    from datetime import datetime
    lineas = [f"Notas guardadas{f' sobre {buscar}' if buscar else ''}:"]
    for f in filas:
        try:
            cuando = datetime.fromisoformat(f["fecha"]).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            cuando = f["fecha"]
        lineas.append(f"  [{f['id']}] {cuando} — {f['texto']}")
    return "\n".join(lineas)


def borrar_nota(numero: int) -> str:
    """Quita una nota por su número."""
    try:
        numero = int(numero)
    except (TypeError, ValueError):
        raise ToolError("Dime el número de la nota que hay que borrar.")

    with _conexion_notas() as con:
        _tabla_notas(con)
        cur = con.execute("DELETE FROM notas WHERE id = ?", (numero,))
        if cur.rowcount == 0:
            raise ToolError(f"No hay ninguna nota con el número {numero}.")

    return f"Nota {numero} borrada."


# ---------------------------------------------------------------------------
# Registro de tools
# ---------------------------------------------------------------------------

# Esquemas en JSON Schema estándar. Tanto Gemini como Claude entienden este
# formato, así que la misma definición vale para los dos.
TOOL_SCHEMAS = [
    {
        "name": "get_datetime",
        "description": (
            "Obtiene la fecha y hora actual de una ciudad o ubicación. "
            "Úsala siempre que el usuario pregunte qué hora es, qué día es, "
            "o el horario en algún lugar del mundo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Ciudad o ubicación, por ejemplo 'Madrid' o 'Tokio'.",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Obtiene el clima y la temperatura actuales de cualquier ciudad, "
            "pueblo o país del mundo: estado del cielo, temperatura, sensación "
            "térmica, humedad y viento. Úsala SIEMPRE que el usuario pregunte "
            "por el tiempo, el clima, la temperatura, si hace frío o calor, si "
            "llueve o si nieva en algún sitio."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Ciudad, por ejemplo 'Barcelona'.",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": (
                        "Unidad de temperatura. Por defecto celsius; usa "
                        "fahrenheit solo si el usuario lo pide expresamente."
                    ),
                },
            },
            "required": ["location"],
        },
    },
    {
        "name": "calculate",
        "description": (
            "Resuelve una expresión matemática: sumas, restas, multiplicaciones, "
            "divisiones, potencias, raíces y funciones trigonométricas. Úsala "
            "para cualquier cálculo numérico en vez de calcularlo tú."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "Expresión a evaluar en sintaxis de Python, "
                        "por ejemplo '(45 * 8) / 3' o 'sqrt(16) + 2**3'."
                    ),
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "consultar_gym",
        "description": (
            "Consulta el plan de entrenamiento y nutrición del usuario en J0KER GYM: "
            "sus calorías, macros, IMC, la rutina de cada día de la semana, el menú "
            "recomendado y cuánto le falta para su meta. Úsala SIEMPRE que pregunte "
            "por su rutina, su dieta, sus calorías, qué le toca entrenar hoy, qué "
            "debería comer, o cuánto le queda para llegar a su objetivo."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "search_web",
        "description": (
            "Busca información en internet sobre una persona, un lugar, un "
            "concepto o un evento. Úsala cuando el usuario pregunte algo que "
            "no sepas con certeza o pida buscar/investigar sobre un tema. "
            "Solo encuentra lo que hay en Wikipedia: sirve para lo que ya es "
            "historia (personas, lugares, conceptos, hechos pasados). Para lo "
            "que está pasando ahora usa buscar_noticias."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Qué buscar, por ejemplo 'Real Madrid' o 'Marie Curie'.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "consultar_gastos",
        "description": (
            "Consulta las cuentas del usuario en J0KER GASTOS: lo que ingresa al mes, "
            "lo que lleva gastado, cómo va cada parte de su regla de reparto "
            "(50/30/20 y demás), si se está pasando, sus deudas y cuánto tardaría en "
            "quitárselas. Úsala SIEMPRE que pregunte por su dinero, sus gastos, si "
            "puede permitirse algo, cuánto lleva ahorrado este mes, sus deudas o su "
            "presupuesto."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "buscar_noticias",
        "description": (
            "Busca TITULARES DE ACTUALIDAD de medios reales, con su fecha y su "
            "medio. Úsala SIEMPRE que la pregunta vaya de algo de hoy, de esta "
            "semana o de lo que está pasando: noticias, quién ha ganado algo, "
            "cómo va un tema en marcha, qué se dice de alguien ahora mismo, "
            "resultados recientes, o cuando el usuario pida 'ponme al día'. "
            "search_web (Wikipedia) sirve para lo que ya es historia; esta, para "
            "lo de ahora. Si dudas entre las dos y la pregunta tiene que ver con "
            "el presente, usa esta. Devuelve titulares, NO artículos: cuenta lo "
            "que dicen los titulares citando el medio, y no rellenes lo que falte."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tema": {
                    "type": "string",
                    "description": (
                        "Sobre qué. Pocas palabras funcionan mejor: 'incendios "
                        "Galicia', 'Real Madrid', 'precio de la luz'. Déjalo "
                        "vacío para la portada del día."
                    ),
                },
                "dias": {
                    "type": "integer",
                    "description": (
                        "Cuántos días hacia atrás mirar. 1 para hoy, 7 por "
                        "defecto, 30 para el mes."
                    ),
                },
                "cuantas": {
                    "type": "integer",
                    "description": "Cuántos titulares traer (1-15, por defecto 8).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "cotizacion_bolsa",
        "description": (
            "El precio de una acción, un índice de bolsa, una divisa o una "
            "criptomoneda. Úsala cuando pregunten cuánto vale algo que cotiza: "
            "'¿a cuánto está Apple?', '¿cómo va el IBEX?', '¿cuánto vale el "
            "bitcoin?'. Es una cotización gratuita CON RETRASO, no tiempo real: "
            "dilo al darla."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "simbolo": {
                    "type": "string",
                    "description": (
                        "El símbolo con su sufijo de mercado: AAPL.US, MSFT.US "
                        "(EE. UU.); ITX.ES, SAN.ES (España); ^SPX, ^NDQ, ^IBEX, "
                        "^DAX (índices); EURUSD, EURGBP (divisas); BTCUSD, ETHUSD "
                        "(cripto). Si el usuario dice el nombre de la empresa, "
                        "tradúcelo tú al símbolo."
                    ),
                }
            },
            "required": ["simbolo"],
        },
    },
    {
        "name": "consultar_cartera",
        "description": (
            "Qué tiene el usuario invertido: en qué empresas, cuánto puso, cuánto "
            "vale hoy y cuánto gana o pierde. Úsala cuando pregunte por SUS "
            "inversiones, su cartera o cómo van sus acciones. Los datos están "
            "cifrados: si la cartera está cerrada, la tool te lo dirá y lo único "
            "que hay que hacer es pedirle que la desbloquee en la página. NUNCA le "
            "pidas la contraseña por el chat, ni la repitas si la escribe."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "convertir_moneda",
        "description": (
            "Pasa una cantidad de una moneda a otra con los cambios oficiales del "
            "Banco Central Europeo. Úsala siempre que haya que convertir dinero, "
            "en vez de calcularlo de memoria con un cambio que puede estar viejo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cantidad": {"type": "number", "description": "Cuánto convertir."},
                "desde": {"type": "string", "description": "Moneda de origen: EUR, USD, GBP, JPY..."},
                "hasta": {"type": "string", "description": "Moneda de destino. Por defecto EUR."},
            },
            "required": ["cantidad", "desde"],
        },
    },
    {
        "name": "guardar_nota",
        "description": (
            "Apunta algo en la libreta del usuario para que no se pierda al cerrar "
            "la conversación. Úsala cuando te pida recordar algo ('apúntame que...', "
            "'recuérdame que...', 'guarda esto'), y también cuando cuente un dato "
            "suyo que claramente va a querer recuperar más adelante. Se guarda en su "
            "ordenador, no en internet."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texto": {
                    "type": "string",
                    "description": "Lo que hay que apuntar, redactado para que se "
                                   "entienda solo dentro de un mes.",
                }
            },
            "required": ["texto"],
        },
    },
    {
        "name": "leer_notas",
        "description": (
            "Lee lo que el usuario tiene apuntado en su libreta. Úsala cuando "
            "pregunte qué tenía apuntado, qué le habías guardado, o cuando busque "
            "algo que te dijo hace tiempo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "buscar": {
                    "type": "string",
                    "description": "Palabra para filtrar las notas. Déjalo vacío "
                                   "para ver las últimas.",
                },
                "cuantas": {
                    "type": "integer",
                    "description": "Cuántas traer (1-50, por defecto 10).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "borrar_nota",
        "description": (
            "Quita una nota de la libreta por su número. Úsala solo si el usuario "
            "lo pide claramente; si no sabes qué número es, léelas antes con "
            "leer_notas y confirma cuál."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "numero": {"type": "integer", "description": "El número de la nota."},
            },
            "required": ["numero"],
        },
    },
]

TOOL_FUNCTIONS = {
    "get_datetime": get_datetime,
    "get_weather": get_weather,
    "calculate": calculate,
    "search_web": search_web,
    "buscar_noticias": buscar_noticias,
    "consultar_gym": consultar_gym,
    "consultar_gastos": consultar_gastos,
    "cotizacion_bolsa": cotizacion_bolsa,
    "consultar_cartera": consultar_cartera,
    "convertir_moneda": convertir_moneda,
    "guardar_nota": guardar_nota,
    "leer_notas": leer_notas,
    "borrar_nota": borrar_nota,
}


def execute_tool(name: str, arguments: dict) -> tuple[str, bool]:
    """
    Ejecuta una tool por su nombre. Devuelve (texto_resultado, hubo_error).

    Nunca lanza excepciones: los errores se devuelven como texto para que el
    modelo pueda leerlos, explicárselos al usuario o probar otra cosa.
    """
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Tool desconocida: {name}", True
    try:
        return str(func(**arguments)), False
    except ToolError as e:
        return str(e), True
    except TypeError as e:
        return f"Argumentos inválidos para '{name}': {e}", True
    except Exception as e:
        return f"Error inesperado ejecutando '{name}': {e}", True
