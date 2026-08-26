JOKER
"La última carta del mazo"


QUÉ HACE
--------

Un asistente personal que dice la hora y el tiempo de cualquier lugar del
mundo, busca información y resuelve problemas de matemáticas.

Se puede usar de dos formas:
  - Desde una página web con interfaz de chat  ->  python app.py
  - Desde la terminal, sin adornos             ->  python joker.py


ÚLTIMO CAMBIO (resumen rápido)
-------------------------------

El proyecto se llamaba Jarvis y ahora se llama JOKER. Además de cambiarle
el nombre a todo, ahora tiene una PÁGINA WEB con colores burdeos y negros,
en vez de tener que hablar con él desde la ventana negra de la terminal.


DÓNDE LO DEJASTE / QUÉ FALTA POR HACER
-----------------------------------------

  [ ] 1. Actualizar la carpeta:      git pull
  [ ] 2. Instalar lo nuevo:          pip install -r requirements.txt
  [ ] 3. Guardar la imagen del diablillo dentro de la carpeta "static"
         con un nombre que EMPIECE por "joker" (ej. joker.png o joker.jpg)
         (es lo único que no puedo hacer yo; sin ella sale un 🃏 en su sitio)
  [ ] 4. Poner la clave:             $env:GROQ_API_KEY="tu-clave"
  [ ] 5. Arrancar la web:            python app.py
  [ ] 6. Abrir en el navegador:      http://127.0.0.1:5000


FICHEROS DEL PROYECTO
---------------------

  app.py            El servidor de la página web. Es lo que ejecutas para
                    usar JOKER desde el navegador.
  templates/        El diseño de la página web (index.html).
  static/           Imágenes. Aquí va joker.png.

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


LA IMAGEN DE JOKER
-------------------

Guarda la imagen del diablillo en la carpeta "static". El nombre no tiene
que ser exacto: basta con que EMPIECE por "joker" (mayúsculas o minúsculas
da igual) y sea .png, .jpg, .jpeg, .webp o .gif. Por ejemplo, todos estos
valdrían:

    static/joker.png
    static/Joker.PNG
    static/joker_mascota.jpg

Si no encuentra ninguna, sale un 🃏 en su lugar y todo lo demás funciona
igual. Si la guardaste y sigue sin salir, casi seguro es que el archivo no
está dentro de la carpeta "static" (comprueba la ruta) o el nombre no
empieza literalmente por "joker".


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

La habilidad nueva aparece automáticamente tanto en la web como en la
terminal, sin tocar nada más.

El modelo decide solo cuándo llamarla, basándose en la descripción que le
escribas. Cuanto más claro digas CUÁNDO debe usarse (no solo qué hace),
mejor acertará.


NOTA SOBRE EL HISTORIAL DE CONVERSACIÓN
-----------------------------------------

Las conversaciones de la web se guardan en la memoria del servidor, así que
se borran al cerrar la ventana donde ejecutaste "python app.py". El botón
"Nueva partida" las borra a mano cuando quieras empezar de cero.
