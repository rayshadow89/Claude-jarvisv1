"""
Copia de seguridad: llevarte tus datos, y traerlos de vuelta.

Hasta ahora, "todo se queda en tu ordenador" tenía una letra pequeña incómoda:
se quedaba en ESE ordenador y para siempre. Si el disco se rompe o cambias de
portátil, se pierde todo. Esto lo arregla.

Lo que sale es un único fichero .json con todo dentro. Dos cosas que conviene
saber sobre él:

  LA CARTERA VIAJA CIFRADA. No se descifra para exportarla: se copia el bloque
  tal cual, con su sal y su nonce. El fichero de copia es tan ilegible como el
  original, y hace falta la misma contraseña para abrirlo donde lo restaures.

  EL RESTO VIAJA EN CLARO, igual que está en joker.db. Tu peso, tus gastos y
  tus notas se leen abriendo el fichero. Si lo vas a guardar en la nube o
  mandártelo por correo, tenlo en cuenta: esto es una copia de seguridad, no
  una caja fuerte.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DATOS = Path(__file__).parent / "joker.db"
VERSION = 1

# Qué se copia. Si una tabla no existe todavía (porque no has usado esa sala),
# se salta sin quejarse: una copia de una casa a medio amueblar es válida.
TABLAS = [
    "perfil_gym", "pesos", "rutina_propia", "dias_hechos",
    "finanzas", "gastos", "deudas",
    "notas",
    "cartera",
    "acceso",
]

# Columnas que son bytes y no texto. En JSON no caben tal cual, así que viajan
# en base64 y se marcan para poder devolverlas a su sitio al restaurar.
COLUMNAS_BINARIAS = {"sal", "nonce", "cuerpo", "huella"}


def _conexion() -> sqlite3.Connection:
    con = sqlite3.connect(BASE_DATOS)
    con.row_factory = sqlite3.Row
    return con


def _existe(con: sqlite3.Connection, tabla: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    ).fetchone() is not None


def exportar() -> dict:
    """Todo lo que hay en joker.db, listo para escribirse como JSON."""
    datos, cuenta = {}, {}
    with _conexion() as con:
        for tabla in TABLAS:
            if not _existe(con, tabla):
                continue
            filas = []
            for fila in con.execute(f"SELECT * FROM {tabla}").fetchall():
                limpia = {}
                for clave in fila.keys():
                    valor = fila[clave]
                    if isinstance(valor, (bytes, bytearray)):
                        limpia[clave] = {"__b64__": base64.b64encode(valor).decode()}
                    else:
                        limpia[clave] = valor
                filas.append(limpia)
            datos[tabla] = filas
            cuenta[tabla] = len(filas)

    return {
        "programa": "JOKER",
        "version": VERSION,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "aviso": ("La cartera de inversiones viaja CIFRADA y necesita su contraseña. "
                  "El resto (gimnasio, gastos, notas) va en claro: guarda este "
                  "fichero donde guardarías una libreta con tus cosas."),
        "cuenta": cuenta,
        "tablas": datos,
    }


def resumen(copia: dict) -> dict:
    """Qué trae una copia, para poder enseñarlo ANTES de restaurar nada."""
    cuenta = copia.get("cuenta") or {}
    tablas = copia.get("tablas") or {}
    if not cuenta:
        cuenta = {t: len(f) for t, f in tablas.items()}

    return {
        "fecha": copia.get("fecha", "desconocida"),
        "version": copia.get("version"),
        "hay_gym": bool(cuenta.get("perfil_gym")),
        "pesos": cuenta.get("pesos", 0),
        "hay_gastos": bool(cuenta.get("finanzas")),
        "gastos": cuenta.get("gastos", 0),
        "deudas": cuenta.get("deudas", 0),
        "notas": cuenta.get("notas", 0),
        "hay_cartera": bool(cuenta.get("cartera")),
        "hay_pin": bool(cuenta.get("acceso")),
    }


def comprobar(copia) -> None:
    """
    ¿Esto es una copia de JOKER? Se mira ANTES de tocar nada, porque restaurar
    borra lo que hay: si el fichero es otra cosa, hay que enterarse antes de
    haber perdido los datos buenos.
    """
    if not isinstance(copia, dict):
        raise ValueError("Ese fichero no es una copia de JOKER.")
    if copia.get("programa") != "JOKER":
        raise ValueError("Ese fichero no es una copia de JOKER (le falta la marca).")

    version = copia.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise ValueError(
            f"Esa copia es de una versión más nueva de JOKER (v{version}). "
            f"Actualiza el programa antes de restaurarla.")

    tablas = copia.get("tablas")
    if not isinstance(tablas, dict) or not tablas:
        raise ValueError("La copia no trae ninguna tabla: está vacía o dañada.")

    desconocidas = set(tablas) - set(TABLAS)
    if desconocidas:
        raise ValueError(f"La copia trae tablas que no reconozco: "
                         f"{', '.join(sorted(desconocidas))}.")

    for tabla, filas in tablas.items():
        if not isinstance(filas, list):
            raise ValueError(f"La tabla '{tabla}' de la copia está dañada.")


def restaurar(copia: dict) -> dict:
    """
    Deja joker.db como estaba en la copia. Lo que haya ahora se pierde.

    Va todo dentro de una transacción: si algo falla a mitad, no se queda una
    base medio restaurada, que sería peor que no haber empezado.
    """
    comprobar(copia)
    tablas = copia["tablas"]
    puestas = {}

    con = _conexion()
    try:
        con.execute("BEGIN")
        for tabla in TABLAS:
            if tabla not in tablas or not _existe(con, tabla):
                continue

            con.execute(f"DELETE FROM {tabla}")
            filas = tablas[tabla]
            if not filas:
                puestas[tabla] = 0
                continue

            columnas_reales = {c[1] for c in con.execute(f"PRAGMA table_info({tabla})")}
            metidas = 0
            for fila in filas:
                if not isinstance(fila, dict):
                    continue
                # Solo las columnas que esta versión conoce: si la copia es de
                # una versión anterior con menos campos, entra igual.
                columnas, valores = [], []
                for clave, valor in fila.items():
                    if clave not in columnas_reales:
                        continue
                    if isinstance(valor, dict) and "__b64__" in valor:
                        valor = base64.b64decode(valor["__b64__"])
                    columnas.append(clave)
                    valores.append(valor)
                if not columnas:
                    continue
                huecos = ", ".join("?" * len(columnas))
                con.execute(
                    f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({huecos})",
                    valores)
                metidas += 1
            puestas[tabla] = metidas

        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    return puestas


def preparar_tablas() -> None:
    """
    Se asegura de que todas las tablas existen antes de restaurar.

    Hace falta porque las tablas se crean la primera vez que usas cada sala: si
    restauras en una instalación recién estrenada, la mitad no existirían y sus
    datos se perderían en silencio.
    """
    import gastos, gym, inversiones, acceso

    with _conexion() as con:
        gym._tabla_pesos(con)
        gym._tabla_rutina(con)
        gym._tabla_completados(con)
        gastos._tablas(con)
        inversiones._tabla(con)
        acceso._tabla(con)
        con.execute("""CREATE TABLE IF NOT EXISTS perfil_gym (
            id INTEGER PRIMARY KEY CHECK (id = 1), datos TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL,
            texto TEXT NOT NULL)""")
