"""
La Mesa: las cuatro salas de un vistazo.

No calcula nada nuevo. Lee lo que ya sacan gym.py, gastos.py e inversiones.py
y se queda con UNA cifra de cada sitio: la que contestarías si alguien te
preguntase por el pasillo "¿cómo lo llevas?".

Dos reglas:

  Si una sala no está estrenada, se dice y se invita a entrar. No se enseña un
  cero, que parecería un dato.

  La cartera solo aparece si está desbloqueada. Si está cerrada, la Mesa lo
  dice sin enseñar ni una cifra: para eso se cifró.
"""

from __future__ import annotations

from datetime import date


def _tarjeta(clave, palo, titulo, enlace, **resto):
    return {"clave": clave, "palo": palo, "titulo": titulo, "enlace": enlace, **resto}


def _gimnasio() -> dict:
    import gym

    perfil = gym.leer_perfil()
    if not perfil:
        return _tarjeta("gym", "♠", "Gimnasio", "/gym", estrenada=False,
                        invitacion="Mete tus datos y te calculo la rutina y las calorías.")

    rutina, _ = gym.rutina_actual(perfil)
    hechos = gym.dias_completados()
    entrenos = [d for d in rutina if not d["descanso"]]
    hoy = gym.DIAS_SEMANA[date.today().weekday()]
    dia_hoy = next((d for d in rutina if d["dia"] == hoy), None)

    metricas = gym.calcular_metricas(perfil)
    nutricion = gym.calcular_nutricion(perfil, metricas)

    if dia_hoy and dia_hoy["descanso"]:
        titular, detalle = "Hoy descansas", f"{len(hechos)} de {len(entrenos)} días hechos esta semana"
    elif dia_hoy and hoy in hechos:
        titular, detalle = "Hoy ya está hecho", dia_hoy["titulo"]
    elif dia_hoy:
        titular, detalle = f"Hoy toca {dia_hoy['titulo'].lower()}", \
                           f"{len(hechos)} de {len(entrenos)} días hechos esta semana"
    else:
        titular, detalle = "Sin plan para hoy", ""

    return _tarjeta(
        "gym", "♠", "Gimnasio", "/gym", estrenada=True,
        titular=titular, detalle=detalle,
        cifra=f"{len(hechos)}/{len(entrenos)}", cifra_pie="días de la semana",
        progreso=round(len(hechos) / len(entrenos) * 100) if entrenos else 0,
        extra=f"{nutricion['calorias']} kcal · {nutricion['proteina_g']} g de proteína",
    )


def _dinero() -> dict:
    import gastos

    perfil = gastos.leer_perfil()
    if not perfil:
        return _tarjeta("gastos", "♦", "Gastos", "/gastos", estrenada=False,
                        invitacion="Dime cuánto ingresas y reparto el mes contigo.")

    resumen = gastos.resumen_mes(perfil)
    ahorro = next((p for p in resumen["partes"] if p["tipo"] == "ahorro"), None)
    gastado_pct = round(resumen["total_gastado"] / resumen["ingreso"] * 100) if resumen["ingreso"] else 0

    if not resumen["num_gastos"]:
        titular, detalle = "Mes sin estrenar", "Apunta lo primero que gastes"
    elif resumen["total_gastado"] > resumen["ingreso"]:
        titular = "Te has pasado del sueldo"
        detalle = f"{resumen['total_gastado'] - resumen['ingreso']:,.0f} € de más".replace(",", ".")
    elif ahorro and ahorro["corto"]:
        titular = "El ahorro va corto"
        detalle = f"faltan {ahorro['presupuesto'] - ahorro['usado']:,.0f} €".replace(",", ".")
    else:
        titular, detalle = "El mes va en orden", f"quedan {resumen['dias_quedan']} días"

    return _tarjeta(
        "gastos", "♦", "Gastos", "/gastos", estrenada=True,
        titular=titular, detalle=detalle,
        cifra=f"{resumen['sobrante']:,.0f} €".replace(",", "."), cifra_pie="te queda este mes",
        progreso=min(gastado_pct, 100),
        extra=(f"{resumen['num_gastos']} "
               f"{'apunte' if resumen['num_gastos'] == 1 else 'apuntes'} · "
               f"{resumen['total_gastado']:,.0f} € gastados").replace(",", "."),
    )


def _cartera(clave_cartera: str | None) -> dict:
    import inversiones

    if not inversiones.hay_cartera():
        return _tarjeta("inversiones", "♣", "Inversiones", "/inversiones",
                        estrenada=False,
                        invitacion="Apunta dónde tienes el dinero. Se guarda cifrado.")

    if not clave_cartera:
        # Cerrada: ni una cifra. Enseñar aunque fuera el total sería regalar
        # información a quien se ha sentado delante sin saber la contraseña.
        return _tarjeta("inversiones", "♣", "Inversiones", "/inversiones",
                        estrenada=True, bloqueada=True,
                        titular="Cartera cerrada",
                        detalle="Ábrela para ver cómo va")

    try:
        valoracion = inversiones.valorar(inversiones.leer_cartera(clave_cartera))
    except (inversiones.ClaveIncorrecta, inversiones.SinCartera):
        return _tarjeta("inversiones", "♣", "Inversiones", "/inversiones",
                        estrenada=True, bloqueada=True,
                        titular="Cartera cerrada", detalle="Vuelve a abrirla")

    if not valoracion["cuantas"]:
        return _tarjeta("inversiones", "♣", "Inversiones", "/inversiones",
                        estrenada=True, titular="Cartera vacía",
                        detalle="Apunta tu primera posición",
                        cifra="—", cifra_pie="sin posiciones")

    g = valoracion["ganancia"]
    hay = valoracion["valor_total"] != valoracion["coste_total"]
    moneda = "" if valoracion["varias_monedas"] else (valoracion["monedas"][0] or "EUR")
    simbolo = {"EUR": "€", "USD": "$", "GBP": "£"}.get(moneda, "")

    return _tarjeta(
        "inversiones", "♣", "Inversiones", "/inversiones", estrenada=True,
        titular=("Sin precios ahora mismo" if not hay
                 else ("Vas en verde" if g >= 0 else "Vas en rojo")),
        detalle=(f"{valoracion['cuantas']} "
                 f"{'posición' if valoracion['cuantas'] == 1 else 'posiciones'}"
                 + (f" · {valoracion['ganancia_pct']:+.1f}%" if hay else "")),
        cifra=f"{valoracion['valor_total']:,.0f} {simbolo}".replace(",", "."),
        cifra_pie="vale tu cartera",
        signo=("sube" if hay and g >= 0 else ("baja" if hay else "")),
    )


def _libreta() -> dict:
    import sqlite3
    from pathlib import Path

    con = sqlite3.connect(Path(__file__).parent / "joker.db")
    con.row_factory = sqlite3.Row
    try:
        existe = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                             "AND name='notas'").fetchone()
        if not existe:
            return _tarjeta("libreta", "♥", "Libreta", "/", estrenada=False,
                            invitacion="Dile a JOKER que te apunte algo y aparecerá aquí.")
        cuantas = con.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
        ultima = con.execute("SELECT texto FROM notas ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        con.close()

    if not cuantas:
        return _tarjeta("libreta", "♥", "Libreta", "/", estrenada=False,
                        invitacion="Dile a JOKER que te apunte algo y aparecerá aquí.")

    return _tarjeta("libreta", "♥", "Libreta", "/", estrenada=True,
                    titular=ultima["texto"][:90],
                    detalle=(f"{cuantas} nota guardada" if cuantas == 1
                             else f"{cuantas} notas guardadas"),
                    cifra=str(cuantas), cifra_pie="apuntadas")


SALUDOS = [
    (5, "Madrugas"), (12, "Buenos días"), (20, "Buenas tardes"), (24, "Buenas noches"),
]


def saludo() -> str:
    from datetime import datetime
    hora = datetime.now().hour
    for tope, texto in SALUDOS:
        if hora < tope:
            return texto
    return "Buenas noches"


def resumen(clave_cartera: str | None = None) -> dict:
    """Todo lo que enseña la Mesa."""
    return {
        "saludo": saludo(),
        "fecha": date.today().isoformat(),
        "tarjetas": [_gimnasio(), _dinero(), _cartera(clave_cartera), _libreta()],
    }
