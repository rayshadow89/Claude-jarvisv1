"""
El PIN de la casa.

Es la pantalla que tapa JOKER entero cuando alguien que no eres tú abre el
portátil. Conviene tener claro qué es y qué NO es:

  LO QUE ES     una cortina. El PIN se guarda como un hash con scrypt, así que
                no está escrito en ninguna parte, y sin él la web no se abre.

  LO QUE NO ES  cifrado. El gimnasio, los gastos y las notas siguen guardados
                en claro dentro de joker.db. Quien coja el fichero y lo abra
                con otro programa los ve, con PIN o sin él.

Esa diferencia es a propósito y está explicada en la web: la cartera de
inversiones sí va cifrada de verdad, porque ahí sí compensa escribir una
contraseña larga cada vez. Para mirar cuántas series tocan hoy, no.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from pathlib import Path

BASE_DATOS = Path(__file__).parent / "joker.db"

PIN_MINIMO = 4
PIN_MAXIMO = 32
SCRYPT_N = 2 ** 14      # ~50 ms: suficiente para un PIN que se escribe a diario


def _conexion() -> sqlite3.Connection:
    con = sqlite3.connect(BASE_DATOS)
    con.row_factory = sqlite3.Row
    return con


def _tabla(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS acceso (
            id     INTEGER PRIMARY KEY CHECK (id = 1),
            sal    BLOB NOT NULL,
            huella BLOB NOT NULL,
            creado TEXT NOT NULL
        )
    """)


def _huella(pin: str, sal: bytes) -> bytes:
    return hashlib.scrypt(pin.encode("utf-8"), salt=sal, n=SCRYPT_N, r=8, p=1,
                          dklen=32, maxmem=64 * 1024 * 1024)


def hay_pin() -> bool:
    with _conexion() as con:
        _tabla(con)
        return con.execute("SELECT 1 FROM acceso WHERE id = 1").fetchone() is not None


def poner_pin(pin: str) -> None:
    from datetime import datetime

    pin = (pin or "").strip()
    if len(pin) < PIN_MINIMO:
        raise ValueError(f"El PIN necesita al menos {PIN_MINIMO} caracteres.")
    if len(pin) > PIN_MAXIMO:
        raise ValueError(f"El PIN no puede pasar de {PIN_MAXIMO} caracteres.")

    sal = os.urandom(16)
    with _conexion() as con:
        _tabla(con)
        con.execute(
            "INSERT INTO acceso (id, sal, huella, creado) VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET sal=excluded.sal, huella=excluded.huella",
            (sal, _huella(pin, sal), datetime.now().isoformat(timespec="seconds")),
        )


def comprobar_pin(pin: str) -> bool:
    """
    ¿Es este el PIN? Se compara con compare_digest y no con ==, para que el
    tiempo que tarda no delate cuántos caracteres se han acertado.
    """
    with _conexion() as con:
        _tabla(con)
        fila = con.execute("SELECT sal, huella FROM acceso WHERE id = 1").fetchone()
    if fila is None:
        return True                    # sin PIN puesto, la casa está abierta
    return hmac.compare_digest(_huella(pin or "", fila["sal"]), fila["huella"])


def quitar_pin(pin: str) -> None:
    if not comprobar_pin(pin):
        raise ValueError("Ese PIN no es el bueno.")
    with _conexion() as con:
        _tabla(con)
        con.execute("DELETE FROM acceso WHERE id = 1")


def cambiar_pin(viejo: str, nuevo: str) -> None:
    if not comprobar_pin(viejo):
        raise ValueError("El PIN actual no es el bueno.")
    poner_pin(nuevo)
