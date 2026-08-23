"""
Jarvis v1 — asistente personal con function calling (Google Gemini)
====================================================================

Esta es la versión GRATUITA de Jarvis: usa la API de Gemini, que tiene una
capa gratuita (clave gratis, sin tarjeta, con límites de peticiones).

Cómo funciona, en cuatro pasos:
  1. Le mandamos a Gemini el mensaje del usuario + la lista de tools que sabe usar.
  2. Gemini responde: o bien con texto, o bien pidiendo llamar a una tool.
  3. Si pide una tool, la ejecutamos NOSOTROS aquí en local y le devolvemos el resultado.
  4. Repetimos hasta que Gemini ya no pida más tools y dé la respuesta final.

A ese ciclo se le llama "loop agéntico", y está en la función run_turn().

Las tools en sí viven en tools.py, para poder reutilizarlas.

Configuración:
  GEMINI_API_KEY      -> obligatoria. Gratis en https://aistudio.google.com/apikey
  OPENWEATHER_API_KEY -> opcional, solo para el clima. Gratis en https://openweathermap.org/api

Ejecutar:
  pip install -r requirements.txt
  python jarvis.py
"""

from __future__ import annotations

import os
import sys

from google import genai
from google.genai import errors, types

import tools

try:
    # Opcional: si tienes python-dotenv, carga las claves desde un fichero .env
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Los modelos "flash" son los que entran en la capa gratuita.
MODEL = "gemini-3.5-flash"

# Tope de vueltas del loop por cada mensaje del usuario. Evita bucles infinitos
# si el modelo se empeña en llamar tools una y otra vez.
MAX_ITERACIONES = 8

# Búsqueda en internet mediante Google Search, integrada en Gemini (no requiere
# código nuestro). Si tu modelo diera error al combinarla con tools propias,
# pon esto a False y Jarvis seguirá funcionando sin buscar en internet.
USAR_BUSQUEDA_WEB = True

SYSTEM_PROMPT = """Eres Jarvis, un asistente personal conversacional.
Eres cercano, directo y eficiente.

Cuando el usuario pregunte la hora o el clima de un lugar, o pida un cálculo
matemático, usa SIEMPRE la tool correspondiente en vez de inventarte la
respuesta. Si necesitas información actual de internet (noticias, datos que
cambian con el tiempo, cosas que no sabes con certeza), búscala.

Si una tool te devuelve un error, explícaselo al usuario en lenguaje llano y
dile qué puede hacer para arreglarlo.

Responde siempre en castellano, de forma breve y natural."""


# ---------------------------------------------------------------------------
# Traducción de nuestros esquemas al formato de Gemini
# ---------------------------------------------------------------------------

def construir_tools() -> list[types.Tool]:
    """Convierte los esquemas de tools.py en objetos Tool de Gemini."""
    declaraciones = [
        types.FunctionDeclaration(
            name=schema["name"],
            description=schema["description"],
            parameters_json_schema=schema["parameters"],
        )
        for schema in tools.TOOL_SCHEMAS
    ]
    lista = [types.Tool(function_declarations=declaraciones)]

    if USAR_BUSQUEDA_WEB:
        # Tool nativa de Google: se ejecuta en sus servidores, no escribimos nada.
        lista.append(types.Tool(google_search=types.GoogleSearch()))

    return lista


# ---------------------------------------------------------------------------
# El loop agéntico
# ---------------------------------------------------------------------------

def run_turn(client: genai.Client, contents: list, config: types.GenerateContentConfig):
    """
    Procesa un turno completo de conversación.

    Llama al modelo; si pide tools, las ejecuta y le devuelve los resultados;
    repite hasta que responda sin pedir nada más. Va añadiendo todo a
    `contents` (el historial), que se modifica in-place.

    Devuelve la respuesta final del modelo.
    """
    for _ in range(MAX_ITERACIONES):
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )

        # Guardamos el turno del modelo en el historial. Es imprescindible:
        # si no, en la siguiente vuelta el modelo no recordaría qué tool pidió.
        if response.candidates and response.candidates[0].content:
            contents.append(response.candidates[0].content)

        llamadas = response.function_calls
        if not llamadas:
            # No pide tools -> esto es la respuesta final.
            return response

        # Ejecutamos todas las tools que ha pedido (pueden ser varias a la vez)
        # y devolvemos todos los resultados juntos en un solo mensaje.
        partes = []
        for llamada in llamadas:
            argumentos = dict(llamada.args or {})
            resultado, hubo_error = tools.execute_tool(llamada.name, argumentos)

            print(f"   [tool] {llamada.name}({argumentos}) -> "
                  f"{'ERROR: ' if hubo_error else ''}{resultado}")

            partes.append(
                types.Part.from_function_response(
                    name=llamada.name,
                    response={"error" if hubo_error else "resultado": resultado},
                )
            )

        contents.append(types.Content(role="tool", parts=partes))

    raise RuntimeError(
        f"Jarvis se ha quedado dando vueltas ({MAX_ITERACIONES} iteraciones). "
        "Puede que una tool esté fallando en bucle."
    )


def extraer_texto(response) -> str:
    """Saca el texto de la respuesta, ignorando otros tipos de bloque."""
    if not response.candidates or not response.candidates[0].content:
        return ""
    partes = response.candidates[0].content.parts or []
    return "\n".join(p.text for p in partes if getattr(p, "text", None)).strip()


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print(
            "ERROR: falta la clave de la API.\n\n"
            "1. Consigue una gratis en https://aistudio.google.com/apikey\n"
            "2. Configúrala en esta misma terminal:\n\n"
            '     Windows PowerShell:  $env:GEMINI_API_KEY="tu-clave"\n'
            "     Windows cmd:         set GEMINI_API_KEY=tu-clave\n"
            '     Mac / Linux:         export GEMINI_API_KEY="tu-clave"\n',
            file=sys.stderr,
        )
        sys.exit(1)

    # El cliente coge la clave automáticamente de GEMINI_API_KEY.
    client = genai.Client()

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=construir_tools(),
        # Desactivamos el modo automático a propósito: queremos gestionar el
        # loop nosotros en run_turn() para ver y controlar qué se ejecuta.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents: list = []  # historial completo de la conversación

    print("Jarvis listo. Escribe 'salir' para terminar.\n")

    while True:
        try:
            entrada = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego!")
            break

        if not entrada:
            continue
        if entrada.lower() in {"salir", "exit", "quit", "adios", "adiós"}:
            print("¡Hasta luego!")
            break

        contents.append(types.Content(role="user", parts=[types.Part(text=entrada)]))

        try:
            response = run_turn(client, contents, config)
        except errors.ClientError as e:
            # 429 = has agotado la cuota gratuita por ahora; 400 = petición mal formada
            print(f"Jarvis: Error de la API ({e.code}): {e.message}\n")
            continue
        except errors.ServerError as e:
            print(f"Jarvis: Google está teniendo problemas ({e.code}). Reinténtalo.\n")
            continue
        except errors.APIError as e:
            print(f"Jarvis: Error con la API: {e}\n")
            continue
        except RuntimeError as e:
            print(f"Jarvis: {e}\n")
            continue

        texto = extraer_texto(response)
        print(f"Jarvis: {texto if texto else '(no he sabido qué responder)'}\n")


if __name__ == "__main__":
    main()
