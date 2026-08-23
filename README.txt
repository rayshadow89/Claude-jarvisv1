READ ME

que hará mi jarvis.v1

Decir el tiempo y la hora de la ubicación pedida, buscar información en
internet y resolver problemas básicos de matemáticas.


FICHEROS DEL PROYECTO
---------------------

  jarvis.py         El asistente. Usa Gemini (Google) -> GRATIS.
  jarvis_claude.py  La misma idea pero con la API de Claude -> DE PAGO.
                    Está aquí solo como referencia/comparación.
  tools.py          Las habilidades de Jarvis (hora, clima, matemáticas).
                    No depende de ningún proveedor, la comparten los dos.
  requirements.txt  Las librerías que hay que instalar.


CÓMO PONERLO EN MARCHA (versión gratuita)
------------------------------------------

1. Instala las dependencias, desde esta misma carpeta:

     pip install -r requirements.txt

2. Consigue una clave gratuita de Gemini en:

     https://aistudio.google.com/apikey

   Es gratis y no pide tarjeta. Tiene límites de peticiones por minuto y
   por día, más que suficientes para trastear.

3. Configura la clave en la terminal (dura hasta que cierres la ventana):

     Windows PowerShell:  $env:GEMINI_API_KEY="tu-clave"
     Windows cmd:         set GEMINI_API_KEY=tu-clave
     Mac / Linux:         export GEMINI_API_KEY="tu-clave"

   Alternativa más cómoda: crea un fichero llamado .env en esta carpeta con
   esta línea dentro, y se cargará sola cada vez:

     GEMINI_API_KEY=tu-clave

4. Arranca Jarvis:

     python jarvis.py

5. Pruébalo:

     ¿qué hora es en Tokio?
     cuánto es (45 * 8) / 3
     busca las últimas noticias sobre el Real Madrid

   Escribe 'salir' para terminar.


CLIMA (opcional)
----------------

La tool del clima necesita otra clave, también gratuita:

  https://openweathermap.org/api

Configúrala igual que la anterior, con el nombre OPENWEATHER_API_KEY.
Sin ella, todo lo demás sigue funcionando.


CÓMO AÑADIRLE HABILIDADES NUEVAS
---------------------------------

Todo se hace en tools.py, en tres pasos:

  1. Escribe una función de Python normal (por ejemplo, poner_alarma).
  2. Añade su descripción y sus parámetros a la lista TOOL_SCHEMAS.
  3. Regístrala en el diccionario TOOL_FUNCTIONS.

El modelo decide solo cuándo llamarla, basándose en la descripción que le
escribas. Cuanto más claro digas CUÁNDO debe usarse (no solo qué hace),
mejor acertará.
