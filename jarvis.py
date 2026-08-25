"""
Jarvis v1 — asistente personal con function calling (Groq)
=============================================================

Esta es la versión por defecto de Jarvis. Usa Groq, que aloja modelos de
código abierto y tiene un plan gratuito estable de verdad: sin tarjeta,
sin facturación oculta, sin "esto ya no es gratis, actualízate a la versión
nueva" (que es justo lo que nos pasó con Gemini — ver jarvis_gemini.py).

Groq es compatible con el formato de OpenAI, así que usamos la librería
`openai` apuntando a los servidores de Groq en vez de a los de OpenAI.

Cómo funciona, en cuatro pasos:
  1. Le mandamos al modelo el mensaje del usuario + la lista de tools que sabe usar.
  2. El modelo responde: o bien con texto, o bien pidiendo llamar a una tool.
  3. Si pide una tool, la ejecutamos NOSOTROS aquí en local y le devolvemos el resultado.
  4. Repetimos hasta que el modelo ya no pida más tools y dé la respuesta final.

A ese ciclo se le llama "loop agéntico", y está en la función run_turn().

Las tools en sí viven en tools.py, para poder reutilizarlas.

Configuración:
  GROQ_API_KEY        -> obligatoria. Gratis en https://console.groq.com/keys
  OPENWEATHER_API_KEY -> opcional, solo para el clima. Gratis en https://openweathermap.org/api

Ejecutar:
  pip install -r requirements.txt
  python jarvis.py
"""

from __future__ import annotations

import json
import os
import sys

import openai
from openai import OpenAI

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

# openai/gpt-oss-120b es el modelo de propósito general recomendado por Groq
# a día de hoy. Si quieres respuestas más rápidas (a costa de ser algo menos
# listo), prueba "openai/gpt-oss-20b". Lista completa siempre actualizada:
# https://console.groq.com/docs/models
MODEL = "openai/gpt-oss-120b"

# Tope de vueltas del loop por cada mensaje del usuario, para que no se quede
# pidiendo tools en bucle si algo va mal.
MAX_ITERACIONES = 8

SYSTEM_PROMPT = """Eres Jarvis, un asistente personal conversacional.
Eres cercano, directo y eficiente.

Cuando el usuario pregunte la hora o el clima de un lugar, pida un cálculo
matemático, o quiera buscar información sobre algo, usa SIEMPRE la tool
correspondiente en vez de inventarte la respuesta.

Si una tool te devuelve un error, explícaselo al usuario en lenguaje llano y
dile qué puede hacer para arreglarlo.

Responde siempre en castellano, de forma breve y natural."""


def construir_tools() -> list[dict]:
    """
    Traduce los esquemas de tools.py al formato de OpenAI/Groq: cada tool va
    envuelta en {"type": "function", "function": {...}}.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": schema["name"],
                "description": schema["description"],
                "parameters": schema["parameters"],
            },
        }
        for schema in tools.TOOL_SCHEMAS
    ]


# ---------------------------------------------------------------------------
# El loop agéntico
# ---------------------------------------------------------------------------

def run_turn(client: OpenAI, messages: list, tool_defs: list):
    """
    Procesa un turno completo: llama al modelo, ejecuta las tools que pida,
    le devuelve los resultados y repite hasta que responda sin pedir nada
    más. Modifica `messages` in-place para mantener el historial.

    Devuelve el mensaje final del modelo.
    """
    for _ in range(MAX_ITERACIONES):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_defs,
        )
        mensaje = response.choices[0].message

        # Guardamos el turno del modelo en el historial tal cual lo devuelve,
        # incluidas las tool_calls — si no, en la siguiente vuelta no sabría
        # qué tool pidió ni con qué argumentos.
        messages.append(mensaje.model_dump(exclude_unset=True))

        if not mensaje.tool_calls:
            return mensaje  # respuesta final, sin más tools que ejecutar

        for llamada in mensaje.tool_calls:
            argumentos = json.loads(llamada.function.arguments or "{}")
            resultado, hubo_error = tools.execute_tool(llamada.function.name, argumentos)

            print(f"   [tool] {llamada.function.name}({argumentos}) -> "
                  f"{'ERROR: ' if hubo_error else ''}{resultado}")

            messages.append({
                "role": "tool",
                "tool_call_id": llamada.id,
                "content": resultado,
            })

    raise RuntimeError(
        f"Jarvis se ha quedado dando vueltas ({MAX_ITERACIONES} iteraciones). "
        "Puede que una tool esté fallando en bucle."
    )


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    if not os.environ.get("GROQ_API_KEY"):
        print(
            "ERROR: falta la clave de la API.\n\n"
            "1. Consigue una gratis en https://console.groq.com/keys\n"
            "2. Configúrala en esta misma terminal:\n\n"
            '     Windows PowerShell:  $env:GROQ_API_KEY="tu-clave"\n'
            "     Windows cmd:         set GROQ_API_KEY=tu-clave\n"
            '     Mac / Linux:         export GROQ_API_KEY="tu-clave"\n',
            file=sys.stderr,
        )
        sys.exit(1)

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
    )
    tool_defs = construir_tools()
    messages: list = [{"role": "system", "content": SYSTEM_PROMPT}]

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

        messages.append({"role": "user", "content": entrada})

        try:
            mensaje = run_turn(client, messages, tool_defs)
        except openai.AuthenticationError:
            print("Jarvis: La clave de API no es válida. Revisa GROQ_API_KEY.\n")
            break
        except openai.RateLimitError:
            print("Jarvis: He llegado al límite de peticiones gratuitas por ahora. "
                  "Espera un minuto y vuelve a intentarlo.\n")
            continue
        except openai.APIConnectionError:
            print("Jarvis: No pude conectar con la API. Revisa tu conexión.\n")
            continue
        except openai.APIStatusError as e:
            print(f"Jarvis: Error de la API ({e.status_code}): {e.message}\n")
            continue
        except RuntimeError as e:
            print(f"Jarvis: {e}\n")
            continue

        print(f"Jarvis: {mensaje.content or '(no he sabido qué responder)'}\n")


if __name__ == "__main__":
    main()
