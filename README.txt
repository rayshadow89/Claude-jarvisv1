JOKER
"La última carta del mazo"


QUÉ ES
------

Un asistente personal con IA que dice la hora y el clima de cualquier
lugar del mundo, busca información y resuelve problemas de matemáticas.
Se llamó "Jarvis" al principio; ahora es JOKER, con página web propia en
burdeos y negro.

Se puede usar de dos formas:
  - Desde una página web con interfaz de chat  ->  python app.py
  - Desde la terminal, sin adornos              ->  python joker.py


DÓNDE ESTAMOS AHORA MISMO
----------------------------

FUNCIONANDO Y TERMINADO. La página web está completa: el chat, los
colores burdeos y negro, el título JOKER, el eslogan, la imagen del
diablillo y el icono de la pestaña del navegador. Todo probado.

Para usarlo, cada vez:

  1. Colócate en la rama main:     git checkout main
  2. Actualiza:                     git pull
  3. Pon la clave:                  $env:GROQ_API_KEY="tu-clave"
  4. Arranca la web:                python app.py
  5. Abre en el navegador:          http://127.0.0.1:5000

(el paso 1 solo hace falta si alguna vez te cambias de rama sin querer)


AVISO IMPORTANTE: USA SIEMPRE LA RAMA "main"
-----------------------------------------------

Este proyecto tiene dos ramas en GitHub:

  main    <- LA BUENA. Aquí está lo terminado y probado. USA ESTA.
  claude/python-function-calling-script-...  <- zona de trabajo de Claude.
          Cambia constantemente y puede estar a medias. NO la uses.

Si en algún momento algo "deja de funcionar" sin motivo, lo primero que
hay que mirar es en qué rama estás:

  git branch

El asterisco (*) tiene que estar en main. Si no lo está:

  git checkout main
  git pull

Esto ya ha pasado dos veces y fue la causa real del problema las dos.


TODO EL CAMINO RECORRIDO (por si quieres el porqué de algo)
---------------------------------------------------------------

1. Empezamos con la API de Claude (Anthropic) como esqueleto de function
   calling. Es de pago, así que se descartó como opción por defecto.

2. Se probó con Gemini (Google), que se anunciaba como gratis. Dio
   problemas: modelos que dejaban de estar disponibles, avisos de tener
   que activar facturación, cambios de un día para otro. Se descartó.
   (Se conserva en joker_gemini.py por si algún día se quiere retomar.)

3. Se migró a Groq: gratis de verdad, sin tarjeta, con límites de uso
   generosos para un proyecto personal. Es el que se usa ahora.

4. La hora fallaba en TODAS las ciudades en Windows. Causa: Windows no
   trae de serie la base de datos de zonas horarias del mundo (Linux y
   Mac sí). Arreglado instalando "tzdata" y haciendo que la hora se
   resuelva primero sin necesidad de internet (con alias en español para
   ciudades y países), y solo si hace falta se consulta una API externa
   gratuita (Open-Meteo) para ubicaciones menos conocidas.

5. Se cambió el nombre del proyecto de "Jarvis" a "JOKER", con el eslogan
   "La última carta del mazo".

6. Se creó la página web (app.py + templates/index.html): un chat en
   burdeos y negro que por dentro usa exactamente el mismo motor y las
   mismas herramientas que la versión de terminal.

7. La imagen de la mascota no aparecía. Hubo dos causas encadenadas:
   primero, se pedía con un nombre de archivo fijo ("joker.png") y hubo
   cambios hechos a la vez desde el terminal y desde la web de GitHub
   que se cruzaron; y segundo, la copia local estaba en la rama de
   trabajo de Claude en vez de en main, así que no recibía el arreglo.
   Resuelto con una ruta flexible (/mascota) que encuentra cualquier
   archivo que empiece por "joker" sea cual sea su extensión, y
   volviendo a la rama main. Ya funciona.

8. Se añadió el icono de la pestaña del navegador (favicon), que
   reutiliza la misma imagen del diablillo.


FICHEROS DEL PROYECTO
----------------------

  app.py            El servidor de la página web. Es lo que ejecutas para
                    usar JOKER desde el navegador.
  templates/        El diseño de la página web (index.html).
  static/           Imágenes. Aquí está joker.jpg (la mascota).

  joker.py          El asistente en versión terminal. Contiene el "motor"
                    (el loop que habla con la IA), que la web reutiliza.
  tools.py          Las habilidades de JOKER: hora, clima, matemáticas y
                    búsqueda. No depende de ningún proveedor de IA.

  joker_gemini.py   La misma idea con Gemini (Google). Referencia: dio
                    problemas de facturación, puede que no funcione ya.
  joker_claude.py   La misma idea con Claude (Anthropic) -> DE PAGO.
                    Está aquí solo como referencia/comparación.

  requirements.txt  Las librerías que hay que instalar.


CÓMO PONERLO EN MARCHA
-----------------------

1. Instala las dependencias, desde esta misma carpeta:

     pip install -r requirements.txt

2. Consigue una clave gratuita de Groq en:

     https://console.groq.com/keys

   Es gratis y sin tarjeta. Tiene límites de peticiones por minuto y por
   día, de sobra para uso personal.

3. Configura la clave en la terminal (dura hasta que cierres la ventana):

     Windows PowerShell:  $env:GROQ_API_KEY="tu-clave"
     Windows cmd:         set GROQ_API_KEY=tu-clave
     Mac / Linux:         export GROQ_API_KEY="tu-clave"

   Alternativa más cómoda: crea un fichero llamado .env en esta carpeta con
   esta línea dentro, y se cargará sola cada vez:

     GROQ_API_KEY=tu-clave

4. Arranca la página web:

     python app.py

   Deja esa ventana abierta (es el servidor) y abre en el navegador:

     http://127.0.0.1:5000

   Para pararlo, pulsa Ctrl+C en la ventana de la terminal.

5. Pruébalo:

     ¿Qué hora es en Tokio?
     Cuánto es (45 * 8) / 3
     Busca información sobre Nikola Tesla


LA IMAGEN DE LA MASCOTA
-------------------------

Ya está puesta (static/joker.jpg). Si algún día quieres cambiarla, solo
tiene que EMPEZAR por "joker" (mayúsculas o minúsculas da igual) y ser
.png, .jpg, .jpeg, .webp o .gif — el nombre exacto no importa. Si no
hay ninguna, sale un 🃏 en su lugar y todo lo demás sigue funcionando.


CLIMA (opcional)
----------------

La tool del clima necesita otra clave, también gratuita:

  https://openweathermap.org/api

Configúrala igual que la anterior, con el nombre OPENWEATHER_API_KEY.
Sin ella, todo lo demás sigue funcionando.


LA BÚSQUEDA WEB, EN HONESTIDAD
--------------------------------

La tool de búsqueda usa la Wikipedia, no un buscador de verdad. Sirve para
"qué es X" o "quién fue X", pero no para noticias del día de hoy. Es la
opción que hemos elegido porque es gratis y no necesita clave. Si más
adelante quieres búsqueda real de internet, se puede sustituir por un
servicio como Tavily o Serper (tienen capa gratuita, pero piden registro).


CÓMO AÑADIRLE HABILIDADES NUEVAS
-----------------------------------

Todo se hace en tools.py, en tres pasos:

  1. Escribe una función de Python normal (por ejemplo, poner_alarma).
  2. Añade su descripción y sus parámetros a la lista TOOL_SCHEMAS.
  3. Regístrala en el diccionario TOOL_FUNCTIONS.

La habilidad nueva aparece automáticamente tanto en la web como en la
terminal, sin tocar nada más.

El modelo decide solo cuándo llamarla, basándose en la descripción que le
escribas. Cuanto más claro digas CUÁNDO debe usarse (no solo qué hace),
mejor acertará.


UN PAR DE COSAS A TENER EN CUENTA
-------------------------------------

- Las conversaciones de la web se guardan en la memoria del servidor, así
  que se borran al cerrar la ventana donde ejecutaste "python app.py". El
  botón "Nueva partida" las borra a mano cuando quieras empezar de cero.

- Si editas archivos directamente desde la web de GitHub mientras hay
  trabajo en curso aquí, es fácil que los cambios se crucen (ya ha pasado
  una vez, con la imagen de la mascota). Mejor pedir los cambios aquí, o
  avisar antes de tocar algo en GitHub.
