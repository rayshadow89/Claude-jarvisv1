"""
J0KER INVERSIONES — tu cartera, cifrada, y lo que hace el mercado.

Dos partes que no se mezclan:

  LO TUYO      dónde tienes metido el dinero y cuánto. Se guarda CIFRADO con
               una contraseña que solo sabes tú. Sin ella, ni JOKER ni nadie
               puede leerlo: no es que esté "protegido", es que los bytes del
               fichero no significan nada.

  EL MERCADO   las cotizaciones. Son públicas, salen de una fuente gratuita
               (Stooq) y no hay nada que esconder ahí.


SOBRE EL CIFRADO, porque es la parte que importa
------------------------------------------------
De tu contraseña se saca una clave con scrypt, que está hecho a propósito para
ser LENTO: probar contraseñas a lo bruto sale caro. Con esa clave se cifra con
AES-256-GCM, que además de ocultar el contenido detecta si alguien ha tocado
un solo byte del fichero.

La contraseña NO se guarda en ningún sitio. Mientras el servidor está abierto
vive en su memoria; al cerrarlo, se olvida y la cartera vuelve a estar
bloqueada. Eso significa una cosa incómoda que conviene decir claro:

    SI OLVIDAS LA CONTRASEÑA, LOS DATOS SE PIERDEN.

No hay "he olvidado mi contraseña". Si lo hubiera, tampoco habría cifrado.


SOBRE LOS PRECIOS
-----------------
Stooq da cotizaciones gratis, sin registro y sin clave, en CSV. A cambio:
llegan con retraso (no es tiempo real) y no cubre todos los mercados. Para
mirar cómo va tu cartera sirve de sobra; para operar al segundo, no. La página
lo dice, en vez de dejar que parezca un terminal de bolsa.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path

BASE_DATOS = Path(__file__).parent / "joker.db"


class ClaveIncorrecta(Exception):
    """La contraseña no abre la cartera (o el fichero está tocado)."""


class SinCartera(Exception):
    """Todavía no hay ninguna cartera creada."""


# ---------------------------------------------------------------------------
# El cifrado
# ---------------------------------------------------------------------------

# Parámetros de scrypt. n=2^15 tarda ~100 ms en un portátil normal: ni se nota
# al escribir la contraseña, y multiplica por mucho lo que cuesta probar
# millones de ellas. Se guardan junto al dato para poder subirlos en el futuro
# sin dejar ilegibles las carteras viejas.
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
LONGITUD_CLAVE = 32          # 32 bytes = AES-256
CLAVE_MINIMA = 8             # caracteres


def _derivar(clave: str, sal: bytes, n: int = SCRYPT_N,
             r: int = SCRYPT_R, p: int = SCRYPT_P) -> bytes:
    """De la contraseña que escribes a la clave con la que se cifra."""
    return hashlib.scrypt(clave.encode("utf-8"), salt=sal,
                          n=n, r=r, p=p, dklen=LONGITUD_CLAVE,
                          maxmem=64 * 1024 * 1024)


def _cifrar(clave: str, datos: dict, sal: bytes | None = None) -> dict:
    """Devuelve el paquete cifrado listo para guardar."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    sal = sal or os.urandom(16)
    nonce = os.urandom(12)          # irrepetible: AES-GCM se rompe si se repite
    aes = AESGCM(_derivar(clave, sal))
    crudo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    return {
        "sal": sal,
        "nonce": nonce,
        "cuerpo": aes.encrypt(nonce, crudo, None),
        "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
    }


def _descifrar(clave: str, paquete: dict) -> dict:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aes = AESGCM(_derivar(clave, paquete["sal"],
                          paquete.get("n", SCRYPT_N),
                          paquete.get("r", SCRYPT_R),
                          paquete.get("p", SCRYPT_P)))
    try:
        crudo = aes.decrypt(paquete["nonce"], paquete["cuerpo"], None)
    except InvalidTag as e:
        # El mismo error para "contraseña mala" y "fichero manipulado": no hay
        # forma de distinguirlos, y tampoco conviene dar pistas.
        raise ClaveIncorrecta(
            "Esa contraseña no abre la cartera. Si estás seguro de que es la "
            "correcta, puede que el fichero esté dañado."
        ) from e
    return json.loads(crudo.decode("utf-8"))


# ---------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------

def _conexion() -> sqlite3.Connection:
    con = sqlite3.connect(BASE_DATOS)
    con.row_factory = sqlite3.Row
    return con


def _tabla(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS cartera (
            id      INTEGER PRIMARY KEY CHECK (id = 1),
            sal     BLOB NOT NULL,
            nonce   BLOB NOT NULL,
            cuerpo  BLOB NOT NULL,
            n       INTEGER NOT NULL,
            r       INTEGER NOT NULL,
            p       INTEGER NOT NULL,
            creada  TEXT NOT NULL
        )
    """)


def hay_cartera() -> bool:
    with _conexion() as con:
        _tabla(con)
        return con.execute("SELECT 1 FROM cartera WHERE id = 1").fetchone() is not None


def _guardar_paquete(paquete: dict) -> None:
    from datetime import datetime
    with _conexion() as con:
        _tabla(con)
        con.execute(
            "INSERT INTO cartera (id, sal, nonce, cuerpo, n, r, p, creada) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET sal=excluded.sal, nonce=excluded.nonce, "
            "cuerpo=excluded.cuerpo, n=excluded.n, r=excluded.r, p=excluded.p",
            (paquete["sal"], paquete["nonce"], paquete["cuerpo"],
             paquete["n"], paquete["r"], paquete["p"],
             datetime.now().isoformat(timespec="seconds")),
        )


def _leer_paquete() -> dict:
    with _conexion() as con:
        _tabla(con)
        fila = con.execute("SELECT * FROM cartera WHERE id = 1").fetchone()
    if fila is None:
        raise SinCartera("Todavía no hay ninguna cartera creada.")
    return {"sal": fila["sal"], "nonce": fila["nonce"], "cuerpo": fila["cuerpo"],
            "n": fila["n"], "r": fila["r"], "p": fila["p"], "creada": fila["creada"]}


def crear_cartera(clave: str) -> None:
    """La primera vez: cartera vacía, cifrada con la contraseña que elijas."""
    if len(clave) < CLAVE_MINIMA:
        raise ValueError(f"La contraseña necesita al menos {CLAVE_MINIMA} caracteres.")
    if hay_cartera():
        raise ValueError("Ya hay una cartera creada.")
    _guardar_paquete(_cifrar(clave, {"posiciones": [], "version": 1}))


def leer_cartera(clave: str) -> dict:
    """Abre la cartera. Lanza ClaveIncorrecta si la contraseña no vale."""
    return _descifrar(clave, _leer_paquete())


def guardar_cartera(clave: str, cartera: dict) -> None:
    """
    Vuelve a cifrar con la MISMA sal (así no hay que rederivar el coste de
    scrypt cada vez) pero con un nonce nuevo, que eso sí es obligatorio.
    """
    paquete = _leer_paquete()
    _guardar_paquete(_cifrar(clave, cartera, sal=paquete["sal"]))


def cambiar_clave(vieja: str, nueva: str) -> None:
    if len(nueva) < CLAVE_MINIMA:
        raise ValueError(f"La contraseña necesita al menos {CLAVE_MINIMA} caracteres.")
    cartera = leer_cartera(vieja)           # si la vieja no vale, para aquí
    _guardar_paquete(_cifrar(nueva, cartera))   # sal nueva, clave nueva


def borrar_cartera() -> None:
    with _conexion() as con:
        _tabla(con)
        con.execute("DELETE FROM cartera WHERE id = 1")


def info_cartera() -> dict:
    """Lo único que se puede saber SIN la contraseña: que existe y desde cuándo."""
    if not hay_cartera():
        return {"existe": False}
    paquete = _leer_paquete()
    return {"existe": True, "creada": paquete["creada"],
            "tamano": len(paquete["cuerpo"])}


# ---------------------------------------------------------------------------
# Las posiciones
# ---------------------------------------------------------------------------

MONEDAS = {"EUR": "€", "USD": "$", "GBP": "£"}


def _limpiar_posicion(cruda: dict) -> dict:
    """
    Deja una posición en su forma buena, o explota diciendo por qué.

    Se valida aquí y no solo en la web porque estos datos van a un fichero
    cifrado: si entra basura, se cifra la basura y luego no hay quien la
    arregle sin abrirlo todo.
    """
    empresa = str(cruda.get("empresa", "")).strip()[:80]
    if not empresa:
        raise ValueError("Cada posición necesita el nombre de la empresa.")

    try:
        participaciones = float(cruda.get("participaciones", 0))
        precio_compra = float(cruda.get("precio_compra", 0))
    except (TypeError, ValueError):
        raise ValueError("Las participaciones y el precio tienen que ser números.")

    if participaciones <= 0:
        raise ValueError(f"{empresa}: las participaciones tienen que ser más de 0.")
    if precio_compra <= 0:
        raise ValueError(f"{empresa}: el precio de compra tiene que ser más de 0.")

    moneda = str(cruda.get("moneda", "EUR")).upper()
    if moneda not in MONEDAS:
        moneda = "EUR"

    fecha = str(cruda.get("fecha", "")).strip()[:10]
    if fecha:
        from datetime import date
        try:
            date.fromisoformat(fecha)
        except ValueError:
            raise ValueError(f"{empresa}: la fecha de compra no es válida.")

    return {
        "id": str(cruda.get("id") or secrets.token_hex(8)),
        "empresa": empresa,
        "simbolo": str(cruda.get("simbolo", "")).strip().upper()[:20],
        "participaciones": round(participaciones, 6),
        "precio_compra": round(precio_compra, 6),
        "moneda": moneda,
        "fecha": fecha,
        "nota": str(cruda.get("nota", "")).strip()[:200],
    }


def normalizar_cartera(cartera: dict) -> dict:
    posiciones = [_limpiar_posicion(p) for p in (cartera.get("posiciones") or [])]
    return {"posiciones": posiciones, "version": 1}


# ---------------------------------------------------------------------------
# Las cotizaciones
# ---------------------------------------------------------------------------
# Stooq: CSV, gratis, sin registro y sin clave. Los símbolos llevan sufijo de
# mercado: aapl.us, itx.es, ^spx (índices), eurusd (divisas), btc.v (cripto).

STOOQ_ULTIMO = "https://stooq.com/q/l/"
STOOQ_HISTORICO = "https://stooq.com/q/d/l/"

# Las cotizaciones no cambian cada segundo y Stooq es un servicio gratuito:
# guardamos lo pedido un rato para no machacarlo ni hacer esperar al usuario.
_CACHE: dict[str, tuple] = {}
SEGUNDOS_CACHE = 300


def _de_cache(clave: str):
    guardado = _CACHE.get(clave)
    if guardado and time.time() - guardado[0] < SEGUNDOS_CACHE:
        return guardado[1]
    return None


def _a_cache(clave: str, valor):
    _CACHE[clave] = (time.time(), valor)
    return valor


def _numero(texto: str):
    """Stooq escribe 'N/D' cuando no tiene el dato. Eso no es un cero."""
    try:
        valor = float(texto)
    except (TypeError, ValueError):
        return None
    return valor


def analizar_cotizacion(csv_texto: str) -> dict | None:
    """
    Saca la cotización del CSV de Stooq.

    Separado de la descarga para poder probarlo sin internet, igual que se
    hizo con las noticias.
    """
    lineas = [l.strip() for l in csv_texto.strip().split("\n") if l.strip()]
    if len(lineas) < 2:
        return None

    cabecera = [c.strip().lower() for c in lineas[0].split(",")]
    valores = lineas[1].split(",")
    if len(valores) < len(cabecera):
        return None

    fila = dict(zip(cabecera, [v.strip() for v in valores]))
    cierre = _numero(fila.get("close"))
    if cierre is None:
        return None

    apertura = _numero(fila.get("open"))
    variacion = None
    if apertura:
        variacion = round((cierre - apertura) / apertura * 100, 2)

    return {
        "simbolo": fila.get("symbol", "").upper(),
        "precio": cierre,
        "apertura": apertura,
        "maximo": _numero(fila.get("high")),
        "minimo": _numero(fila.get("low")),
        "volumen": _numero(fila.get("volume")),
        "fecha": fila.get("date", ""),
        "hora": fila.get("time", ""),
        "variacion_dia": variacion,
    }


def analizar_historico(csv_texto: str, dias: int = 60) -> list:
    """Los últimos cierres, para pintar la línea. CSV: Date,Open,High,Low,Close,Volume."""
    lineas = [l.strip() for l in csv_texto.strip().split("\n") if l.strip()]
    if len(lineas) < 2:
        return []

    cabecera = [c.strip().lower() for c in lineas[0].split(",")]
    try:
        i_fecha, i_cierre = cabecera.index("date"), cabecera.index("close")
    except ValueError:
        return []

    puntos = []
    for linea in lineas[1:]:
        trozos = linea.split(",")
        if len(trozos) <= max(i_fecha, i_cierre):
            continue
        cierre = _numero(trozos[i_cierre])
        if cierre is None:
            continue
        puntos.append({"fecha": trozos[i_fecha].strip(), "cierre": cierre})

    return puntos[-dias:]


def cotizacion(simbolo: str) -> dict | None:
    """El último precio de un símbolo. None si no se puede saber."""
    simbolo = (simbolo or "").strip().lower()
    if not simbolo:
        return None

    guardado = _de_cache("c:" + simbolo)
    if guardado is not None:
        return guardado

    import requests
    try:
        r = requests.get(STOOQ_ULTIMO,
                         params={"s": simbolo, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
                         timeout=10, headers={"User-Agent": "JOKER-v1-proyecto-personal"})
        r.raise_for_status()
    except requests.RequestException:
        return None

    return _a_cache("c:" + simbolo, analizar_cotizacion(r.text))


def historico(simbolo: str, dias: int = 60) -> list:
    simbolo = (simbolo or "").strip().lower()
    if not simbolo:
        return []

    guardado = _de_cache(f"h:{simbolo}:{dias}")
    if guardado is not None:
        return guardado

    import requests
    try:
        r = requests.get(STOOQ_HISTORICO, params={"s": simbolo, "i": "d"},
                         timeout=12, headers={"User-Agent": "JOKER-v1-proyecto-personal"})
        r.raise_for_status()
    except requests.RequestException:
        return []

    return _a_cache(f"h:{simbolo}:{dias}", analizar_historico(r.text, dias))


# Lo que se enseña arriba aunque no tengas cartera: cómo va el mercado hoy.
INDICES = [
    {"simbolo": "^spx",  "nombre": "S&P 500",   "que_es": "las 500 mayores de EE. UU."},
    {"simbolo": "^ndq",  "nombre": "Nasdaq 100", "que_es": "tecnología de EE. UU."},
    {"simbolo": "^dax",  "nombre": "DAX",       "que_es": "las grandes de Alemania"},
    {"simbolo": "^ibex", "nombre": "IBEX 35",   "que_es": "las 35 grandes de España"},
    {"simbolo": "eurusd", "nombre": "EUR/USD",  "que_es": "cuántos dólares vale un euro"},
    {"simbolo": "btcusd", "nombre": "Bitcoin",  "que_es": "en dólares"},
]


def mercado_hoy() -> list:
    """Los índices de referencia. Los que no se puedan leer, se dicen como tal."""
    salida = []
    for indice in INDICES:
        dato = cotizacion(indice["simbolo"])
        salida.append({**indice, "cotizacion": dato, "hay_dato": dato is not None})
    return salida


# ---------------------------------------------------------------------------
# Las cuentas de la cartera
# ---------------------------------------------------------------------------

def _cambio(desde: str, hasta: str) -> float | None:
    """
    Cuánto vale una moneda en otra, según el Banco Central Europeo.

    Frankfurter es una fachada gratuita y sin clave sobre los datos del BCE.
    Si no responde, devolvemos None y la página dice que no ha podido
    convertir, en vez de inventarse un cambio.
    """
    if desde == hasta:
        return 1.0

    guardado = _de_cache(f"fx:{desde}:{hasta}")
    if guardado is not None:
        return guardado

    import requests
    try:
        r = requests.get("https://api.frankfurter.app/latest",
                         params={"from": desde, "to": hasta}, timeout=10)
        r.raise_for_status()
        tasa = r.json().get("rates", {}).get(hasta)
    except (requests.RequestException, ValueError):
        return None

    return _a_cache(f"fx:{desde}:{hasta}", float(tasa) if tasa else None)


def valorar(cartera: dict, moneda_base: str = "EUR", con_precios: bool = True) -> dict:
    """
    Pone números a la cartera: lo que costó, lo que vale y la diferencia.

    Las posiciones sin símbolo (o cuyo símbolo no encuentra precio) NO se
    inventan: cuentan en el coste y se dicen aparte. Es la diferencia entre
    "tu cartera vale X" y "de tu cartera sé valorar esta parte".
    """
    posiciones = []
    coste_total = 0.0
    valor_total = 0.0
    sin_precio = 0

    for p in cartera.get("posiciones", []):
        coste = p["participaciones"] * p["precio_compra"]
        fila = {**p, "coste": round(coste, 2)}

        dato = cotizacion(p["simbolo"]) if (con_precios and p["simbolo"]) else None
        if dato:
            valor = p["participaciones"] * dato["precio"]
            fila.update({
                "precio_actual": dato["precio"],
                "fecha_precio": dato["fecha"],
                "variacion_dia": dato["variacion_dia"],
                "valor": round(valor, 2),
                "ganancia": round(valor - coste, 2),
                "ganancia_pct": round((valor - coste) / coste * 100, 2) if coste else 0.0,
                "hay_precio": True,
            })
            valor_total += valor
        else:
            # No es lo mismo "esto no cotiza" que "no he podido preguntar el
            # precio". Lo primero es normal (un piso, un fondo sin símbolo); lo
            # segundo es que no hay internet, y conviene no confundirlos.
            fila.update({
                "hay_precio": False, "valor": None, "ganancia": None,
                "ganancia_pct": None,
                "motivo_sin_precio": ("sin_simbolo" if not p["simbolo"]
                                      else "no_se_pudo_consultar"),
            })
            sin_precio += 1
            valor_total += coste        # sin precio, lo mejor que sabemos es lo que costó

        coste_total += coste
        posiciones.append(fila)

    # El peso de cada una dentro del total, para el círculo
    for fila in posiciones:
        referencia = fila["valor"] if fila["hay_precio"] else fila["coste"]
        fila["peso"] = round(referencia / valor_total * 100, 2) if valor_total else 0.0

    posiciones.sort(key=lambda f: -(f["valor"] or f["coste"]))

    monedas = {p["moneda"] for p in cartera.get("posiciones", [])}
    return {
        "posiciones": posiciones,
        "coste_total": round(coste_total, 2),
        "valor_total": round(valor_total, 2),
        "ganancia": round(valor_total - coste_total, 2),
        "ganancia_pct": (round((valor_total - coste_total) / coste_total * 100, 2)
                         if coste_total else 0.0),
        "sin_precio": sin_precio,
        "cuantas": len(posiciones),
        "monedas": sorted(monedas),
        "varias_monedas": len(monedas) > 1,
        "moneda_base": moneda_base,
    }


def _cifra(numero: float) -> str:
    """
    Un número como se escribe en España: 1.234,56.

    Con una función, no con un apaño de reemplazos sobre la frase entera: eso
    convertía también las comas del texto en puntos y dejaba frases rotas.
    """
    return f"{numero:,.2f}".translate(str.maketrans({",": ".", ".": ","}))


def avisos_cartera(valoracion: dict) -> list:
    """
    Lo que conviene saber mirando TU cartera. Con cifras tuyas o no se dice.

    Nada de "diversifica": si el 70% está en una sola empresa, se dice el 70%
    y se dice cuál.
    """
    avisos = []
    posiciones = valoracion["posiciones"]
    if not posiciones:
        return avisos

    # 1. Concentración: la regla no escrita que más dinero ha costado
    mayor = max(posiciones, key=lambda p: p["peso"])
    if mayor["peso"] >= 40:
        avisos.append({
            "tipo": "aviso", "clase": "Mucho en un solo sitio",
            "texto": (f"El {mayor['peso']:.0f}% de tu cartera está en "
                      f"{mayor['empresa']}. Si eso cae un 20%, tú pierdes un "
                      f"{mayor['peso'] * 0.2:.0f}% de todo. No digo que sea mala idea: "
                      f"digo que sepas que es una apuesta, no una cartera."),
        })

    # 2. Cuántas cosas distintas hay de verdad
    if valoracion["cuantas"] == 1:
        avisos.append({
            "tipo": "consejo", "clase": "Una sola posición",
            "texto": "Con una sola empresa, tu cartera ES esa empresa. Todo lo que "
                     "le pase, te pasa entero.",
        })

    # 3. Lo que no se puede valorar
    if valoracion["sin_precio"]:
        sin, total = valoracion["sin_precio"], valoracion["cuantas"]
        fallaron = sum(1 for p in posiciones
                       if p.get("motivo_sin_precio") == "no_se_pudo_consultar")
        no_cotizan = sin - fallaron

        # La concordancia importa: "1 de tus 3 posiciones no tienen" se lee mal,
        # y en una página de dinero cada frase torcida resta confianza.
        if sin == total:
            cuantas = "Ninguna de tus posiciones tiene"
        elif sin == 1:
            cuantas = f"1 de tus {total} posiciones no tiene"
        else:
            cuantas = f"{sin} de tus {total} posiciones no tienen"

        if fallaron and no_cotizan:
            otras = ("la otra no cotiza" if no_cotizan == 1
                     else f"las otras {no_cotizan} no cotizan")
            pedir = ("1 no ha respondido al pedir el precio" if fallaron == 1
                     else f"{fallaron} no han respondido al pedir el precio")
            porque = f"{pedir} y {otras}"
        elif fallaron:
            porque = ("no he podido consultar su precio (¿hay internet?)" if fallaron == 1
                      else "no he podido consultar sus precios (¿hay internet?)")
        else:
            porque = ("no cotiza en ningún mercado" if no_cotizan == 1
                      else "no cotizan en ningún mercado")

        avisos.append({
            "tipo": "consejo", "clase": "Sin precio de mercado",
            "texto": (f"{cuantas} precio de mercado ahora mismo: {porque}. "
                      f"{'Ahí' if sin == 1 else 'Para esas'} cuento lo que pagaste, "
                      f"no lo que vale{'' if sin == 1 else 'n'} hoy, así que el total "
                      f"de arriba se queda corto o largo por esa parte."),
        })

    # 4. Monedas mezcladas: un total sumando euros y dólares no significa nada
    if valoracion["varias_monedas"]:
        avisos.append({
            "tipo": "aviso", "clase": "Monedas mezcladas",
            "texto": (f"Tienes posiciones en {', '.join(valoracion['monedas'])}. "
                      f"Los totales están sumados sin convertir, así que son "
                      f"orientativos: un euro y un dólar no valen lo mismo."),
        })

    # 5. Cómo va la cosa, en cifras suyas
    if valoracion["coste_total"] and valoracion["valor_total"] != valoracion["coste_total"]:
        g = valoracion["ganancia"]
        coletilla = ("Y cuidado con confundir suerte con acierto: unos meses "
                     "buenos no demuestran nada todavía." if g >= 0 else
                     "Una cartera en rojo no es una cartera rota. Lo es si vendes "
                     "por miedo justo abajo.")
        avisos.append({
            "tipo": "bien" if g >= 0 else "aviso",
            "clase": "Cómo vas" if g >= 0 else "Vas en rojo",
            "texto": (f"Pusiste {_cifra(valoracion['coste_total'])} y ahora son "
                      f"{_cifra(valoracion['valor_total'])}: "
                      f"{'ganas' if g >= 0 else 'pierdes'} {_cifra(abs(g))} "
                      f"({abs(valoracion['ganancia_pct']):.1f}%). {coletilla}"),
        })

    return avisos


def resumen_texto(valoracion: dict) -> str:
    """Para que JOKER pueda hablar de la cartera por el chat."""
    if not valoracion["posiciones"]:
        return "La cartera está abierta pero vacía: no hay ninguna posición apuntada."

    lineas = [
        f"Cartera: {valoracion['cuantas']} posiciones. Invertido "
        f"{valoracion['coste_total']:.2f}, valor actual {valoracion['valor_total']:.2f}, "
        f"diferencia {valoracion['ganancia']:+.2f} ({valoracion['ganancia_pct']:+.2f}%)."
    ]
    for p in valoracion["posiciones"]:
        if p["hay_precio"]:
            lineas.append(
                f"  - {p['empresa']} ({p['simbolo']}): {p['participaciones']:g} x "
                f"{p['precio_compra']:.2f} = {p['coste']:.2f} {p['moneda']}; "
                f"hoy vale {p['valor']:.2f} ({p['ganancia']:+.2f}, "
                f"{p['ganancia_pct']:+.2f}%). Pesa el {p['peso']:.1f}%.")
        else:
            porque = ("no cotiza / no tiene símbolo" if p.get("motivo_sin_precio") == "sin_simbolo"
                      else f"no he podido consultar el precio de {p['simbolo']}")
            lineas.append(
                f"  - {p['empresa']}: {p['participaciones']:g} x "
                f"{p['precio_compra']:.2f} = {p['coste']:.2f} {p['moneda']}. "
                f"Sin precio de mercado ({porque}). Pesa el {p['peso']:.1f}%.")

    if valoracion["varias_monedas"]:
        lineas.append("AVISO: hay varias monedas y los totales no están convertidos.")
    return "\n".join(lineas)
