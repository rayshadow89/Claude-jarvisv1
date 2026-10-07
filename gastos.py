"""
J0KER GASTOS — el dinero del mes, con nombre y apellidos.

La idea es la misma que en el gimnasio: no dar consejos de manual, sino
números tuyos. Aquí eso significa que cada aviso cita cuánto te has pasado,
en qué, y qué le cuesta eso a tu ahorro.

Tres cosas que conviene saber antes de leer el código:

  1. El AHORRO no es un gasto más. Es lo que queda: ingreso menos todo lo
     que has gastado. Por eso no se "apunta" ahorro, se calcula.

  2. Cada REGLA de reparto (50/30/20 y compañía) reparte el mismo dinero en
     partes distintas, y cada parte se alimenta de unas categorías de gasto.
     La misma cena cuenta como "deseos" en 50/30/20 y como "ocio" en los seis
     frascos: es la regla la que decide, no el gasto.

  3. Los PORCENTAJES se pueden cambiar. Si quieres ahorrar el 99% y vivir con
     el 1%, el programa te deja: te dirá si es realista mirando lo que gastas
     de verdad, pero no te lo va a prohibir.

Los datos se guardan en la misma base local que el gimnasio (joker.db), que
no se sube a GitHub. Son tus cuentas: no salen de tu ordenador.
"""

# ---------------------------------------------------------------------------
# Copyright (c) 2026 Roberto (github.com/rayshadow89)
# Todos los derechos reservados. Software propietario de código visible:
# puedes leerlo y estudiarlo; usarlo, copiarlo o modificarlo necesita
# permiso por escrito. Los términos completos están en LICENSE.
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

BASE_DATOS = Path(__file__).parent / "joker.db"


# ---------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------

def _conexion() -> sqlite3.Connection:
    con = sqlite3.connect(BASE_DATOS)
    con.row_factory = sqlite3.Row
    return con


def _tablas(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS finanzas (
            id     INTEGER PRIMARY KEY CHECK (id = 1),
            datos  TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha     TEXT NOT NULL,
            categoria TEXT NOT NULL,
            concepto  TEXT NOT NULL DEFAULT '',
            importe   REAL NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS deudas (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre       TEXT NOT NULL,
            saldo        REAL NOT NULL,
            interes      REAL NOT NULL DEFAULT 0,
            pago_minimo  REAL NOT NULL DEFAULT 0
        )
    """)


def guardar_perfil(perfil: dict) -> None:
    with _conexion() as con:
        _tablas(con)
        con.execute(
            "INSERT INTO finanzas (id, datos) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET datos = excluded.datos",
            (json.dumps(perfil, ensure_ascii=False),),
        )


def leer_perfil() -> dict | None:
    with _conexion() as con:
        _tablas(con)
        fila = con.execute("SELECT datos FROM finanzas WHERE id = 1").fetchone()
    return json.loads(fila["datos"]) if fila else None


def borrar_todo() -> None:
    """Empezar de cero: se va el perfil, los gastos y las deudas."""
    with _conexion() as con:
        _tablas(con)
        con.execute("DELETE FROM finanzas")
        con.execute("DELETE FROM gastos")
        con.execute("DELETE FROM deudas")


def apuntar_gasto(fecha: str, categoria: str, concepto: str, importe: float) -> int:
    with _conexion() as con:
        _tablas(con)
        cur = con.execute(
            "INSERT INTO gastos (fecha, categoria, concepto, importe) VALUES (?, ?, ?, ?)",
            (fecha, categoria, concepto, round(float(importe), 2)),
        )
        return cur.lastrowid


def leer_gastos(desde: str | None = None, hasta: str | None = None) -> list:
    """Los gastos apuntados, del más reciente al más antiguo."""
    with _conexion() as con:
        _tablas(con)
        if desde and hasta:
            filas = con.execute(
                "SELECT * FROM gastos WHERE fecha BETWEEN ? AND ? "
                "ORDER BY fecha DESC, id DESC", (desde, hasta)).fetchall()
        else:
            filas = con.execute(
                "SELECT * FROM gastos ORDER BY fecha DESC, id DESC").fetchall()
    return [dict(f) for f in filas]


def borrar_gasto(id_gasto: int) -> None:
    with _conexion() as con:
        _tablas(con)
        con.execute("DELETE FROM gastos WHERE id = ?", (id_gasto,))


def guardar_deuda(nombre: str, saldo: float, interes: float, pago_minimo: float) -> int:
    with _conexion() as con:
        _tablas(con)
        cur = con.execute(
            "INSERT INTO deudas (nombre, saldo, interes, pago_minimo) VALUES (?, ?, ?, ?)",
            (nombre, round(float(saldo), 2), float(interes), round(float(pago_minimo), 2)),
        )
        return cur.lastrowid


def leer_deudas() -> list:
    with _conexion() as con:
        _tablas(con)
        filas = con.execute("SELECT * FROM deudas ORDER BY id").fetchall()
    return [dict(f) for f in filas]


def borrar_deuda(id_deuda: int) -> None:
    with _conexion() as con:
        _tablas(con)
        con.execute("DELETE FROM deudas WHERE id = ?", (id_deuda,))


# ---------------------------------------------------------------------------
# Categorías de gasto
# ---------------------------------------------------------------------------
# Una lista corta a propósito. Con treinta categorías nadie apunta nada porque
# elegir cuesta más que el propio gasto; con estas trece entra todo.

CATEGORIAS = {
    "vivienda":      "Vivienda (alquiler o hipoteca)",
    "suministros":   "Luz, agua, gas e internet",
    "alimentacion":  "Supermercado",
    "transporte":    "Transporte y coche",
    "salud":         "Salud y farmacia",
    "seguros":       "Seguros",
    "formacion":     "Formación y estudios",
    "ocio":          "Ocio, restaurantes y viajes",
    "compras":       "Compras y caprichos",
    "suscripciones": "Suscripciones",
    "deudas":        "Pagos de deudas",
    "donaciones":    "Donaciones y regalos",
    "otros":         "Otros",
}

# Lo imprescindible para vivir, que casi todas las reglas tratan igual.
_BASICOS = ["vivienda", "suministros", "alimentacion", "transporte", "salud", "seguros"]

# Gastos que se pagan UNA vez al mes, no un poco cada día. Importa para la
# proyección: si el alquiler de 650 € cae el día 1 y se divide entre los días
# transcurridos, sale un "ritmo" de escándalo y la página avisa de una ruina
# que no existe. Estos se cuentan como ya pagados y no se proyectan.
CATEGORIAS_FIJAS = {"vivienda", "suministros", "seguros", "deudas"}


# ---------------------------------------------------------------------------
# Las reglas de reparto
# ---------------------------------------------------------------------------
# Cada parte lleva:
#   pct         -> qué porcentaje del ingreso le toca
#   categorias  -> qué gastos suyos cuentan contra ella
#   tipo        -> "gasto" (dinero que sale) o "ahorro" (dinero que se queda)
#
# El reparto de categorías no es opinión mía: es cómo define cada método sus
# propios cajones. Por eso la misma cena cae en "deseos" con 50/30/20 y en
# "ocio" con los seis frascos.

REGLAS = {
    "50_30_20": {
        "nombre": "50/30/20",
        "autor": "Elizabeth Warren",
        "resumen": ("La más conocida y la más fácil de sostener. La mitad para vivir, "
                    "un tercio largo para disfrutar, y una quinta parte para ti."),
        "para_quien": "Si nunca has hecho un presupuesto, empieza por aquí.",
        "partes": [
            {"clave": "necesidades", "nombre": "Necesidades", "pct": 50, "tipo": "gasto",
             "categorias": _BASICOS + ["formacion"],
             "explica": "Lo que pagarías aunque te quedases en casa todo el mes."},
            {"clave": "deseos", "nombre": "Deseos", "pct": 30, "tipo": "gasto",
             "categorias": ["ocio", "compras", "suscripciones", "donaciones", "otros"],
             "explica": "Lo que hace que el mes no sea solo sobrevivir."},
            {"clave": "ahorro", "nombre": "Ahorro y deudas", "pct": 20, "tipo": "ahorro",
             "categorias": ["deudas"],
             "explica": "Lo que no te gastas, más lo que dedicas a quitarte deuda."},
        ],
    },
    "70_20_10": {
        "nombre": "70/20/10",
        "autor": "método clásico de sobres",
        "resumen": ("Un solo cajón para todo lo que gastas, otro para ti y otro para "
                    "quitarte deuda o ayudar a alguien."),
        "para_quien": "Si te agobia clasificar cada gasto: aquí casi todo va al mismo sitio.",
        "partes": [
            {"clave": "vida", "nombre": "Gastos de vida", "pct": 70, "tipo": "gasto",
             "categorias": _BASICOS + ["formacion", "ocio", "compras", "suscripciones", "otros"],
             "explica": "Todo lo que gastas en vivir, sin separar necesidad de capricho."},
            {"clave": "ahorro", "nombre": "Ahorro e inversión", "pct": 20, "tipo": "ahorro",
             "categorias": [],
             "explica": "Lo que se queda quieto y trabaja para ti."},
            {"clave": "deuda_dar", "nombre": "Deuda o donaciones", "pct": 10, "tipo": "gasto",
             "categorias": ["deudas", "donaciones"],
             "explica": "Quitarte deuda, o dar. El método original lo dejaba a tu elección."},
        ],
    },
    "6_frascos": {
        "nombre": "Los 6 frascos",
        "autor": "T. Harv Eker",
        "resumen": ("Seis botes, cada uno con su trabajo. El que manda es el de libertad "
                    "financiera: ese no se toca nunca, ni para emergencias."),
        "para_quien": "Si el problema no es cuánto ganas, sino que todo acaba en el mismo saco.",
        "partes": [
            {"clave": "necesidades", "nombre": "Necesidades", "pct": 55, "tipo": "gasto",
             "categorias": _BASICOS + ["deudas"],
             "explica": "Techo, comida, transporte y lo que debas."},
            {"clave": "libertad", "nombre": "Libertad financiera", "pct": 10, "tipo": "ahorro",
             "categorias": [],
             "explica": "El bote intocable. Solo se invierte, nunca se gasta."},
            {"clave": "largo_plazo", "nombre": "Compras grandes", "pct": 10, "tipo": "gasto",
             "categorias": ["compras"],
             "explica": "Lo que se ahorra para algo concreto: un coche, un viaje, un portátil."},
            {"clave": "formacion", "nombre": "Formación", "pct": 10, "tipo": "gasto",
             "categorias": ["formacion"],
             "explica": "Cursos, libros, aprender algo que te haga ganar más."},
            {"clave": "ocio", "nombre": "Disfrutar", "pct": 10, "tipo": "gasto",
             "categorias": ["ocio", "suscripciones"],
             "explica": "Obligatorio gastarlo. Un plan que no deja disfrutar no dura."},
            {"clave": "dar", "nombre": "Dar", "pct": 5, "tipo": "gasto",
             "categorias": ["donaciones", "otros"],
             "explica": "Regalos, invitar, ayudar."},
        ],
    },
    "80_20": {
        "nombre": "80/20 (págate primero)",
        "autor": "Pay Yourself First",
        "resumen": ("Apartas el 20% en cuanto cobras y vives con lo demás. Una sola regla, "
                    "una sola decisión al mes."),
        "para_quien": "Si lo que falla es la fuerza de voluntad a final de mes.",
        "partes": [
            {"clave": "ahorro", "nombre": "Ahorro (primero)", "pct": 20, "tipo": "ahorro",
             "categorias": [],
             "explica": "Se aparta el día de cobro, antes de gastar nada."},
            {"clave": "vida", "nombre": "Todo lo demás", "pct": 80, "tipo": "gasto",
             "categorias": list(CATEGORIAS),
             "explica": "Sin subdividir: si el 20% ya está guardado, lo demás es tuyo."},
        ],
    },
    "40_30_20_10": {
        "nombre": "40/30/20/10",
        "autor": "variante del 50/30/20",
        "resumen": ("Como el 50/30/20 pero apretando lo básico, para dejar sitio a pagar "
                    "deuda sin renunciar del todo a los caprichos."),
        "para_quien": "Si arrastras deuda y el 50/30/20 se te queda corto.",
        "partes": [
            {"clave": "necesidades", "nombre": "Necesidades", "pct": 40, "tipo": "gasto",
             "categorias": _BASICOS,
             "explica": "Más apretado que en el 50/30/20: aquí hay que ajustar."},
            {"clave": "deseos", "nombre": "Deseos", "pct": 30, "tipo": "gasto",
             "categorias": ["ocio", "compras", "suscripciones", "formacion", "otros"],
             "explica": "Lo mismo que en el 50/30/20."},
            {"clave": "ahorro", "nombre": "Ahorro", "pct": 20, "tipo": "ahorro",
             "categorias": [],
             "explica": "Sin mezclar con la deuda: aquí cada uno tiene su cajón."},
            {"clave": "deuda_dar", "nombre": "Deudas y donaciones", "pct": 10, "tipo": "gasto",
             "categorias": ["deudas", "donaciones"],
             "explica": "El cajón que hace distinta a esta regla."},
        ],
    },
}


def _comprobar_reglas() -> None:
    """
    Cada categoría tiene que caer en UNA parte de cada regla: ni en dos (se
    contaría el mismo gasto dos veces) ni en ninguna (desaparecería del
    presupuesto sin que nadie se entere). Se comprueba al importar, porque un
    fallo aquí descuadra todas las cuentas en silencio.
    """
    for clave, regla in REGLAS.items():
        visto = {}
        for parte in regla["partes"]:
            for cat in parte["categorias"]:
                if cat not in CATEGORIAS:
                    raise ValueError(f"{clave}: la categoría '{cat}' no existe")
                if cat in visto:
                    raise ValueError(
                        f"{clave}: '{cat}' está en '{visto[cat]}' y en '{parte['clave']}'")
                visto[cat] = parte["clave"]

        faltan = set(CATEGORIAS) - set(visto)
        if faltan:
            raise ValueError(f"{clave}: quedan categorías sin parte: {sorted(faltan)}")

        suma = sum(p["pct"] for p in regla["partes"])
        if suma != 100:
            raise ValueError(f"{clave}: los porcentajes suman {suma}, no 100")


_comprobar_reglas()


def reparto_actual(perfil: dict) -> list:
    """
    Las partes de la regla elegida, con TUS porcentajes si los has cambiado.

    Se guardan por regla, así que puedes tener tu 50/30/20 tocado a tu manera
    y cambiar a los seis frascos sin perderlo.
    """
    clave = perfil.get("regla", "50_30_20")
    regla = REGLAS.get(clave, REGLAS["50_30_20"])
    propios = (perfil.get("repartos") or {}).get(clave, {})

    partes = []
    for parte in regla["partes"]:
        copia = dict(parte)
        if parte["clave"] in propios:
            copia["pct"] = float(propios[parte["clave"]])
            copia["tocado"] = True
        else:
            copia["tocado"] = False
        partes.append(copia)
    return partes


# ---------------------------------------------------------------------------
# Las cuentas del mes
# ---------------------------------------------------------------------------

def _limites_mes(mes: str) -> tuple:
    """Primer y último día de un mes en formato 'AAAA-MM'."""
    anio, numero = (int(x) for x in mes.split("-"))
    primero = date(anio, numero, 1)
    if numero == 12:
        siguiente = date(anio + 1, 1, 1)
    else:
        siguiente = date(anio, numero + 1, 1)
    ultimo = date.fromordinal(siguiente.toordinal() - 1)
    return primero.isoformat(), ultimo.isoformat(), ultimo.day


def mes_actual() -> str:
    return date.today().strftime("%Y-%m")


def resumen_mes(perfil: dict, mes: str | None = None) -> dict:
    """
    Lo que has presupuestado frente a lo que llevas gastado, parte por parte.

    El truco está en la parte de ahorro: no se apunta, se deduce. Lo que
    ahorras es lo que te ha sobrado, y si además la regla mete ahí los pagos
    de deuda, esos también cuentan, porque bajar lo que debes es tan tuyo
    como subir lo que tienes.
    """
    mes = mes or mes_actual()
    ingreso = float(perfil.get("ingreso", 0))
    desde, hasta, dias_mes = _limites_mes(mes)

    gastos = leer_gastos(desde, hasta)
    por_categoria = {}
    for g in gastos:
        por_categoria[g["categoria"]] = por_categoria.get(g["categoria"], 0) + g["importe"]

    total_gastado = round(sum(por_categoria.values()), 2)
    sobrante = round(ingreso - total_gastado, 2)

    partes = []
    for parte in reparto_actual(perfil):
        presupuesto = round(ingreso * parte["pct"] / 100, 2)
        gastado = round(sum(por_categoria.get(c, 0) for c in parte["categorias"]), 2)

        if parte["tipo"] == "ahorro":
            # Lo que sobra + lo que hayas metido en sus propias categorías
            conseguido = round(sobrante + gastado, 2)
        else:
            conseguido = gastado

        partes.append({
            **parte,
            "presupuesto": presupuesto,
            "usado": conseguido,
            "restante": round(presupuesto - conseguido, 2),
            "porcentaje_usado": round(conseguido / presupuesto * 100, 1) if presupuesto else 0.0,
            "pasado": conseguido > presupuesto and parte["tipo"] == "gasto",
            "corto": conseguido < presupuesto and parte["tipo"] == "ahorro",
            "detalle": [
                {"categoria": c, "nombre": CATEGORIAS[c],
                 "importe": round(por_categoria.get(c, 0), 2)}
                for c in parte["categorias"] if por_categoria.get(c)
            ],
        })

    # ¿Por dónde va el mes? Sirve para no alarmar el día 2 ni consolar el 28.
    hoy = date.today()
    if hoy.isoformat() > hasta:
        dias_pasados = dias_mes            # mes cerrado
    elif hoy.isoformat() < desde:
        dias_pasados = 0                   # mes que aún no ha empezado
    else:
        dias_pasados = hoy.day

    # El ritmo se mide SOLO sobre lo variable, por lo dicho en CATEGORIAS_FIJAS:
    # el alquiler ya está pagado y no va a volver a caer este mes.
    gasto_fijo = round(sum(v for c, v in por_categoria.items() if c in CATEGORIAS_FIJAS), 2)
    gasto_variable = round(total_gastado - gasto_fijo, 2)
    dias_quedan = max(dias_mes - dias_pasados, 0)

    ritmo = round(gasto_variable / dias_pasados, 2) if dias_pasados else 0.0
    proyeccion = round(total_gastado + ritmo * dias_quedan, 2)

    return {
        "mes": mes,
        "ingreso": round(ingreso, 2),
        "total_gastado": total_gastado,
        "sobrante": sobrante,
        "partes": partes,
        "por_categoria": [
            {"categoria": c, "nombre": CATEGORIAS[c], "importe": round(v, 2)}
            for c, v in sorted(por_categoria.items(), key=lambda x: -x[1])
        ],
        "dias_mes": dias_mes,
        "dias_pasados": dias_pasados,
        "dias_quedan": dias_quedan,
        "gasto_fijo": gasto_fijo,
        "gasto_variable": gasto_variable,
        "ritmo_diario": ritmo,
        "proyeccion_mes": proyeccion,
        "num_gastos": len(gastos),
    }


def generar_avisos(perfil: dict, resumen: dict, deudas: list) -> list:
    """
    Los avisos. Con cifras tuyas o no se dicen.

    "Controla tus gastos" no le sirve a nadie. "Llevas 412 € en ocio de los
    360 € que te tocaban, y a este ritmo acabarás el mes 180 € por debajo de
    tu ahorro" sí, porque ya sabes qué tocar.
    """
    avisos = []
    ingreso = resumen["ingreso"]
    if not ingreso:
        return [{"tipo": "aviso", "clase": "Primero lo primero",
                 "texto": "Sin ingreso mensual no hay presupuesto que repartir. "
                          "Ponlo arriba y vuelvo a calcular."}]

    dias_pasados = resumen["dias_pasados"]
    dias_mes = resumen["dias_mes"]
    partes_gasto = [p for p in resumen["partes"] if p["tipo"] == "gasto"]
    parte_ahorro = next((p for p in resumen["partes"] if p["tipo"] == "ahorro"), None)

    # 1. Lo más grave: gastas más de lo que entra
    if resumen["total_gastado"] > ingreso:
        avisos.append({
            "tipo": "aviso", "clase": "Números rojos",
            "texto": (f"Llevas {resumen['total_gastado']:.2f} € gastados y entran "
                      f"{ingreso:.2f} €. Son {resumen['total_gastado'] - ingreso:.2f} € "
                      f"de más, que salen de ahorros o de deuda nueva. Esto va antes "
                      f"que cualquier regla de reparto."),
        })

    # 2. El ritmo: no es lo mismo ir al 60% el día 5 que el día 25
    if dias_pasados and dias_pasados < dias_mes:
        if resumen["proyeccion_mes"] > ingreso:
            avisos.append({
                "tipo": "aviso", "clase": "El ritmo no cuadra",
                "texto": (f"Sin contar lo fijo (que ya está pagado), vas a "
                          f"{resumen['ritmo_diario']:.2f} € al día. Quedan "
                          f"{resumen['dias_quedan']} días: a este paso cerrarás el mes en "
                          f"{resumen['proyeccion_mes']:.2f} €, o sea "
                          f"{resumen['proyeccion_mes'] - ingreso:.2f} € por encima de lo que "
                          f"ingresas. Para llegar justo tendrías que bajar a "
                          f"{max(ingreso - resumen['total_gastado'], 0) / resumen['dias_quedan']:.2f} € al día."),
            })
        elif parte_ahorro and resumen["proyeccion_mes"] > ingreso - parte_ahorro["presupuesto"]:
            falta = resumen["proyeccion_mes"] - (ingreso - parte_ahorro["presupuesto"])
            avisos.append({
                "tipo": "consejo", "clase": "Cuidado con el ahorro",
                "texto": (f"No te vas a pasar del sueldo, pero sí de lo que te deja ahorrar. "
                          f"A {resumen['ritmo_diario']:.2f} € al día en gasto variable "
                          f"cerrarás en {resumen['proyeccion_mes']:.2f} €, y tu "
                          f"{parte_ahorro['nombre'].lower()} se quedaría {falta:.2f} € corto. "
                          f"Son {falta / resumen['dias_quedan']:.2f} € al día menos durante "
                          f"los {resumen['dias_quedan']} días que quedan."),
            })

    # 3. Las partes que se han pasado, de la que más se ha pasado a la que menos
    pasadas = sorted([p for p in partes_gasto if p["pasado"]],
                     key=lambda p: p["usado"] - p["presupuesto"], reverse=True)
    for parte in pasadas[:3]:
        exceso = parte["usado"] - parte["presupuesto"]
        # Buscamos al culpable sobre el que se puede hacer algo: decirle a
        # alguien que lo que más pesa es el alquiler no le sirve de nada,
        # porque el alquiler no se recorta a mitad de mes.
        movibles = [d for d in parte["detalle"] if d["categoria"] not in CATEGORIAS_FIJAS]
        culpable = max(movibles, key=lambda d: d["importe"], default=None)
        if culpable:
            detalle = (f" De lo que puedes tocar, lo que más pesa es "
                       f"{culpable['nombre'].lower()}: {culpable['importe']:.2f} €.")
        else:
            fijo = max(parte["detalle"], key=lambda d: d["importe"], default=None)
            detalle = (f" Aquí casi todo es fijo ({fijo['nombre'].lower()}, "
                       f"{fijo['importe']:.2f} €), así que el recorte no está en esta "
                       f"parte: tendrá que salir de otra.") if fijo else ""
        avisos.append({
            "tipo": "aviso", "clase": f"Te has pasado en {parte['nombre'].lower()}",
            "texto": (f"{parte['usado']:.2f} € de los {parte['presupuesto']:.2f} € que te "
                      f"tocaban ({parte['pct']:.0f}% de tu sueldo): {exceso:.2f} € de más."
                      f"{detalle} Ese dinero sale de algún sitio, y normalmente es del ahorro."),
        })

    # 4. El ahorro, que es el que importa
    if parte_ahorro:
        if parte_ahorro["usado"] < 0:
            avisos.append({
                "tipo": "aviso", "clase": "Ahorro en negativo",
                "texto": (f"Este mes no ahorras: te faltan {abs(parte_ahorro['usado']):.2f} €. "
                          f"El objetivo era {parte_ahorro['presupuesto']:.2f} €."),
            })
        elif parte_ahorro["corto"]:
            falta = parte_ahorro["presupuesto"] - parte_ahorro["usado"]
            avisos.append({
                "tipo": "consejo", "clase": "Ahorro por debajo",
                "texto": (f"Llevas {parte_ahorro['usado']:.2f} € de los "
                          f"{parte_ahorro['presupuesto']:.2f} € de {parte_ahorro['nombre'].lower()}: "
                          f"faltan {falta:.2f} €. Mirando tus partes, de donde más fácil sale "
                          f"es de {pasadas[0]['nombre'].lower()}." if pasadas else
                          f"Llevas {parte_ahorro['usado']:.2f} € de los "
                          f"{parte_ahorro['presupuesto']:.2f} € de {parte_ahorro['nombre'].lower()}: "
                          f"faltan {falta:.2f} €."),
            })
        elif (parte_ahorro["usado"] >= parte_ahorro["presupuesto"]
              and resumen["num_gastos"]
              and resumen["proyeccion_mes"] <= ingreso - parte_ahorro["presupuesto"]):
            # Solo si el mes TAMBIÉN va a acabar bien. Felicitar hoy por un
            # ahorro que la proyección se va a comer contradice el aviso de
            # arriba y deja al usuario sin saber a cuál hacer caso.
            extra = parte_ahorro["usado"] - parte_ahorro["presupuesto"]
            avisos.append({
                "tipo": "bien", "clase": "Vas bien",
                "texto": (f"Llevas {parte_ahorro['usado']:.2f} € de {parte_ahorro['nombre'].lower()}, "
                          f"{extra:.2f} € por encima de tu objetivo. Si el mes acaba así, "
                          f"en un año son {parte_ahorro['usado'] * 12:.2f} €."),
            })

    # 5. Las deudas: lo que cuesta tenerlas ahí quietas
    if deudas:
        total = sum(d["saldo"] for d in deudas)
        interes_anual = sum(d["saldo"] * d["interes"] / 100 for d in deudas)
        cara = max(deudas, key=lambda d: d["interes"])
        avisos.append({
            "tipo": "aviso", "clase": "Lo que te cuesta la deuda",
            "texto": (f"Debes {total:.2f} € en total. Solo por tenerla, los intereses te "
                      f"cuestan unos {interes_anual / 12:.2f} € al mes ({interes_anual:.2f} € "
                      f"al año). La más cara es {cara['nombre']}, al {cara['interes']:.2f}%: "
                      f"esa es la que hay que quitarse primero si quieres pagar menos."),
        })

    # 6. Las suscripciones, que es donde se escapa el dinero sin que te enteres
    susc = next((c for c in resumen["por_categoria"] if c["categoria"] == "suscripciones"), None)
    if susc and susc["importe"] > 0:
        avisos.append({
            "tipo": "consejo", "clase": "Suscripciones",
            "texto": (f"{susc['importe']:.2f} € al mes en suscripciones son "
                      f"{susc['importe'] * 12:.2f} € al año. No digo que las quites: "
                      f"digo que mires cuántas has usado este mes de verdad."),
        })

    if not avisos:
        avisos.append({
            "tipo": "consejo", "clase": "Todavía no hay nada que decir",
            "texto": "Apunta unos cuantos gastos y aquí empezarán a salir avisos con "
                     "tus cifras, no consejos de manual.",
        })
    return avisos


# ---------------------------------------------------------------------------
# Deudas: cómo salir de ellas
# ---------------------------------------------------------------------------

def _simular(deudas: list, extra: float, orden) -> dict:
    """
    Cuánto se tarda y cuánto se paga de intereses siguiendo un orden.

    Se paga el mínimo de todas y el dinero de sobra va entera a UNA, la que
    diga el orden. Cuando esa cae, su pago se suma al ataque de la siguiente:
    es lo que hace que el final se acelere tanto.
    """
    pendientes = [{"nombre": d["nombre"], "saldo": float(d["saldo"]),
                   "interes": float(d["interes"]), "minimo": float(d["pago_minimo"])}
                  for d in deudas if float(d["saldo"]) > 0]
    if not pendientes:
        return {"meses": 0, "intereses": 0.0, "pasos": [], "imposible": False}

    intereses = 0.0
    pasos = []
    meses = 0
    TOPE = 600   # 50 años: más allá de eso, el plan no es un plan

    while pendientes and meses < TOPE:
        meses += 1
        disponible = sum(d["minimo"] for d in pendientes) + extra

        # 1. Intereses del mes
        for d in pendientes:
            coste = d["saldo"] * (d["interes"] / 100) / 12
            d["saldo"] += coste
            intereses += coste

        # 2. Mínimos
        for d in pendientes:
            pago = min(d["minimo"], d["saldo"], disponible)
            d["saldo"] -= pago
            disponible -= pago

        # 3. Todo lo que sobra, a la elegida
        for d in sorted(pendientes, key=orden):
            if disponible <= 0:
                break
            pago = min(disponible, d["saldo"])
            d["saldo"] -= pago
            disponible -= pago

        # 4. ¿Alguna se ha acabado?
        for d in list(pendientes):
            if d["saldo"] <= 0.01:
                pasos.append({"nombre": d["nombre"], "mes": meses})
                pendientes.remove(d)

    imposible = bool(pendientes)
    return {
        # Si al llegar al tope quedaba deuda, no hay plazo que dar: decir "600
        # meses" sería inventarse una cifra con pinta de cálculo.
        "meses": None if imposible else meses,
        # Los intereses de una deuda que no se acaba tienden a infinito: lo que
        # saldría aquí es el resultado de parar el bucle a los 50 años, no una
        # previsión. Mejor no dar número que dar uno inventado.
        "intereses": None if imposible else round(intereses, 2),
        "pasos": pasos,
        "imposible": imposible,
    }


def plan_deudas(deudas: list, extra: float = 0.0) -> dict:
    """
    Los dos métodos que funcionan, comparados con TUS deudas.

      Avalancha  -> primero la de más interés. Es la que menos dinero cuesta.
      Bola de nieve -> primero la más pequeña. Cuesta algo más, pero tachas
                    una deuda antes, y eso es lo que hace que la gente siga.

    No hay un ganador universal: la avalancha gana en euros y la bola de nieve
    gana en aguante. Se enseñan los dos números y decides tú.
    """
    activas = [d for d in deudas if float(d["saldo"]) > 0]
    if not activas:
        return {"hay_deudas": False}

    minimos = sum(float(d["pago_minimo"]) for d in activas)
    total = sum(float(d["saldo"]) for d in activas)

    avalancha = _simular(activas, extra, lambda d: -d["interes"])
    bola = _simular(activas, extra, lambda d: d["saldo"])

    # ¿Los mínimos llegan siquiera para cubrir los intereses?
    interes_mensual = sum(float(d["saldo"]) * (float(d["interes"]) / 100) / 12 for d in activas)
    ahogado = minimos + extra <= interes_mensual

    # Si alguna simulación no llega a su fin, no hay diferencia que comparar.
    if avalancha["imposible"] or bola["imposible"]:
        ahorro = None
    else:
        ahorro = round(bola["intereses"] - avalancha["intereses"], 2)

    return {
        "hay_deudas": True,
        "total": round(total, 2),
        "minimos": round(minimos, 2),
        "extra": round(float(extra), 2),
        "interes_mensual": round(interes_mensual, 2),
        "ahogado": ahogado,
        "avalancha": avalancha,
        "bola_de_nieve": bola,
        "diferencia_intereses": ahorro,
        "recomendacion": _recomendar_metodo(
            avalancha, bola, ahorro, ahogado, interes_mensual, minimos, float(extra), len(activas)),
    }


def _recomendar_metodo(avalancha: dict, bola: dict, ahorro: float | None, ahogado: bool,
                       interes_mensual: float, minimos: float, extra: float,
                       cuantas: int) -> str:
    """
    Qué método le conviene, dicho con sus números y sin vender humo.

    El caso que más se da y del que nadie habla: si no pones ni un euro por
    encima de los mínimos, los dos métodos dan EXACTAMENTE lo mismo, porque no
    hay dinero suelto que dirigir a ninguna deuda. Decir ahí "elige avalancha"
    sería regalarle al usuario una decisión que no cambia nada.
    """
    if ahogado:
        return (f"Aviso serio: solo los intereses son {interes_mensual:.2f} € al mes, y entre "
                f"los mínimos y el extra estás poniendo {minimos + extra:.2f} €. Así la deuda "
                f"CRECE cada mes hagas lo que hagas, y ningún método arregla eso. Antes de "
                f"elegir hay que subir el pago o renegociar el interés con el banco.")

    if ahorro is None:
        return ("Con lo que estás pagando, la simulación no llega a ver el final de la "
                "deuda ni en 50 años. Eso no es un plazo largo: es que el pago se queda "
                "demasiado cerca de lo que crecen los intereses. Sube el extra de arriba "
                "hasta que salgan plazos, y verás cuánto hace falta de verdad.")

    if cuantas == 1:
        return ("Con una sola deuda los dos métodos son el mismo plan: todo lo que puedas, "
                "a ella. La pregunta útil aquí no es el orden, es cuánto extra puedes meter.")

    if extra <= 0:
        return (f"Pagando solo los mínimos, los dos métodos dan el mismo resultado: "
                f"{avalancha['meses']} meses y {avalancha['intereses']:.2f} € de intereses. "
                f"Y es lógico: sin dinero de sobra no hay nada que dirigir a una deuda ni a "
                f"otra. Prueba a subir el extra de arriba y verás cómo se separan: ahí es "
                f"donde elegir método empieza a valer algo.")

    if abs(ahorro) < 1:
        empate = (f"Con tus deudas y {extra:.2f} € extra, los dos salen casi iguales "
                  f"({abs(ahorro):.2f} € de diferencia). ")
    else:
        empate = (f"Con la avalancha pagas {abs(ahorro):.2f} € menos de intereses. ")

    primera_a = avalancha["pasos"][0] if avalancha["pasos"] else None
    primera_b = bola["pasos"][0] if bola["pasos"] else None
    if primera_a and primera_b and primera_a["mes"] != primera_b["mes"]:
        motivacion = (f"La bola de nieve te quita la primera deuda de encima en el mes "
                      f"{primera_b['mes']} en vez del {primera_a['mes']}, y eso es lo que "
                      f"hace que mucha gente no lo deje a medias. ")
    else:
        motivacion = "Las dos te quitan la primera deuda en el mismo mes. "

    plazos = ""
    if avalancha["meses"] and bola["meses"] and avalancha["meses"] != bola["meses"]:
        plazos = (f"En plazo, {avalancha['meses']} meses frente a {bola['meses']}. ")

    return (empate + plazos + motivacion +
            "Si aguantas sin ver resultados rápidos, avalancha. Si necesitas tachar algo "
            "pronto para seguir, bola de nieve: lo que cuesta de más suele salir barato "
            "comparado con abandonar el plan.")


# ---------------------------------------------------------------------------
# Datos para las gráficas
# ---------------------------------------------------------------------------

def datos_graficas(perfil: dict, resumen: dict) -> dict:
    """
    Dos gráficas, cada una respondiendo a una pregunta distinta:

      La línea  -> ¿cómo va el mes? Lo que te queda día a día, frente al
                   ritmo que deberías llevar para acabar con tu ahorro intacto.
      El círculo -> ¿cómo reparte tu regla el dinero? Y, encima, cuánto llevas
                   usado de cada parte.
    """
    mes = resumen["mes"]
    desde, hasta, dias_mes = _limites_mes(mes)
    ingreso = resumen["ingreso"]

    gastos = leer_gastos(desde, hasta)
    por_dia = {}
    for g in gastos:
        por_dia[g["fecha"]] = por_dia.get(g["fecha"], 0) + g["importe"]

    parte_ahorro = next((p for p in resumen["partes"] if p["tipo"] == "ahorro"), None)
    meta_ahorro = parte_ahorro["presupuesto"] if parte_ahorro else 0.0
    para_gastar = ingreso - meta_ahorro

    anio, numero = (int(x) for x in mes.split("-"))
    linea, ideal = [], []
    acumulado = 0.0
    for dia in range(1, dias_mes + 1):
        fecha = date(anio, numero, dia).isoformat()
        acumulado += por_dia.get(fecha, 0)
        linea.append({"fecha": fecha, "queda": round(ingreso - acumulado, 2),
                      "gastado": round(acumulado, 2)})
        ideal.append({"fecha": fecha,
                      "queda": round(ingreso - para_gastar * dia / dias_mes, 2)})

    # La línea real solo llega hasta hoy: el resto del mes aún no ha pasado.
    hasta_dia = min(resumen["dias_pasados"] or dias_mes, dias_mes)

    return {
        "linea": linea[:hasta_dia],
        "ideal": ideal,
        "ingreso": ingreso,
        "meta_ahorro": round(meta_ahorro, 2),
        "suelo": round(ingreso - para_gastar, 2),
        "circulo": [
            {"clave": p["clave"], "nombre": p["nombre"], "pct": p["pct"],
             "presupuesto": p["presupuesto"], "usado": p["usado"],
             "porcentaje_usado": p["porcentaje_usado"], "tipo": p["tipo"]}
            for p in resumen["partes"]
        ],
    }


# ---------------------------------------------------------------------------
# Todo junto
# ---------------------------------------------------------------------------

def panel_completo(perfil: dict, mes: str | None = None, extra_deuda: float = 0.0) -> dict:
    resumen = resumen_mes(perfil, mes)
    deudas = leer_deudas()
    desde, hasta, _ = _limites_mes(resumen["mes"])

    return {
        "perfil": perfil,
        "regla": REGLAS.get(perfil.get("regla", "50_30_20"), REGLAS["50_30_20"]),
        "resumen": resumen,
        "avisos": generar_avisos(perfil, resumen, deudas),
        "deudas": deudas,
        "plan_deudas": plan_deudas(deudas, extra_deuda),
        "graficas": datos_graficas(perfil, resumen),
        "gastos": leer_gastos(desde, hasta)[:60],
        "aviso_legal": ("Esto es una hoja de cálculo con buenas intenciones, no asesoría "
                        "financiera. Los intereses se calculan de forma simplificada "
                        "(mensual sobre el saldo) y tu banco puede hacerlo distinto."),
    }


def resumen_texto(panel: dict) -> str:
    """Versión en texto, para que JOKER pueda contarlo por el chat."""
    r, regla = panel["resumen"], panel["regla"]
    lineas = [
        f"Regla usada: {regla['nombre']}. Ingreso mensual: {r['ingreso']:.2f} €.",
        f"Mes {r['mes']}: gastado {r['total_gastado']:.2f} € en {r['num_gastos']} apuntes. "
        f"Le quedan {r['sobrante']:.2f} €.",
    ]
    for p in r["partes"]:
        estado = "PASADO" if p["pasado"] else ("corto" if p["corto"] else "bien")
        lineas.append(f"  - {p['nombre']} ({p['pct']:.0f}%): {p['usado']:.2f} € de "
                      f"{p['presupuesto']:.2f} € [{estado}]")

    if r["dias_pasados"] and r["dias_pasados"] < r["dias_mes"]:
        lineas.append(f"Ritmo de gasto variable: {r['ritmo_diario']:.2f} €/día (lo fijo, "
                      f"{r['gasto_fijo']:.2f} €, ya está pagado) -> cerraría el mes en "
                      f"{r['proyeccion_mes']:.2f} €.")

    plan = panel["plan_deudas"]
    if not plan.get("hay_deudas"):
        lineas.append("No tiene deudas apuntadas.")
    elif plan["ahogado"] or plan["avalancha"]["imposible"]:
        # Aquí no hay plazo que dar: con lo que paga, la deuda sube en vez de
        # bajar. Dar una cifra de meses o de intereses sería inventarla.
        lineas.append(f"Deudas: {plan['total']:.2f} € en total. AVISO IMPORTANTE: los "
                      f"intereses son {plan['interes_mensual']:.2f} €/mes y solo está "
                      f"pagando {plan['minimos'] + plan['extra']:.2f} €/mes, así que la "
                      f"deuda CRECE. No hay plazo posible hasta que suba el pago o "
                      f"renegocie el interés.")
    else:
        lineas.append(f"Deudas: {plan['total']:.2f} € en total, intereses "
                      f"{plan['interes_mensual']:.2f} €/mes. Con avalancha, "
                      f"{plan['avalancha']['meses']} meses y "
                      f"{plan['avalancha']['intereses']:.2f} € de intereses; con bola de "
                      f"nieve, {plan['bola_de_nieve']['meses']} meses y "
                      f"{plan['bola_de_nieve']['intereses']:.2f} €.")

    avisos = [a["texto"] for a in panel["avisos"] if a["tipo"] == "aviso"]
    if avisos:
        lineas.append("Avisos: " + " ".join(avisos))
    return "\n".join(lineas)
