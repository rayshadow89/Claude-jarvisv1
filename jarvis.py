"""
Jarvis v1 — esqueleto de asistente personal con function calling (Anthropic API)
==================================================================================

Qué hace este esqueleto:
  - Llama a la Messages API de Anthropic con `tools` habilitado.
  - Implementa un loop agéntico manual: Claude pide usar una tool -> la
    ejecutamos localmente -> le devolvemos el resultado -> repetimos hasta
    que Claude tenga una respuesta final.
  - Incluye 3 tools de ejemplo que cubren lo que pide README.txt:
      1. get_datetime  -> hora de una ubicación
      2. get_weather   -> clima de una ubicación (usa OpenWeatherMap)
      3. calculate     -> matemáticas básicas (evaluador seguro, no usa eval())
    + la tool de búsqueda web nativa de Anthropic (server-side, sin código propio).

Cómo extenderlo:
  1. Escribe una función Python nueva (ej. tool_encender_luces).
  2. Añade su esquema JSON a TOOLS (name, description, input_schema).
  3. Regístrala en TOOL_FUNCTIONS.
  Claude decide solo cuándo llamarla según la descripción que le des —
  sé explícito sobre CUÁNDO debe usarla, no solo qué hace.

Configuración:
  - ANTHROPIC_API_KEY   -> tu clave de la API de Anthropic (o usa `ant auth login`)
  - OPENWEATHER_API_KEY -> opcional, para clima real (https://openweathermap.org/api)

Instalar dependencias:
  pip install -r requirements.txt
"""

from __future__ import annotations

import ast
import math
import operator
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

try:
    # Opcional: si tienes python-dotenv instalado, carga variables desde un .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Configuración general
# ---------------------------------------------------------------------------

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_CONTINUATIONS = 8  # límite de vueltas del loop agéntico por turno, evita bucles infinitos

SYSTEM_PROMPT = """Eres Jarvis, un asistente personal conversacional.
Eres cercano, directo y eficiente.

Cuando el usuario pregunte la hora o el clima de un lugar, o pida un cálculo
matemático, usa SIEMPRE la tool correspondiente en vez de inventar la
respuesta. Cuando necesites información actual de internet (noticias, datos
que cambian con el tiempo, hechos que no conoces con certeza), usa la tool
de búsqueda web.

Responde siempre en español, de forma breve y natural."""


# ---------------------------------------------------------------------------
# Errores esperados de una tool (se devuelven a Claude como is_error=True,
# para que pueda reaccionar o explicarle al usuario qué pasó)
# ---------------------------------------------------------------------------

class ToolError(Exception):
    """Fallo esperado dentro de una tool (input inválido, recurso no encontrado, etc.)."""


# ---------------------------------------------------------------------------
# Tool 1: get_datetime — hora actual de una ubicación
# ---------------------------------------------------------------------------

# Mapa mínimo ciudad -> zona horaria IANA. Para producción, sustitúyelo por
# una API de geocodificación + timezone (ej. https://timeapi.io) que resuelva
# cualquier ciudad automáticamente.
CITY_TIMEZONES = {
    "madrid": "Europe/Madrid",
    "barcelona": "Europe/Madrid",
    "ciudad de mexico": "America/Mexico_City",
    "cdmx": "America/Mexico_City",
    "mexico city": "America/Mexico_City",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "bogota": "America/Bogota",
    "lima": "America/Lima",
    "santiago": "America/Santiago",
    "nueva york": "America/New_York",
    "new york": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "londres": "Europe/London",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "tokio": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",
    "sidney": "Australia/Sydney",
    "sydney": "Australia/Sydney",
}

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def tool_get_datetime(location: str) -> str:
    tz_name = CITY_TIMEZONES.get(location.strip().lower())
    if not tz_name:
        raise ToolError(
            f"No tengo la zona horaria de '{location}' en mi mapa local. "
            "Añádela a CITY_TIMEZONES en jarvis.py, o integra una API de "
            "geocodificación/timezone para resolver cualquier ciudad."
        )
    now = datetime.now(ZoneInfo(tz_name))
    dia = DIAS[now.weekday()]
    mes = MESES[now.month - 1]
    return f"En {location} son las {now:%H:%M} del {dia} {now.day} de {mes} de {now.year} ({tz_name})."


# ---------------------------------------------------------------------------
# Tool 2: get_weather — clima actual de una ubicación (OpenWeatherMap)
# ---------------------------------------------------------------------------

def tool_get_weather(location: str, unit: str = "celsius") -> str:
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise ToolError(
            "No hay OPENWEATHER_API_KEY configurada. Consigue una clave gratis en "
            "https://openweathermap.org/api y expórtala como variable de entorno."
        )

    import requests  # import diferido: solo se necesita si esta tool se usa

    units_param = "imperial" if unit == "fahrenheit" else "metric"
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": location, "appid": api_key, "units": units_param, "lang": "es"},
            timeout=10,
        )
    except requests.RequestException as e:
        raise ToolError(f"Error de red al consultar el clima: {e}") from e

    if resp.status_code == 404:
        raise ToolError(f"No encontré la ubicación '{location}'.")
    if not resp.ok:
        raise ToolError(f"La API de clima devolvió un error ({resp.status_code}).")

    data = resp.json()
    desc = data["weather"][0]["description"]
    temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    symbol = "°F" if units_param == "imperial" else "°C"

    return (
        f"En {location}: {desc}, {temp}{symbol} "
        f"(sensación térmica {feels_like}{symbol}), humedad {humidity}%."
    )


# ---------------------------------------------------------------------------
# Tool 3: calculate — matemáticas básicas, con un evaluador seguro (sin eval())
# ---------------------------------------------------------------------------

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "abs": abs, "round": round,
}
_NAMES = {"pi": math.pi, "e": math.e}


def _eval_node(node: ast.AST):
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


def tool_calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
    except Exception as e:
        raise ToolError(f"No pude evaluar '{expression}': {e}") from e
    return f"{expression} = {result}"


# ---------------------------------------------------------------------------
# Registro de tools: esquema JSON (lo que ve Claude) + función Python (lo
# que se ejecuta localmente). Añade aquí cada tool nueva que crees.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_datetime",
        "description": (
            "Obtiene la fecha y hora actual de una ciudad o ubicación. "
            "Úsala cuando el usuario pregunte qué hora es, la fecha, o el "
            "horario en algún lugar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Ciudad o ubicación, ej. 'Madrid', 'Buenos Aires', 'Tokio'.",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "get_weather",
        "description": (
            "Obtiene el clima/tiempo atmosférico actual (temperatura, condición, "
            "humedad) de una ciudad. Úsala cuando el usuario pregunte por el "
            "clima o el tiempo de un lugar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Ciudad, ej. 'Barcelona'."},
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
            "Resuelve una expresión matemática (suma, resta, multiplicación, "
            "división, potencias, raíces, funciones trigonométricas). Úsala "
            "para cualquier cálculo numérico que pida el usuario en vez de "
            "calcularlo mentalmente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expresión a evaluar, ej. '(23 + 5) * 2 / 4' o 'sqrt(16) + 2**3'.",
                }
            },
            "required": ["expression"],
        },
    },
    # Tool nativa de Anthropic: búsqueda web. No requiere código propio,
    # se ejecuta server-side y Claude decide cuándo usarla.
    {"type": "web_search_20260209", "name": "web_search"},
]

TOOL_FUNCTIONS = {
    "get_datetime": tool_get_datetime,
    "get_weather": tool_get_weather,
    "calculate": tool_calculate,
}


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Ejecuta una tool local por nombre. Devuelve (contenido, is_error)."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Tool desconocida: {name}", True
    try:
        return str(func(**tool_input)), False
    except ToolError as e:
        return str(e), True
    except TypeError as e:
        return f"Argumentos inválidos para '{name}': {e}", True
    except Exception as e:  # cualquier fallo inesperado se reporta a Claude, no revienta el programa
        return f"Error inesperado ejecutando '{name}': {e}", True


# ---------------------------------------------------------------------------
# Loop agéntico: pide -> ejecuta tools -> reenvía resultados -> repite
# ---------------------------------------------------------------------------

def run_turn(client: anthropic.Anthropic, messages: list) -> anthropic.types.Message:
    """
    Ejecuta un turno completo: llama a la API, ejecuta las tools que Claude
    solicite, reenvía los resultados, y repite hasta que Claude termine
    (stop_reason distinto de "tool_use"/"pause_turn") o se agote el límite
    de continuaciones. Muta `messages` in-place para mantener el historial.
    """
    continuations = 0

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            # La tool de búsqueda web (server-side) llegó a su límite de
            # iteraciones. Reenviamos tal cual: el bloque server_tool_use al
            # final le indica a la API que debe continuar donde se quedó.
            continuations += 1
            if continuations > MAX_CONTINUATIONS:
                raise RuntimeError("Límite de continuaciones alcanzado (pause_turn).")
            continue

        if response.stop_reason != "tool_use":
            # end_turn, max_tokens, stop_sequence, refusal... el turno terminó.
            return response

        # Claude pidió una o más tools (pueden ser paralelas) -> ejecutarlas
        # todas y devolver todos los resultados en un único mensaje "user".
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue  # bloques de texto, o de server tools ya resueltos
            content, is_error = execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": is_error,
            })

        messages.append({"role": "user", "content": tool_results})

        continuations += 1
        if continuations > MAX_CONTINUATIONS:
            raise RuntimeError("Límite de continuaciones alcanzado (tool_use).")


def extract_text(response: anthropic.types.Message) -> str:
    return "\n".join(block.text for block in response.content if block.type == "text").strip()


# ---------------------------------------------------------------------------
# REPL principal
# ---------------------------------------------------------------------------

def main() -> None:
    # Resuelve credenciales automáticamente: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN,
    # o un perfil de `ant auth login`. No hace falta hardcodear la clave.
    client = anthropic.Anthropic()
    messages: list = []

    print("Jarvis listo. Escribe 'salir' para terminar.\n")

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"salir", "exit", "quit"}:
            print("¡Hasta luego!")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = run_turn(client, messages)
        except anthropic.AuthenticationError:
            print("Jarvis: Clave de API inválida. Revisa ANTHROPIC_API_KEY.")
            break
        except anthropic.RateLimitError as e:
            retry_after = e.response.headers.get("retry-after", "unos segundos")
            print(f"Jarvis: Estoy limitado por rate limit, reintenta en {retry_after}.\n")
            continue
        except anthropic.APIConnectionError:
            print("Jarvis: No pude conectar con la API. Revisa tu conexión.\n")
            continue
        except anthropic.APIStatusError as e:
            print(f"Jarvis: Error de la API ({e.status_code}): {e.message}\n")
            continue

        if response.stop_reason == "refusal":
            print("Jarvis: Prefiero no responder a eso.\n")
            continue

        print(f"Jarvis: {extract_text(response)}\n")


if __name__ == "__main__":
    main()
