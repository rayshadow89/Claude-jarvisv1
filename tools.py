"""
Tools de Jarvis — la "lógica" real del asistente.
==================================================

Este módulo no sabe nada de Gemini ni de Claude: son funciones de Python
normales y corrientes. Eso permite que jarvis.py (Gemini) y jarvis_claude.py
(Anthropic) compartan exactamente las mismas capacidades.

Para añadirle una habilidad nueva a Jarvis:
  1. Escribe la función aquí abajo.
  2. Añade su esquema a TOOL_SCHEMAS.
  3. Regístrala en TOOL_FUNCTIONS.
No hace falta tocar nada más.
"""

from __future__ import annotations

import ast
import math
import operator
import os
from datetime import datetime
from zoneinfo import ZoneInfo


class ToolError(Exception):
    """Fallo esperado dentro de una tool (input inválido, falta una clave, etc.)."""


# ---------------------------------------------------------------------------
# Tool 1: get_datetime — hora actual de una ubicación
# ---------------------------------------------------------------------------

# Mapa mínimo ciudad -> zona horaria IANA. Amplíalo con las ciudades que uses.
CITY_TIMEZONES = {
    "madrid": "Europe/Madrid",
    "barcelona": "Europe/Madrid",
    "valencia": "Europe/Madrid",
    "sevilla": "Europe/Madrid",
    "bilbao": "Europe/Madrid",
    "canarias": "Atlantic/Canary",
    "las palmas": "Atlantic/Canary",
    "tenerife": "Atlantic/Canary",
    "lisboa": "Europe/Lisbon",
    "londres": "Europe/London",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "parís": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "berlín": "Europe/Berlin",
    "roma": "Europe/Rome",
    "moscu": "Europe/Moscow",
    "moscú": "Europe/Moscow",
    "nueva york": "America/New_York",
    "new york": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "ciudad de mexico": "America/Mexico_City",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "bogota": "America/Bogota",
    "lima": "America/Lima",
    "santiago": "America/Santiago",
    "tokio": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",
    "pekin": "Asia/Shanghai",
    "pekín": "Asia/Shanghai",
    "dubai": "Asia/Dubai",
    "sidney": "Australia/Sydney",
    "sydney": "Australia/Sydney",
}

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def get_datetime(location: str) -> str:
    """Devuelve la fecha y hora actual de una ciudad."""
    tz_name = CITY_TIMEZONES.get(location.strip().lower())
    if not tz_name:
        conocidas = ", ".join(sorted(CITY_TIMEZONES)[:8])
        raise ToolError(
            f"No tengo la zona horaria de '{location}'. "
            f"Añádela a CITY_TIMEZONES en tools.py. Algunas que sí conozco: {conocidas}..."
        )
    ahora = datetime.now(ZoneInfo(tz_name))
    dia = DIAS[ahora.weekday()]
    mes = MESES[ahora.month - 1]
    return (
        f"En {location} son las {ahora:%H:%M} del {dia} "
        f"{ahora.day} de {mes} de {ahora.year} (zona horaria {tz_name})."
    )


# ---------------------------------------------------------------------------
# Tool 2: get_weather — clima actual (OpenWeatherMap, capa gratuita)
# ---------------------------------------------------------------------------

def get_weather(location: str, unit: str = "celsius") -> str:
    """Devuelve el clima actual de una ciudad usando OpenWeatherMap."""
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise ToolError(
            "No hay OPENWEATHER_API_KEY configurada, así que no puedo consultar el "
            "clima. Se consigue gratis en https://openweathermap.org/api"
        )

    import requests  # import diferido: solo se carga si esta tool se usa

    units_param = "imperial" if unit == "fahrenheit" else "metric"
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": location, "appid": api_key, "units": units_param, "lang": "es"},
            timeout=10,
        )
    except requests.RequestException as e:
        raise ToolError(f"Error de red al consultar el clima: {e}") from e

    if resp.status_code == 401:
        raise ToolError("La OPENWEATHER_API_KEY no es válida.")
    if resp.status_code == 404:
        raise ToolError(f"No encontré la ubicación '{location}'.")
    if not resp.ok:
        raise ToolError(f"La API de clima devolvió un error ({resp.status_code}).")

    data = resp.json()
    simbolo = "°F" if units_param == "imperial" else "°C"
    return (
        f"En {location}: {data['weather'][0]['description']}, "
        f"{data['main']['temp']}{simbolo} "
        f"(sensación térmica {data['main']['feels_like']}{simbolo}), "
        f"humedad {data['main']['humidity']}%, "
        f"viento {data['wind']['speed']} m/s."
    )


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
            headers={"User-Agent": "Jarvis-v1-proyecto-personal"},
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
            headers={"User-Agent": "Jarvis-v1-proyecto-personal"},
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
            "Obtiene el clima actual (temperatura, condición, humedad, viento) "
            "de una ciudad. Úsala siempre que el usuario pregunte por el tiempo "
            "o el clima de un lugar."
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
                    "description": "Unidad de temperatura. Por defecto celsius.",
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
        "name": "search_web",
        "description": (
            "Busca información en internet sobre una persona, un lugar, un "
            "concepto o un evento. Úsala cuando el usuario pregunte algo que "
            "no sepas con certeza o pida buscar/investigar sobre un tema. "
            "Nota: solo encuentra lo que hay en Wikipedia, no noticias de última hora."
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
]

TOOL_FUNCTIONS = {
    "get_datetime": get_datetime,
    "get_weather": get_weather,
    "calculate": calculate,
    "search_web": search_web,
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
