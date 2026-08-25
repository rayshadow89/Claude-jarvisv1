READ ME

que hará mi jarvis.v1

Decir el tiempo y la hora de la ubicación pedida, buscar información en
internet y resolver problemas básicos de matemáticas.


ÚLTIMO CAMBIO (resumen rápido)
-------------------------------

Primero probamos con Claude (de pago) y luego con Gemini (Google), que
decía ser gratis pero fue dando problemas: modelos que dejaban de
funcionar, avisos de facturación, cambios de un día para otro. Así que
hemos cambiado a Groq, que también es gratis pero de forma estable: sin
tarjeta, sin sorpresas, sin "actualízate o paga".

jarvis.py ahora usa Groq. Las versiones anteriores (jarvis_gemini.py,
jarvis_claude.py) se han dejado como referencia por si algún día quieres
comparar o volver a probarlas.


DÓNDE LO DEJASTE / QUÉ FALTA POR HACER
-----------------------------------------

Pendiente de hacer la próxima vez que retomes esto:

  [ ] 1. Actualizar la carpeta:      git pull
  [ ] 2. Instalar lo nuevo:          pip install -r requirements.txt
  [ ] 3. Sacar tu clave gratis en:   https://console.groq.com/keys
  [ ] 4. Ponerla en la terminal:     $env:GROQ_API_KEY="tu-clave"
  [ ] 5. Arrancar Jarvis:            python jarvis.py
  [ ] 6. Probarlo y contarle a Claude cómo ha ido

Todos los detalles de cada paso están más abajo, en "CÓMO PONERLO EN
MARCHA".


FICHEROS DEL PROYECTO
---------------------

  jarvis.py         El asistente, por defecto. Usa Groq -> GRATIS y estable.
  jarvis_gemini.py  La misma idea con Gemini (Google). Referencia: dio
                    problemas de facturación, puede que no funcione ya.
  jarvis_claude.py  La misma idea con Claude (Anthropic) -> DE PAGO.
                    Está aquí solo como referencia/comparación.
  tools.py          Las habilidades de Jarvis (hora, clima, matemáticas,
                    búsqueda web). No depende de ningún proveedor, la
                    comparten las tres versiones.
  requirements.txt  Las librerías que hay que instalar.


CÓMO PONERLO EN MARCHA (versión por defecto, con Groq)
---------------------------------------------------------

1. Instala las dependencias, desde esta misma carpeta:

     pip install -r requirements.txt

2. Consigue una clave gratuita de Groq en:

     https://console.groq.com/keys

   Es gratis, sin tarjeta, y no tiene fecha de caducidad conocida (a
   diferencia de lo que nos pasó con Gemini). Tiene límites de peticiones
   por minuto y por día, de sobra para trastear.

3. Configura la clave en la terminal (dura hasta que cierres la ventana):

     Windows PowerShell:  $env:GROQ_API_KEY="tu-clave"
     Windows cmd:         set GROQ_API_KEY=tu-clave
     Mac / Linux:         export GROQ_API_KEY="tu-clave"

   Alternativa más cómoda: crea un fichero llamado .env en esta carpeta con
   esta línea dentro, y se cargará sola cada vez:

     GROQ_API_KEY=tu-clave

4. Arranca Jarvis:

     python jarvis.py

5. Pruébalo:

     ¿qué hora es en Tokio?
     cuánto es (45 * 8) / 3
     busca información sobre el Real Madrid

   Escribe 'salir' para terminar.


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
---------------------------------

Todo se hace en tools.py, en tres pasos:

  1. Escribe una función de Python normal (por ejemplo, poner_alarma).
  2. Añade su descripción y sus parámetros a la lista TOOL_SCHEMAS.
  3. Regístrala en el diccionario TOOL_FUNCTIONS.

El modelo decide solo cuándo llamarla, basándose en la descripción que le
escribas. Cuanto más claro digas CUÁNDO debe usarse (no solo qué hace),
mejor acertará.
