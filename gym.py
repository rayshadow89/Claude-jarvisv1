"""
J0KER GYM — el módulo de entrenamiento.
========================================

Todo el cálculo vive aquí, separado de la web y del chat, para que tanto
la página /gym como JOKER hablando por el chat usen exactamente los
mismos números.

Lo que hace:
  - Guarda tu perfil (altura, peso, edad, objetivo, limitaciones...).
  - Calcula tus números: IMC, metabolismo basal, calorías de mantenimiento
    y las calorías/macros que te tocan según lo que busques.
  - Estima cuánto vas a tardar en llegar a tu meta, y si esa meta es
    realista te propone una ajustada.
  - Genera la rutina de la semana, esquivando tus lesiones y adaptándose
    al material que tengas.
  - Sugiere un menú del día que cuadre con tus calorías.

AVISO: esto es orientativo, basado en fórmulas estándar. No es consejo
médico. Si tienes alguna condición de salud, habla con un profesional.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BASE_DATOS = Path(__file__).parent / "joker.db"


# ---------------------------------------------------------------------------
# Guardado del perfil (SQLite: viene con Python, no hay que instalar nada)
# ---------------------------------------------------------------------------

def _conexion() -> sqlite3.Connection:
    con = sqlite3.connect(BASE_DATOS)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS perfil_gym (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            datos TEXT NOT NULL,
            actualizado TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return con


def guardar_perfil(perfil: dict) -> None:
    """Guarda (o reemplaza) el perfil. Solo hay uno: el del dueño del portátil."""
    with _conexion() as con:
        con.execute(
            "INSERT INTO perfil_gym (id, datos, actualizado) VALUES (1, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(id) DO UPDATE SET datos = excluded.datos, "
            "actualizado = CURRENT_TIMESTAMP",
            (json.dumps(perfil, ensure_ascii=False),),
        )


def leer_perfil() -> dict | None:
    """Devuelve el perfil guardado, o None si todavía no hay ninguno."""
    with _conexion() as con:
        fila = con.execute("SELECT datos FROM perfil_gym WHERE id = 1").fetchone()
    return json.loads(fila["datos"]) if fila else None


def borrar_perfil() -> None:
    with _conexion() as con:
        con.execute("DELETE FROM perfil_gym WHERE id = 1")


# ---------------------------------------------------------------------------
# Tablas de referencia
# ---------------------------------------------------------------------------

# Cuánto multiplica tu gasto el día a día (fuera del gimnasio).
FACTORES_ACTIVIDAD = {
    "sedentario": (1.20, "Trabajo sentado, poco movimiento"),
    "ligero":     (1.375, "Algo de movimiento o 1-3 entrenos por semana"),
    "moderado":   (1.55, "3-5 entrenos por semana"),
    "alto":       (1.725, "6-7 entrenos por semana"),
    "muy_alto":   (1.90, "Doble sesión o trabajo físico duro"),
}

# Los somatotipos (ectomorfo/mesomorfo/endomorfo) vienen de una
# clasificación de los años 40 y NO están respaldados por la ciencia
# moderna: no predicen de verdad cómo responde tu cuerpo. Se usan mucho en
# el mundo del gimnasio, así que los mantenemos, pero solo como un ajuste
# pequeño (±5%). Quien manda de verdad es la fórmula de gasto calórico.
AJUSTE_SOMATOTIPO = {
    "ectomorfo":  (1.05, "Delgado por naturaleza, le cuesta ganar peso"),
    "mesomorfo":  (1.00, "Constitución atlética, gana músculo con facilidad"),
    "endomorfo":  (0.95, "Tiende a acumular grasa con más facilidad"),
    "no_lo_se":   (1.00, "Sin clasificar (es la opción más honesta)"),
}

OBJETIVOS = {
    "perder_grasa":  "Perder grasa",
    "ganar_musculo": "Ganar músculo",
    "ganar_peso":    "Ganar peso",
    "ganar_fuerza":  "Ganar fuerza",
    "mantener":      "Mantenerme",
}

NIVELES = {
    "principiante": "Menos de 1 año entrenando",
    "intermedio":   "Entre 1 y 3 años entrenando",
    "avanzado":     "Más de 3 años entrenando",
}

# Series, repeticiones y descanso según lo que busques.
ESQUEMAS = {
    "perder_grasa":  {"series": 3, "reps": "10-15", "descanso": "45-75 s"},
    "ganar_musculo": {"series": 4, "reps": "8-12",  "descanso": "90-120 s"},
    "ganar_peso":    {"series": 4, "reps": "8-12",  "descanso": "90-120 s"},
    "ganar_fuerza":  {"series": 5, "reps": "4-6",   "descanso": "2-4 min"},
    "mantener":      {"series": 3, "reps": "8-12",  "descanso": "90 s"},
}

LIMITACIONES = {
    "rodilla":  "Molestias de rodilla",
    "hombro":   "Molestias de hombro",
    "espalda":  "Molestias lumbares o de espalda",
    "muneca":   "Molestias de muñeca",
    "sin_material": "Entreno en casa sin material",
    "poco_tiempo":  "Menos de 45 minutos por sesión",
}


# ---------------------------------------------------------------------------
# Catálogo de ejercicios
# ---------------------------------------------------------------------------
# Cada ejercicio lleva:
#   grupo    -> qué músculo trabaja
#   tipo     -> compuesto (varias articulaciones) o aislamiento
#   casa     -> si se puede hacer sin material de gimnasio
#   evitar   -> con qué limitaciones NO conviene hacerlo
#   alt      -> con qué sustituirlo si toca evitarlo

EJERCICIOS = [
    # --- Pecho ---
    {"nombre": "Press de banca con barra", "grupo": "pecho", "tipo": "compuesto",
     "casa": False, "evitar": ["hombro", "muneca", "sin_material"],
     "alt": "Press de banca con mancuernas (agarre neutro)"},
    {"nombre": "Press de banca con mancuernas", "grupo": "pecho", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Flexiones"},
    {"nombre": "Press inclinado con mancuernas", "grupo": "pecho", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Flexiones con los pies elevados"},
    {"nombre": "Flexiones", "grupo": "pecho", "tipo": "compuesto",
     "casa": True, "evitar": ["muneca"],
     "alt": "Flexiones sobre los puños o con mancuernas"},
    {"nombre": "Aperturas con mancuernas", "grupo": "pecho", "tipo": "aislamiento",
     "casa": False, "evitar": ["hombro", "sin_material"],
     "alt": "Cruces en polea a la altura del pecho"},
    {"nombre": "Fondos en paralelas", "grupo": "pecho", "tipo": "compuesto",
     "casa": False, "evitar": ["hombro", "sin_material"],
     "alt": "Fondos en banco con recorrido corto"},

    # --- Espalda ---
    {"nombre": "Dominadas", "grupo": "espalda", "tipo": "compuesto",
     "casa": True, "evitar": ["hombro"],
     "alt": "Jalón al pecho con agarre neutro"},
    {"nombre": "Jalón al pecho", "grupo": "espalda", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Dominadas asistidas con goma"},
    {"nombre": "Remo con barra", "grupo": "espalda", "tipo": "compuesto",
     "casa": False, "evitar": ["espalda", "sin_material"],
     "alt": "Remo con apoyo en banco (sin carga lumbar)"},
    {"nombre": "Remo con apoyo en banco", "grupo": "espalda", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Remo con goma elástica sentado"},
    {"nombre": "Remo con mancuerna a una mano", "grupo": "espalda", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Remo con goma elástica"},
    {"nombre": "Remo con goma elástica", "grupo": "espalda", "tipo": "compuesto",
     "casa": True, "evitar": [],
     "alt": "Remo invertido bajo una mesa"},
    {"nombre": "Face pull", "grupo": "espalda", "tipo": "aislamiento",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Face pull con goma elástica"},

    # --- Pierna ---
    {"nombre": "Sentadilla con barra", "grupo": "pierna", "tipo": "compuesto",
     "casa": False, "evitar": ["rodilla", "espalda", "sin_material"],
     "alt": "Prensa de piernas con recorrido parcial"},
    {"nombre": "Prensa de piernas", "grupo": "pierna", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Sentadilla búlgara con peso corporal"},
    {"nombre": "Peso muerto rumano", "grupo": "pierna", "tipo": "compuesto",
     "casa": False, "evitar": ["espalda", "sin_material"],
     "alt": "Curl femoral tumbado"},
    {"nombre": "Curl femoral", "grupo": "pierna", "tipo": "aislamiento",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Puente de glúteo a una pierna"},
    {"nombre": "Extensión de cuádriceps", "grupo": "pierna", "tipo": "aislamiento",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Sentadilla isométrica contra la pared"},
    {"nombre": "Sentadilla búlgara", "grupo": "pierna", "tipo": "compuesto",
     "casa": True, "evitar": ["rodilla"],
     "alt": "Hip thrust (empuje de cadera)"},
    {"nombre": "Hip thrust", "grupo": "pierna", "tipo": "compuesto",
     "casa": True, "evitar": [],
     "alt": "Puente de glúteo en el suelo"},
    {"nombre": "Sentadilla con peso corporal", "grupo": "pierna", "tipo": "compuesto",
     "casa": True, "evitar": ["rodilla"],
     "alt": "Hip thrust (empuje de cadera)"},
    {"nombre": "Zancadas", "grupo": "pierna", "tipo": "compuesto",
     "casa": True, "evitar": ["rodilla"],
     "alt": "Peso muerto rumano con mancuernas"},
    {"nombre": "Elevación de gemelos", "grupo": "pierna", "tipo": "aislamiento",
     "casa": True, "evitar": [],
     "alt": "Elevación de gemelos a una pierna"},

    # --- Hombro ---
    {"nombre": "Press militar con barra", "grupo": "hombro", "tipo": "compuesto",
     "casa": False, "evitar": ["hombro", "espalda", "muneca", "sin_material"],
     "alt": "Press de hombro con mancuernas (agarre neutro)"},
    {"nombre": "Press de hombro con mancuernas", "grupo": "hombro", "tipo": "compuesto",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Press de hombro con gomas"},
    {"nombre": "Elevaciones laterales", "grupo": "hombro", "tipo": "aislamiento",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Elevaciones laterales con goma elástica"},
    {"nombre": "Elevaciones laterales con goma", "grupo": "hombro", "tipo": "aislamiento",
     "casa": True, "evitar": [],
     "alt": "Elevaciones frontales con una botella de agua"},
    {"nombre": "Pájaros (deltoides posterior)", "grupo": "hombro", "tipo": "aislamiento",
     "casa": True, "evitar": [],
     "alt": "Face pull con goma elástica"},

    # --- Brazo ---
    {"nombre": "Curl de bíceps con barra", "grupo": "brazo", "tipo": "aislamiento",
     "casa": False, "evitar": ["muneca", "sin_material"],
     "alt": "Curl martillo con mancuernas"},
    {"nombre": "Curl martillo", "grupo": "brazo", "tipo": "aislamiento",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Curl con goma elástica"},
    {"nombre": "Curl con goma elástica", "grupo": "brazo", "tipo": "aislamiento",
     "casa": True, "evitar": [],
     "alt": "Curl con mochila cargada"},
    {"nombre": "Extensión de tríceps en polea", "grupo": "brazo", "tipo": "aislamiento",
     "casa": False, "evitar": ["sin_material"],
     "alt": "Fondos en banco"},
    {"nombre": "Fondos en banco", "grupo": "brazo", "tipo": "compuesto",
     "casa": True, "evitar": ["hombro"],
     "alt": "Flexiones diamante"},
    {"nombre": "Flexiones diamante", "grupo": "brazo", "tipo": "compuesto",
     "casa": True, "evitar": ["muneca"],
     "alt": "Extensión de tríceps con goma elástica"},

    # --- Core ---
    {"nombre": "Plancha abdominal", "grupo": "core", "tipo": "aislamiento",
     "casa": True, "evitar": ["muneca"],
     "alt": "Plancha apoyando los antebrazos"},
    {"nombre": "Elevación de piernas colgado", "grupo": "core", "tipo": "aislamiento",
     "casa": False, "evitar": ["hombro", "sin_material"],
     "alt": "Elevación de piernas tumbado"},
    {"nombre": "Elevación de piernas tumbado", "grupo": "core", "tipo": "aislamiento",
     "casa": True, "evitar": ["espalda"],
     "alt": "Bicho muerto (dead bug)"},
    {"nombre": "Bicho muerto (dead bug)", "grupo": "core", "tipo": "aislamiento",
     "casa": True, "evitar": [],
     "alt": "Plancha apoyando los antebrazos"},
    {"nombre": "Rueda abdominal", "grupo": "core", "tipo": "compuesto",
     "casa": False, "evitar": ["espalda", "muneca", "sin_material"],
     "alt": "Plancha apoyando los antebrazos"},

    # --- Cardio ---
    {"nombre": "Cardio suave 20-30 min", "grupo": "cardio", "tipo": "cardio",
     "casa": True, "evitar": [],
     "alt": "Caminar a paso rápido 40 min"},
    {"nombre": "Intervalos (HIIT) 15 min", "grupo": "cardio", "tipo": "cardio",
     "casa": True, "evitar": ["rodilla"],
     "alt": "Cardio suave 30 min en bici estática"},
]


# ---------------------------------------------------------------------------
# Los números: metabolismo, calorías y macros
# ---------------------------------------------------------------------------

def calcular_metricas(perfil: dict) -> dict:
    """
    IMC, metabolismo basal y calorías de mantenimiento.

    Usa la fórmula de Mifflin-St Jeor, que es la que mejor acierta de las
    que se calculan solo con peso, altura, edad y sexo.
    """
    peso = float(perfil["peso"])          # kg
    altura = float(perfil["altura"])      # cm
    edad = int(perfil["edad"])
    sexo = perfil.get("sexo", "hombre")

    # Metabolismo basal: lo que gastas estando en reposo todo el día
    basal = 10 * peso + 6.25 * altura - 5 * edad
    basal += 5 if sexo == "hombre" else -161

    factor, _ = FACTORES_ACTIVIDAD.get(perfil.get("actividad", "moderado"),
                                       FACTORES_ACTIVIDAD["moderado"])
    ajuste, _ = AJUSTE_SOMATOTIPO.get(perfil.get("somatotipo", "no_lo_se"),
                                      (1.0, ""))

    mantenimiento = basal * factor * ajuste

    altura_m = altura / 100
    imc = peso / (altura_m ** 2)

    if imc < 18.5:
        clasificacion = "por debajo del peso recomendado"
    elif imc < 25:
        clasificacion = "en un rango de peso saludable"
    elif imc < 30:
        clasificacion = "por encima del peso recomendado"
    else:
        clasificacion = "en rango de obesidad según el IMC"

    return {
        "imc": round(imc, 1),
        "clasificacion_imc": clasificacion,
        "peso_saludable_min": round(18.5 * altura_m ** 2, 1),
        "peso_saludable_max": round(24.9 * altura_m ** 2, 1),
        "basal": round(basal),
        "mantenimiento": round(mantenimiento),
    }


def calcular_nutricion(perfil: dict, metricas: dict) -> dict:
    """Calorías objetivo y reparto de macronutrientes."""
    peso = float(perfil["peso"])
    objetivo = perfil.get("objetivo", "mantener")
    mantenimiento = metricas["mantenimiento"]

    # Cuánto nos desviamos del mantenimiento según el objetivo
    if objetivo == "perder_grasa":
        calorias = mantenimiento * 0.80          # déficit del 20%
        proteina_por_kg = 2.2                    # más proteína para no perder músculo
        explicacion = "un 20% por debajo de tu mantenimiento"
    elif objetivo == "ganar_musculo":
        calorias = mantenimiento * 1.10          # superávit contenido
        proteina_por_kg = 1.8
        explicacion = "un 10% por encima de tu mantenimiento"
    elif objetivo == "ganar_peso":
        calorias = mantenimiento * 1.20          # superávit mayor
        proteina_por_kg = 1.6
        explicacion = "un 20% por encima de tu mantenimiento"
    elif objetivo == "ganar_fuerza":
        calorias = mantenimiento * 1.05
        proteina_por_kg = 1.8
        explicacion = "ligeramente por encima de tu mantenimiento"
    else:  # mantener
        calorias = mantenimiento
        proteina_por_kg = 1.6
        explicacion = "tu mantenimiento"

    proteina_g = round(peso * proteina_por_kg)
    grasa_g = round(peso * 0.9)                  # mínimo sano para las hormonas
    kcal_restantes = calorias - (proteina_g * 4) - (grasa_g * 9)
    carbos_g = max(round(kcal_restantes / 4), 0)

    return {
        "calorias": round(calorias),
        "explicacion": explicacion,
        "proteina_g": proteina_g,
        "grasa_g": grasa_g,
        "carbos_g": carbos_g,
        "agua_litros": round(peso * 0.035, 1),
    }


def estimar_plazo(perfil: dict, metricas: dict) -> dict:
    """
    Cuánto se tarda en llegar a la meta, a un ritmo sostenible.

    Los ritmos que usa no son inventados: perder más de un 1% del peso
    corporal por semana empieza a costar músculo, y ganar músculo tiene un
    techo biológico que no se salta por comer más.
    """
    peso = float(perfil["peso"])
    objetivo = perfil.get("objetivo", "mantener")
    nivel = perfil.get("nivel", "principiante")
    meta_peso = perfil.get("peso_objetivo")

    if objetivo == "mantener" or not meta_peso:
        return {
            "aplica": False,
            "mensaje": "Sin meta de peso concreta: el plan va enfocado a mantener y mejorar.",
        }

    meta_peso = float(meta_peso)
    diferencia = abs(meta_peso - peso)

    if diferencia < 0.5:
        return {"aplica": False, "mensaje": "Ya estás prácticamente en tu peso objetivo."}

    perdiendo = meta_peso < peso

    # ANTES QUE NADA: ¿el peso al que quieres llegar es sano?
    # Que dé tiempo a conseguirlo no significa que convenga conseguirlo.
    altura_m = float(perfil["altura"]) / 100
    imc_meta = meta_peso / (altura_m ** 2)
    meta_insana = None

    if imc_meta < 18.5:
        minimo_sano = round(18.5 * altura_m ** 2, 1)
        meta_insana = {
            "meta_segura": minimo_sano,
            "motivo": (f"Con {meta_peso} kg tu IMC quedaría en {imc_meta:.1f}, por debajo "
                       f"del rango saludable (18,5). Para tu altura, el mínimo recomendable "
                       f"son unos {minimo_sano} kg. He calculado el plan hacia ese peso."),
        }
    elif imc_meta >= 30:
        maximo_sano = round(24.9 * altura_m ** 2, 1)
        meta_insana = {
            "meta_segura": maximo_sano,
            "motivo": (f"Con {meta_peso} kg tu IMC quedaría en {imc_meta:.1f}, ya en rango "
                       f"de obesidad. Si lo que buscas es ganar músculo, se hace sin llegar "
                       f"a ese peso. He calculado el plan hacia unos {maximo_sano} kg."),
        }

    # Si la meta no es sana, recalculamos sobre el peso seguro
    if meta_insana:
        meta_peso = meta_insana["meta_segura"]
        diferencia = abs(meta_peso - peso)
        perdiendo = meta_peso < peso
        if diferencia < 0.5:
            return {
                "aplica": False,
                "meta_insana": meta_insana,
                "mensaje": meta_insana["motivo"] + " Y ahí ya estás, así que el plan va "
                           "enfocado a mantener y mejorar composición.",
            }

    if perdiendo:
        # Entre 0,5% y 1% del peso corporal por semana
        kg_semana_lento = peso * 0.005
        kg_semana_rapido = peso * 0.010
        nota = ("A más velocidad no se pierde más grasa: se pierde más músculo. "
                "Por eso el ritmo va atado a tu peso y no a un número fijo.")
    else:
        # Ganancia de músculo: depende mucho de la experiencia previa
        ritmos = {"principiante": (0.010, 0.015),
                  "intermedio":   (0.005, 0.010),
                  "avanzado":     (0.0025, 0.005)}
        lento_mes, rapido_mes = ritmos.get(nivel, ritmos["principiante"])
        kg_semana_lento = peso * lento_mes / 4.345
        kg_semana_rapido = peso * rapido_mes / 4.345
        nota = ("Cuanta más experiencia tienes, más despacio se gana músculo. "
                "Comer de más por encima de esto añade grasa, no músculo.")

    semanas_rapido = diferencia / kg_semana_rapido
    semanas_lento = diferencia / kg_semana_lento

    # ¿Es una meta razonable? Más de un año y medio se hace muy cuesta arriba.
    realista = semanas_rapido <= 78
    ajuste = None
    if not realista:
        # Proponemos una meta intermedia a 6 meses, que sí se puede sostener
        kg_en_6_meses = kg_semana_rapido * 26
        meta_intermedia = peso - kg_en_6_meses if perdiendo else peso + kg_en_6_meses
        ajuste = {
            "meta_intermedia": round(meta_intermedia, 1),
            "motivo": (f"Llegar a {meta_peso} kg llevaría más de año y medio, y a esa "
                       f"distancia casi nadie aguanta. Mejor apunta a "
                       f"{round(meta_intermedia, 1)} kg en 6 meses y revalúas allí."),
        }

    return {
        "aplica": True,
        "meta_insana": meta_insana,
        "meta_usada": round(meta_peso, 1),
        "direccion": "perder" if perdiendo else "ganar",
        "diferencia_kg": round(diferencia, 1),
        "ritmo_semanal": f"{kg_semana_lento:.2f}-{kg_semana_rapido:.2f} kg/semana",
        "semanas_min": int(semanas_rapido),
        "semanas_max": int(semanas_lento),
        "meses_min": round(semanas_rapido / 4.345, 1),
        "meses_max": round(semanas_lento / 4.345, 1),
        "realista": realista,
        "ajuste_sugerido": ajuste,
        "nota": nota,
    }


# ---------------------------------------------------------------------------
# La rutina de la semana
# ---------------------------------------------------------------------------

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Qué grupos toca cada tipo de sesión, y en qué orden (primero lo pesado).
PLANTILLAS = {
    "cuerpo_entero": ("Cuerpo entero", ["pierna", "espalda", "pecho", "hombro", "brazo", "core"]),
    "torso":         ("Torso", ["pecho", "espalda", "hombro", "brazo", "brazo", "core"]),
    "pierna":        ("Pierna", ["pierna", "pierna", "pierna", "pierna", "core"]),
    "empuje":        ("Empuje (pecho, hombro, tríceps)", ["pecho", "pecho", "hombro", "hombro", "brazo"]),
    "tiron":         ("Tirón (espalda y bíceps)", ["espalda", "espalda", "espalda", "brazo", "brazo"]),
    "cardio":        ("Cardio y core", ["cardio", "core", "core"]),
}

# Qué sesiones se hacen según cuántos días puedas entrenar.
REPARTOS = {
    1: ["cuerpo_entero"],
    2: ["cuerpo_entero", "cuerpo_entero"],
    3: ["empuje", "tiron", "pierna"],
    4: ["torso", "pierna", "torso", "pierna"],
    5: ["empuje", "tiron", "pierna", "torso", "cardio"],
    6: ["empuje", "tiron", "pierna", "empuje", "tiron", "pierna"],
    7: ["empuje", "tiron", "pierna", "empuje", "tiron", "pierna", "cardio"],
}


def _ejercicio_valido(ejercicio: dict, limitaciones: list) -> bool:
    """¿Este ejercicio es apto con las limitaciones que tiene la persona?"""
    return not any(lim in ejercicio["evitar"] for lim in limitaciones)


def _elegir_ejercicios(grupos: list, limitaciones: list, variante: int = 0) -> list:
    """
    Escoge un ejercicio por cada hueco de la plantilla, sin repetir, dando
    prioridad a los compuestos (rinden más por minuto) y respetando las
    limitaciones. Si uno no vale, se anota con qué se ha sustituido.

    `variante` sirve para que dos sesiones del mismo tipo en la misma semana
    (por ejemplo dos días de torso) no salgan calcadas: rota la elección
    dentro de los ejercicios válidos.
    """
    elegidos = []
    usados = set()

    for grupo in grupos:
        candidatos = [e for e in EJERCICIOS if e["grupo"] == grupo and e["nombre"] not in usados]
        if not candidatos:
            continue

        # Los compuestos van primero
        candidatos.sort(key=lambda e: 0 if e["tipo"] == "compuesto" else 1)

        aptos = [e for e in candidatos if _ejercicio_valido(e, limitaciones)]
        if aptos:
            elegido = aptos[variante % len(aptos)]

            # ¿Hubo que descartar alguno mejor por una limitación? Lo anotamos
            # como usado para no repetir el mismo aviso en cada hueco del mismo
            # grupo muscular ("en lugar de sentadilla" tres veces seguidas).
            descartado = next((e for e in candidatos if e is not elegido
                               and not _ejercicio_valido(e, limitaciones)), None)
            if descartado:
                usados.add(descartado["nombre"])

            elegidos.append({
                "nombre": elegido["nombre"],
                "grupo": grupo,
                "alternativa": elegido["alt"],
                "sustituye_a": descartado["nombre"] if descartado else None,
            })
            usados.add(elegido["nombre"])
        else:
            # Ninguno vale: proponemos la alternativa del primero
            elegidos.append({
                "nombre": candidatos[0]["alt"],
                "grupo": grupo,
                "alternativa": None,
                "sustituye_a": candidatos[0]["nombre"],
            })

    return elegidos


def generar_rutina(perfil: dict) -> list:
    """Devuelve los 7 días de la semana, con entreno o descanso en cada uno."""
    dias_disponibles = int(perfil.get("dias_semana", 3))
    dias_disponibles = max(1, min(dias_disponibles, 7))
    limitaciones = perfil.get("limitaciones", [])
    objetivo = perfil.get("objetivo", "mantener")
    esquema = ESQUEMAS.get(objetivo, ESQUEMAS["mantener"])

    # Si hay poco tiempo, recortamos los ejercicios de cada sesión
    tope = 4 if "poco_tiempo" in limitaciones else 99

    reparto = REPARTOS[dias_disponibles]

    # Repartimos los entrenos a lo largo de la semana dejando descansos
    # espaciados, en vez de amontonarlos al principio.
    posiciones = [round(i * 7 / dias_disponibles) for i in range(dias_disponibles)]

    semana = []
    indice_entreno = 0
    veces_usada = {}   # cuántas veces ha salido ya cada tipo de sesión
    for numero_dia, nombre_dia in enumerate(DIAS_SEMANA):
        if indice_entreno < len(posiciones) and numero_dia == posiciones[indice_entreno]:
            clave = reparto[indice_entreno]
            titulo, grupos = PLANTILLAS[clave]

            # Si esta sesión ya salió antes en la semana, cambiamos los
            # ejercicios para que el segundo día no sea calcado al primero.
            variante = veces_usada.get(clave, 0)
            veces_usada[clave] = variante + 1
            if variante:
                titulo = f"{titulo} · variante {variante + 1}"

            ejercicios = _elegir_ejercicios(grupos, limitaciones, variante)[:tope]

            # En definición añadimos algo de cardio al final si no lo lleva ya
            if objetivo == "perder_grasa" and clave != "cardio":
                ejercicios.append({
                    "nombre": "Cardio suave 20 min al terminar", "grupo": "cardio",
                    "alternativa": "Caminar 30 min", "sustituye_a": None,
                })

            semana.append({
                "dia": nombre_dia,
                "descanso": False,
                "titulo": titulo,
                "series": esquema["series"],
                "reps": esquema["reps"],
                "tiempo_descanso": esquema["descanso"],
                "ejercicios": ejercicios,
            })
            indice_entreno += 1
        else:
            semana.append({
                "dia": nombre_dia,
                "descanso": True,
                "titulo": "Descanso",
                "ejercicios": [],
            })

    return semana


# ---------------------------------------------------------------------------
# El menú del día
# ---------------------------------------------------------------------------
# Valores aproximados por ración. La idea no es contar al gramo, sino
# darte una plantilla realista que cuadre con tus calorías.

COMIDAS = {
    "desayuno": [
        {"nombre": "Avena con leche, plátano y canela", "kcal": 420, "prot": 18},
        {"nombre": "Tostadas integrales con aguacate y 2 huevos", "kcal": 480, "prot": 22},
        {"nombre": "Yogur griego con fruta y nueces", "kcal": 350, "prot": 24},
        {"nombre": "Tortilla de 3 huevos con pan integral", "kcal": 400, "prot": 26},
        {"nombre": "Batido de leche, avena, plátano y crema de cacahuete", "kcal": 620, "prot": 28},
    ],
    "comida": [
        {"nombre": "Pechuga de pollo con arroz y verduras", "kcal": 620, "prot": 48},
        {"nombre": "Lentejas con verduras y un huevo duro", "kcal": 560, "prot": 30},
        {"nombre": "Salmón al horno con patata y ensalada", "kcal": 680, "prot": 42},
        {"nombre": "Pasta integral con atún y tomate", "kcal": 600, "prot": 38},
        {"nombre": "Ternera magra salteada con quinoa", "kcal": 700, "prot": 50},
        {"nombre": "Ensalada de garbanzos, atún y verduras", "kcal": 450, "prot": 32},
    ],
    "cena": [
        {"nombre": "Merluza a la plancha con verduras salteadas", "kcal": 380, "prot": 38},
        {"nombre": "Revuelto de huevo con espinacas y pavo", "kcal": 420, "prot": 36},
        {"nombre": "Crema de verduras con pollo a la plancha", "kcal": 400, "prot": 40},
        {"nombre": "Tortilla francesa con ensalada y pan", "kcal": 450, "prot": 28},
        {"nombre": "Salteado de tofu con verduras y arroz", "kcal": 520, "prot": 26},
    ],
    "snack": [
        {"nombre": "Yogur griego natural", "kcal": 130, "prot": 15},
        {"nombre": "Puñado de almendras", "kcal": 180, "prot": 6},
        {"nombre": "Batido de proteína con agua", "kcal": 130, "prot": 25},
        {"nombre": "Fruta con crema de cacahuete", "kcal": 250, "prot": 8},
        {"nombre": "Requesón con miel", "kcal": 200, "prot": 20},
        {"nombre": "Tortitas de arroz con pavo", "kcal": 160, "prot": 14},
    ],
}


def sugerir_menu(calorias_objetivo: int, proteina_objetivo: int) -> dict:
    """
    Compone un día de comidas que se acerque a las calorías y la proteína
    marcadas. Prueba combinaciones y se queda con la que menos se desvía.
    """
    import itertools

    mejor = None
    menor_error = float("inf")

    # Probamos con 1, 2 y 3 snacks: con pocas calorías sobra uno, y con
    # objetivos altos hacen falta varios para no quedarse corto.
    for num_snacks in (1, 2, 3):
        for desayuno in COMIDAS["desayuno"]:
            for comida in COMIDAS["comida"]:
                for cena in COMIDAS["cena"]:
                    for snacks in itertools.combinations(COMIDAS["snack"], num_snacks):
                        platos = [desayuno, comida, cena, *snacks]
                        kcal = sum(p["kcal"] for p in platos)
                        prot = sum(p["prot"] for p in platos)

                        # Penalizamos más quedarse corto de proteína que de calorías
                        error = abs(kcal - calorias_objetivo) / max(calorias_objetivo, 1)
                        error += 1.5 * max(0, proteina_objetivo - prot) / max(proteina_objetivo, 1)

                        if error < menor_error:
                            menor_error = error
                            mejor = {
                                "desayuno": desayuno, "comida": comida,
                                "cena": cena, "snacks": list(snacks),
                                "kcal_base": kcal, "proteina_base": prot,
                            }

    # Aunque elijamos la mejor combinación, con platos fijos es imposible
    # clavar cualquier cifra. En vez de mentir con el total, decimos cuánto
    # hay que agrandar o reducir las raciones para cuadrarlo de verdad.
    factor = calorias_objetivo / mejor["kcal_base"] if mejor["kcal_base"] else 1.0
    factor = max(0.7, min(factor, 1.6))   # fuera de este rango ya sería otro menú

    mejor["factor_raciones"] = round(factor, 2)
    mejor["kcal_total"] = round(mejor["kcal_base"] * factor)
    mejor["proteina_total"] = round(mejor["proteina_base"] * factor)
    mejor["desviacion_kcal"] = mejor["kcal_total"] - calorias_objetivo

    if factor >= 1.08:
        mejor["ajuste_raciones"] = (
            f"Sirve las raciones un {round((factor - 1) * 100)}% más grandes "
            f"para llegar a tus {calorias_objetivo} kcal.")
    elif factor <= 0.92:
        mejor["ajuste_raciones"] = (
            f"Sirve las raciones un {round((1 - factor) * 100)}% más pequeñas "
            f"para ajustarte a tus {calorias_objetivo} kcal.")
    else:
        mejor["ajuste_raciones"] = "Raciones normales: el menú ya cuadra con tus calorías."

    return mejor


# ---------------------------------------------------------------------------
# Consejos y plan completo
# ---------------------------------------------------------------------------

def generar_consejos(perfil: dict, metricas: dict, plazo: dict) -> list:
    """Avisos y recomendaciones adaptados a este perfil concreto."""
    consejos = []
    objetivo = perfil.get("objetivo", "mantener")
    nivel = perfil.get("nivel", "principiante")
    limitaciones = perfil.get("limitaciones", [])
    dias = int(perfil.get("dias_semana", 3))

    # Sobre la meta: primero si es sana, luego si da tiempo
    if plazo.get("meta_insana"):
        consejos.append({
            "tipo": "aviso",
            "texto": plazo["meta_insana"]["motivo"],
        })
    if plazo.get("aplica") and not plazo.get("realista"):
        consejos.append({
            "tipo": "aviso",
            "texto": plazo["ajuste_sugerido"]["motivo"],
        })

    # Sobre el IMC
    if metricas["imc"] < 18.5 and objetivo == "perder_grasa":
        consejos.append({
            "tipo": "aviso",
            "texto": ("Tu IMC ya está por debajo del rango saludable. Perder más peso "
                      "no es buena idea: replantéate el objetivo hacia ganar músculo."),
        })
    elif metricas["imc"] >= 30 and objetivo == "ganar_peso":
        consejos.append({
            "tipo": "aviso",
            "texto": ("Con tu IMC actual, ganar peso general no suele ser lo más "
                      "recomendable. Plantéate ganar músculo manteniendo el peso."),
        })

    # Sobre la frecuencia
    if dias <= 2 and objetivo in ("ganar_musculo", "ganar_fuerza"):
        consejos.append({
            "tipo": "consejo",
            "texto": (f"Con {dias} día(s) por semana se progresa, pero despacio. Si algún "
                      "día puedes sacar un tercero, notarás bastante diferencia."),
        })
    if dias >= 6 and nivel == "principiante":
        consejos.append({
            "tipo": "consejo",
            "texto": ("Empezando, 6-7 días es mucho: el músculo crece descansando, no "
                      "entrenando. Con 3-4 días bien hechos irías igual de rápido y con "
                      "menos riesgo de lesión."),
        })

    # Por limitación
    if "rodilla" in limitaciones:
        consejos.append({
            "tipo": "adaptacion",
            "texto": ("He quitado sentadillas profundas y saltos. El trabajo de glúteo e "
                      "isquios (hip thrust, femoral) suele tolerarse bien y además "
                      "estabiliza la rodilla."),
        })
    if "hombro" in limitaciones:
        consejos.append({
            "tipo": "adaptacion",
            "texto": ("Fuera press por encima de la cabeza con barra y fondos profundos. "
                      "El agarre neutro con mancuernas suele molestar mucho menos."),
        })
    if "espalda" in limitaciones:
        consejos.append({
            "tipo": "adaptacion",
            "texto": ("Nada que cargue la zona lumbar sin apoyo: fuera peso muerto "
                      "convencional y remo con barra. Con apoyo en banco trabajas lo mismo "
                      "sin comprometer la espalda."),
        })
    if "sin_material" in limitaciones:
        consejos.append({
            "tipo": "adaptacion",
            "texto": ("Todo el plan es con peso corporal y gomas. Cuando esos ejercicios "
                      "se te queden cortos, sube repeticiones o baja más despacio: una "
                      "goma barata multiplica las opciones."),
        })
    if "poco_tiempo" in limitaciones:
        consejos.append({
            "tipo": "adaptacion",
            "texto": ("Sesiones recortadas a 4 ejercicios. Para ir aún más rápido, junta "
                      "ejercicios de grupos distintos en superseries y descansa solo "
                      "entre pares."),
        })

    # Según el objetivo
    if objetivo == "perder_grasa":
        consejos.append({
            "tipo": "consejo",
            "texto": ("Sigue entrenando fuerza aunque quieras perder grasa: es lo que le "
                      "dice al cuerpo que conserve el músculo mientras adelgazas."),
        })
    elif objetivo in ("ganar_musculo", "ganar_peso"):
        consejos.append({
            "tipo": "consejo",
            "texto": ("Si tras 2-3 semanas el peso no se mueve, sube unas 200 kcal. "
                      "Ajustar sobre lo que ves en la báscula acierta más que cualquier "
                      "fórmula."),
        })
    elif objetivo == "ganar_fuerza":
        consejos.append({
            "tipo": "consejo",
            "texto": ("Con pocas repeticiones, la técnica manda. Añade peso solo cuando "
                      "completes todas las series limpias."),
        })

    # Universal
    consejos.append({
        "tipo": "consejo",
        "texto": ("Dormir 7-9 horas influye en el resultado tanto como el entreno. Es lo "
                  "más barato y lo que más se descuida."),
    })

    return consejos


def plan_completo(perfil: dict) -> dict:
    """Junta todo: números, nutrición, plazos, rutina, menú y consejos."""
    metricas = calcular_metricas(perfil)
    nutricion = calcular_nutricion(perfil, metricas)
    plazo = estimar_plazo(perfil, metricas)

    return {
        "perfil": perfil,
        "metricas": metricas,
        "nutricion": nutricion,
        "plazo": plazo,
        "rutina": generar_rutina(perfil),
        "menu": sugerir_menu(nutricion["calorias"], nutricion["proteina_g"]),
        "consejos": generar_consejos(perfil, metricas, plazo),
        "aviso": ("Estos números son orientativos, calculados con fórmulas estándar. "
                  "No son consejo médico. Si tienes alguna condición de salud o tomas "
                  "medicación, coméntalo con un profesional antes de cambiar tu dieta "
                  "o tu entrenamiento."),
    }


def resumen_texto(plan: dict) -> str:
    """Versión en texto del plan, para que JOKER pueda contarlo por el chat."""
    m, n, p = plan["metricas"], plan["nutricion"], plan["plazo"]
    perfil = plan["perfil"]

    lineas = [
        f"Perfil: {perfil['peso']} kg, {perfil['altura']} cm, {perfil['edad']} años. "
        f"Objetivo: {OBJETIVOS.get(perfil.get('objetivo'), 'mantener')}.",
        f"IMC {m['imc']} ({m['clasificacion_imc']}). Peso saludable para tu altura: "
        f"{m['peso_saludable_min']}-{m['peso_saludable_max']} kg.",
        f"Mantenimiento: {m['mantenimiento']} kcal. Tu objetivo diario: {n['calorias']} kcal "
        f"({n['explicacion']}).",
        f"Macros: {n['proteina_g']} g de proteína, {n['carbos_g']} g de carbohidratos, "
        f"{n['grasa_g']} g de grasa. Agua: {n['agua_litros']} L.",
    ]

    if p.get("aplica"):
        lineas.append(
            f"Para {p['direccion']} {p['diferencia_kg']} kg a un ritmo sostenible "
            f"({p['ritmo_semanal']}): entre {p['meses_min']} y {p['meses_max']} meses."
        )
        if not p["realista"]:
            lineas.append("AVISO: " + p["ajuste_sugerido"]["motivo"])
    else:
        lineas.append(p.get("mensaje", ""))

    dias_entreno = [d for d in plan["rutina"] if not d["descanso"]]
    lineas.append(f"Rutina: {len(dias_entreno)} días por semana -> " +
                  ", ".join(f"{d['dia']} ({d['titulo']})" for d in dias_entreno))

    menu = plan["menu"]
    lineas.append(
        f"Menú de hoy ({menu['kcal_total']} kcal, {menu['proteina_total']} g de proteína): "
        f"desayuno, {menu['desayuno']['nombre']}; comida, {menu['comida']['nombre']}; "
        f"cena, {menu['cena']['nombre']}; snacks, " +
        " y ".join(s["nombre"] for s in menu["snacks"]) + "."
    )

    avisos = [c["texto"] for c in plan["consejos"] if c["tipo"] == "aviso"]
    if avisos:
        lineas.append("Avisos: " + " ".join(avisos))

    return "\n".join(lineas)
