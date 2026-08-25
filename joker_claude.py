"""
JOKER v1 — versión con la API de Claude (Anthropic)
=====================================================

OJO: esta versión es DE PAGO. La API de Anthropic se factura por uso y va
aparte de la suscripción de Claude.ai. La versión que se usa por defecto en
este proyecto es joker.py, que funciona con la capa gratuita de Gemini.

Este fichero se mantiene por dos motivos:
  - Sirve de comparación: el loop agéntico es el mismo concepto, cambia
    solo la forma de hablar con la API.
  - Si algún día quieres pasarte a Claude, ya está listo.

Configuración:
  ANTHROPIC_API_KEY   -> https://console.anthropic.com (requiere saldo)
  OPENWEATHER_API_KEY -> opcional, solo para el clima

Ejecutar:
  pip install anthropic
  python joker_claude.py
"""

from __future__ import annotations

import os
import sys

import anthropic

import tools

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# claude-opus-5 es el que mejor razona. Para gastar mucho menos, cambia a
# "claude-haiku-4-5" (unas 5 veces más barato).
MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_ITERACIONES = 8

SYSTEM_PROMPT = """Eres JOKER, un asistente personal conversacional.
Eres cercano, directo y eficiente.

Cuando el usuario pregunte la hora o el clima de un lugar, o pida un cálculo
matemático, usa SIEMPRE la tool correspondiente en vez de inventarte la
respuesta. Si necesitas información actual de internet, búscala en la web.

Si una tool te devuelve un error, explícaselo al usuario en lenguaje llano y
dile qué puede hacer para arreglarlo.

Responde siempre en castellano, de forma breve y natural."""


def construir_tools() -> list[dict]:
    """
    Traduce los esquemas de tools.py al formato de Anthropic.

    La única diferencia con Gemini es el nombre del campo: aquí el esquema de
    parámetros se llama 'input_schema' en vez de 'parameters'.
    """
    lista = [
        {
            "name": schema["name"],
            "description": schema["description"],
            "input_schema": schema["parameters"],
        }
        for schema in tools.TOOL_SCHEMAS
    ]
    # Búsqueda web nativa de Anthropic: se ejecuta en sus servidores.
    lista.append({"type": "web_search_20260209", "name": "web_search"})
    return lista


# ---------------------------------------------------------------------------
# El loop agéntico
# ---------------------------------------------------------------------------

def run_turn(client: anthropic.Anthropic, messages: list, tool_defs: list):
    """
    Procesa un turno completo: llama a la API, ejecuta las tools que Claude
    pida, le devuelve los resultados y repite hasta que termine.
    Modifica `messages` in-place.
    """
    for _ in range(MAX_ITERACIONES):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=tool_defs,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "pause_turn":
            # La búsqueda web (que corre en servidor) agotó sus iteraciones.
            # Reenviando tal cual, la API continúa donde se quedó.
            continue

        if response.stop_reason != "tool_use":
            return response  # end_turn, max_tokens, refusal... el turno acabó

        resultados = []
        for bloque in response.content:
            if bloque.type != "tool_use":
                continue
            contenido, hubo_error = tools.execute_tool(bloque.name, dict(bloque.input))

            print(f"   [tool] {bloque.name}({bloque.input}) -> "
                  f"{'ERROR: ' if hubo_error else ''}{contenido}")

            resultados.append({
                "type": "tool_result",
                "tool_use_id": bloque.id,
                "content": contenido,
                "is_error": hubo_error,
            })

        messages.append({"role": "user", "content": resultados})

    raise RuntimeError(
        f"JOKER se ha quedado dando vueltas ({MAX_ITERACIONES} iteraciones)."
    )


def extraer_texto(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: falta ANTHROPIC_API_KEY.\n"
            "Consigue una en https://console.anthropic.com (necesita saldo).\n"
            "Si prefieres la opción gratuita, ejecuta joker.py en su lugar.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic()
    tool_defs = construir_tools()
    messages: list = []

    print("JOKER (Claude) listo. Escribe 'salir' para terminar.\n")

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
            response = run_turn(client, messages, tool_defs)
        except anthropic.AuthenticationError:
            print("JOKER: La clave de API no es válida.\n")
            break
        except anthropic.RateLimitError as e:
            espera = e.response.headers.get("retry-after", "unos segundos")
            print(f"JOKER: Rate limit alcanzado, reinténtalo en {espera}.\n")
            continue
        except anthropic.APIConnectionError:
            print("JOKER: No pude conectar con la API. Revisa tu conexión.\n")
            continue
        except anthropic.APIStatusError as e:
            print(f"JOKER: Error de la API ({e.status_code}): {e.message}\n")
            continue
        except RuntimeError as e:
            print(f"JOKER: {e}\n")
            continue

        if response.stop_reason == "refusal":
            print("JOKER: Prefiero no responder a eso.\n")
            continue

        print(f"JOKER: {extraer_texto(response)}\n")


if __name__ == "__main__":
    main()
