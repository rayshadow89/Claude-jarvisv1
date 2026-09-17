JOKER
"La última carta del mazo"


QUÉ ES
------

Un asistente personal con IA que dice la hora y el clima de cualquier
lugar del mundo, busca información, cuenta lo que ha pasado hoy y resuelve
problemas de matemáticas. Se llamó "Jarvis" al principio; ahora es JOKER,
con página web propia en burdeos y negro.

Y ya no es solo un chat: tiene cuatro salas, y cada una lleva su palo de la
baraja para que sepas dónde estás antes de leer la palabra.

  ♥  JOKER        el chat con la IA                 ->  /
  ♠  J0KER GYM    entrenamiento y nutrición         ->  /gym
  ♦  J0KER GASTOS tu dinero, repartido              ->  /gastos
  ♣  INVERSIONES  de momento, solo el escenario     ->  /inversiones

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

9. El clima dejó de necesitar clave. Antes usaba OpenWeatherMap, que
   pedía registrarse y sacar una OPENWEATHER_API_KEY, y como nunca se
   configuró, JOKER respondía que le faltaba esa clave cada vez que se
   le preguntaba por el tiempo. Ahora usa Open-Meteo (el mismo servicio
   gratuito que ya usábamos para buscar ciudades), así que funciona sin
   configurar nada.

10. Se añadió el selector de potencia (Bajo/Medio/Alto/Extra/J0KER) con
    el modo J0KER: pantalla iluminada, degradado burdeos arriba, y los
    palos de los laterales parándose, temblando y arrancando los dos
    hacia arriba. Por ahora es solo estético.

11. Se creó J0KER GYM (gym.py + /gym): el primer módulo de verdad más
    allá del chat. Calcula calorías y macros, genera la rutina semanal
    esquivando lesiones, propone menú y estima plazos realistas. Los
    datos personales se guardan en una base local que no se sube.

12. J0KER GYM, segunda vuelta: gráfica de peso (lo registrado frente a
    lo previsto), rutina editable a mano o generada por JOKER,
    limitaciones que se pueden escribir en lenguaje normal, lista de
    ejercicios a evitar, recomendaciones que citan tus cifras concretas
    en vez de consejos genéricos, y los números movidos a un apartado
    aparte de "Datos adicionales".

13. J0KER GYM, tercera vuelta. Ocho arreglos pedidos tras usarlo:

    - La trayectoria prevista ya no parece de adorno. Si no aparece es
      porque falta el peso objetivo, y ahora la página lo DICE en vez de
      callarse. Y cuando aparece, se puede acercar la vista ("Mis
      registros" / "3 meses" / "Todo el plan"): antes cuatro días de
      datos ocupaban el 2% del ancho frente a seis meses de proyección,
      así que no se veía nada.
    - El catálogo pasó de 41 a 115 ejercicios, y los grupos musculares
      de 6 a 12: antes "brazo" y "pierna" lo mezclaban todo; ahora hay
      bíceps, tríceps, antebrazo, cuádriceps, femoral, glúteo y gemelo
      por separado.
    - Se puede añadir un ejercicio que no esté en la lista, escribiendo
      su nombre y eligiendo de qué grupo es.
    - El título de cada día se calcula con los ejercicios que tiene de
      verdad. Antes ponía "Lunes: día de pecho" aunque le cambiaras todo
      por sentadillas.
    - Casilla de "día completado": al marcarla, el día se pone morado
      (el mismo burdeos de la casa girado de tono). Se guarda por semana,
      así que cada lunes empieza limpia sola.
    - Las comidas rotan: hay doce menús que cuadran con tus números y
      cada día toca uno. Como no son siete, el menú de un lunes no es el
      del lunes siguiente. Y hay un botón para pasar al siguiente.
    - Los palos de la baraja salen en TODAS las páginas, no solo en la
      del chat (templates/_palos.html).
    - Los siete días de la semana caben de lado a lado de la pantalla.

    Y de paso, dos cosas que se vieron por el camino: la alternativa que
    se enseña ("cambia por X") ahora se comprueba contra tus lesiones
    (a quien le dolía la rodilla le proponía cambiar la prensa por una
    sentadilla goblet, que es justo lo que no debe hacer), y los avisos
    de "en lugar de..." se limitan a dos por sesión, que con una rodilla
    tocada salían en casi todas las líneas y tapaban lo importante.


14. J0KER GASTOS (gastos.py + /gastos): la segunda sala de verdad. Metes
    lo que ingresas, eliges cómo repartirlo (50/30/20, 70/20/10, los seis
    frascos, 80/20 o 40/30/20/10), apuntas lo que gastas cada día y te
    avisa con TUS cifras cuando el mes se va de las manos. Lleva simulador
    de deudas comparando avalancha contra bola de nieve, y dos gráficas:
    cómo va tu dinero durante el mes y un círculo con tu reparto, con los
    porcentajes editables (si quieres ahorrar el 99%, te deja).

15. Una tool nueva, buscar_noticias: titulares de actualidad de medios de
    verdad, con su fecha y su medio. Sale del RSS de Google Noticias, que
    es gratis y no pide clave. Wikipedia seguía siendo Wikipedia: sabe
    quién fue Tesla, no sabe qué pasó ayer.

16. Repaso de aspecto en toda la web: un CSS compartido (static/joker.css)
    en vez de la paleta copiada en cada plantilla, botones con barrido de
    luz al pasar por encima y hundimiento al pulsar, cada apartado con su
    palo, cada día del gimnasio con su índice de carta en la esquina, los
    días de descanso con el dorso de la baraja, los números grandes
    contando hacia arriba, y un Joker flotante en todas las salas que te
    devuelve al chat de un toque. Más un micrófono en el chat que todavía
    NO graba: está puesto para cuando le toque, y al pulsarlo lo dice él
    mismo en vez de quedarse mudo.

17. La sala de inversiones, de momento vacía a propósito. Lo que sí está
    terminado es cómo se entra: la web entera vira de burdeos a azul, el
    halo de luz se va de arriba y aparece abajo, y los palos de los
    laterales se paran y se tumban en dos franjas horizontales. Entre esas
    dos franjas queda el marco donde irán las cotizaciones. Mientras
    tanto, corren minigráficas de ejemplo en sentido contrario al de los
    palos.


FICHEROS DEL PROYECTO
----------------------

  app.py            El servidor de la página web. Es lo que ejecutas para
                    usar JOKER desde el navegador.
  templates/        El diseño de las páginas:
                      index.html        el chat
                      gym.html          J0KER GYM
                      gastos.html       J0KER GASTOS
                      inversiones.html  la sala azul
                      _palos.html       los carruseles de palos
                      _salas.html       la navegación entre salas
                      _joker_boton.html el Joker flotante
  static/           Imágenes. Aquí está joker.jpg (la mascota).

  joker.py          El asistente en versión terminal. Contiene el "motor"
                    (el loop que habla con la IA), que la web reutiliza.
  tools.py          Las habilidades de JOKER: hora, clima, matemáticas,
                    búsqueda y consultar el plan del gimnasio.
                    No depende de ningún proveedor de IA.
  gym.py            Todo el cálculo de J0KER GYM.
  gastos.py         Todo el cálculo de J0KER GASTOS: reglas de reparto,
                    avisos y el simulador de deudas.
  joker.db          Tus datos del gimnasio Y de tus cuentas. Local, NO se
                    sube a GitHub.

  static/joker.css  El estilo compartido por las cuatro salas: la paleta,
                    la cabecera, las tarjetas, los botones y los campos.
  static/gastos-graficas.js
                    Las dos gráficas de la sala de gastos, hechas a mano
                    con SVG (sin librerías).

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
     ¿Qué tiempo hace en Madrid?
     Cuánto es (45 * 8) / 3
     Busca información sobre Nikola Tesla


LA IMAGEN DE LA MASCOTA
-------------------------

Ya está puesta (static/joker.jpg). Si algún día quieres cambiarla, solo
tiene que EMPEZAR por "joker" (mayúsculas o minúsculas da igual) y ser
.png, .jpg, .jpeg, .webp o .gif — el nombre exacto no importa. Si no
hay ninguna, sale un 🃏 en su lugar y todo lo demás sigue funcionando.


J0KER GYM
-----------

Apartado de entrenamiento, en http://127.0.0.1:5000/gym (o pulsando
"J0KER GYM" arriba a la derecha en el chat).

Metes tus datos una vez y te calcula:

  TU META
    Cuánto tardas en llegar, a un ritmo sostenible. Si la meta no es sana
    o no es alcanzable, te lo dice y te propone otra.

  TU PESO (la gráfica)
    Apuntas tu peso cada día y ves tu evolución real frente a la
    trayectoria prevista hasta tu meta. Eje X el tiempo, eje Y los kilos.
    Pasando el ratón te dice el dato de cada día.
    Tu peso va en burdeos y sólido; lo previsto en azul y discontinuo
    (los colores están comprobados para que se distingan también con
    daltonismo, y además una línea es continua y la otra no).

    LA TRAYECTORIA PREVISTA sale de tu peso objetivo. Si no has puesto
    ninguno, no hay línea que dibujar, y la gráfica te lo dice ahí mismo
    en vez de dejarte pensando si está rota.

    Y como el plan dura meses pero tú llevas unos días apuntando, hay
    tres botones para elegir qué ves:
      Mis registros -> tu tramo, ampliado. Es donde se compara de verdad
                       si vas por encima o por debajo de lo previsto.
      3 meses       -> el trimestre.
      Todo el plan  -> de hoy hasta la meta, con la línea del peso
                       objetivo marcada.

  LA SEMANA
    Los 7 días, uno al lado del otro, con sus ejercicios, series,
    repeticiones y descansos. El nombre de cada día (por ejemplo "Pecho,
    hombro y tríceps") NO está escrito a mano: se calcula mirando qué
    músculos tocan los ejercicios que hay ese día, así que si cambias el
    contenido, el título cambia contigo.

    PUEDES EDITARLA: el botón "Editar mi rutina" te deja cambiar cada
    ejercicio por otro, quitar los que no quieras, añadir más, o
    convertir un día de descanso en día de entreno. Al editar, el
    desplegable te avisa con ⚠ si un ejercicio choca con tus lesiones.
    Hay 115 ejercicios repartidos en 12 grupos musculares, y si aun así
    falta el tuyo, "+ Escribir un ejercicio mío" te deja ponerlo con su
    nombre y su grupo (hace falta el grupo: sin él, el título del día no
    sabría contarlo).
    Si prefieres no complicarte, "Que la haga JOKER" vuelve a la
    calculada automáticamente.

    DÍA COMPLETADO: cada día de entreno lleva una casilla. Al marcarla el
    día se pone morado. Se guarda por semana, así que el lunes empieza
    limpia sola sin que tengas que borrar nada. JOKER también lo sabe: si
    le preguntas por el chat, te dice qué días llevas y cuáles te quedan.

  OJO CON ESTOS EJERCICIOS
    La lista concreta de lo que debes evitar según tus lesiones, con por
    cuál cambiar cada uno. El recambio que te propone está comprobado
    contra TUS lesiones, no es la alternativa genérica del catálogo.

  MENÚ DE HOY
    Desayuno, comida, cena y snacks que cuadran con tus calorías.
    NO SE QUEDAN AHÍ PARADAS: hay doce menús distintos que cuadran con
    tus números, y cada día toca uno. Como no son siete, el menú de un
    lunes no es el del lunes siguiente. Si hoy no te apetece lo que ha
    salido, "Enséñame otro menú" pasa al siguiente.

  RECOMENDACIONES
    Centradas en TU perfil: citan tus calorías, tus gramos de proteína,
    tus días de entreno y los ejercicios concretos que se te han
    cambiado. Nada de consejos de manual.

  DATOS ADICIONALES
    Al final: IMC, metabolismo basal, mantenimiento, macros, agua y el
    rango de peso saludable para tu altura.


J0KER GASTOS
--------------

En http://127.0.0.1:5000/gastos (o pulsando ♦ GASTOS arriba).

Dices cuánto te entra al mes, eliges cómo repartirlo, y a partir de ahí
apuntas lo que vas gastando. Lo que te da:

  EL MES
    Cada parte de tu regla con lo que le toca y lo que llevas usado. La de
    ahorro no se apunta: se calcula, porque el ahorro es lo que queda.

  CÓMO VA TU DINERO
    Una línea con lo que te va quedando día a día, frente al ritmo que
    deberías llevar para acabar el mes con tu ahorro intacto. Y un círculo
    con tu reparto: el anillo de fuera es lo que le toca a cada parte, el de
    dentro lo que llevas. Los colores están comprobados para que se
    distingan también con daltonismo, y la leyenda lleva nombre y cifra, así
    que nunca dependes solo del color.

  TUS PORCENTAJES
    Los puedes mover a tu gusto. Lo único que se te pide es que sumen 100,
    porque no se puede repartir más dinero del que entra. ¿Quieres ahorrar
    el 99% y vivir con el 1%? Adelante: te dice cuánto sería al mes y al
    año, y no te lo discute.

  APUNTAR UN GASTO
    Día, categoría, qué era e importe. Trece categorías, ni una más: con
    treinta, elegir cuesta más que el propio gasto y acabas no apuntando.

  DEUDAS
    Cada deuda con su saldo, su interés y lo que pagas al mes. Te dice
    cuánto te cuesta tenerla ahí quieta, y compara los dos métodos que
    funcionan:
      Avalancha      -> primero la de más interés. La que menos dinero cuesta.
      Bola de nieve  -> primero la más pequeña. Cuesta algo más, pero tachas
                        una antes, y eso es lo que hace que la gente siga.
    Si pagas solo los mínimos te lo dice claro: los dos métodos dan
    exactamente lo mismo, porque no hay dinero suelto que dirigir. Y si lo
    que pagas no cubre ni los intereses, te avisa de que la deuda CRECE y de
    que ningún método arregla eso.

  LO QUE DEBERÍAS SABER
    Los avisos. Con cifras tuyas o no se dicen: no vas a leer "controla tus
    gastos", vas a leer cuánto te has pasado, en qué, y qué le cuesta eso a
    tu ahorro. El ritmo de gasto se mide solo sobre lo variable, porque el
    alquiler del día 1 no se repite y dividirlo entre los días daba sustos
    que no eran de verdad.

AVISO: esto es una hoja de cálculo con buenas intenciones, no asesoría
financiera. Los intereses se calculan de forma simplificada (mensual sobre
el saldo) y tu banco puede hacerlo distinto.


INVERSIONES: LO QUE HAY Y LO QUE NO
-------------------------------------

En /inversiones. Ahora mismo NO trae ni un dato real, y es a propósito: es
el sitio preparado para cuando lo traiga.

Lo que sí está terminado es la entrada. Al abrirla, la web entera vira de
burdeos a azul (no es otra hoja de estilos: es la misma, con el color de
acento apuntando a otro sitio), el halo de luz se va de arriba y aparece
abajo, y los palos de los laterales se paran y se tumban en dos franjas
horizontales. Entre esas dos franjas queda el marco donde irán las
cotizaciones.

Las minigráficas que ves moverse son inventadas, y no lo disimulan: se
llaman PICA, CORAZÓN, COMODÍN y demás, no como empresas de verdad, para que
a nadie se le ocurra leerlas como una cotización.


LAS LIMITACIONES, SIN SABER CUÁL MARCAR
-----------------------------------------

Puedes marcar las casillas a mano, o escribirlo con tus palabras en el
recuadro de abajo:

  "me duele la rodilla al agacharme y entreno en casa sin material"

Pulsas "Que lo interprete JOKER" y te marca las casillas que
correspondan, diciéndote cuáles ha marcado para que lo revises.

A partir de ahí, la rutina esquiva sola los ejercicios que no te
convienen. Está comprobado con 2240 combinaciones distintas de
limitaciones, días y objetivos: en ninguna se cuela un ejercicio
contraindicado, ni como ejercicio ni como alternativa propuesta.


JOKER TAMBIÉN LO CONOCE
-------------------------

Puedes preguntarle por el chat "¿qué me toca entrenar hoy?", "¿cuántas
calorías tengo que comer?", "¿cuánto llevo gastado este mes?" o "¿puedo
permitirme esto?" y te lo lee de tu plan y de tus cuentas, sin inventarse
nada.


DÓNDE SE GUARDAN TUS DATOS
----------------------------

En joker.db, un fichero local en tu carpeta del proyecto: tanto lo del
gimnasio (peso, rutina, días hechos) como tus cuentas (sueldo, gastos,
deudas). NO se sube a GitHub (está en el .gitignore). Son tuyos y se quedan
en tu ordenador: lo de salud y lo de dinero son justo las dos cosas que no
tienen por qué salir de ahí.

AVISO: los cálculos son orientativos, con fórmulas estándar (Mifflin-St
Jeor). No son consejo médico.

Nota sobre los somatotipos: la clasificación ectomorfo/mesomorfo/endomorfo
es de los años 40 y la ciencia moderna no la respalda como predictor. Está
incluida porque se usa mucho, pero solo ajusta un ±5%. Lo que manda de
verdad es la fórmula de gasto calórico.


EL SELECTOR DE POTENCIA
-------------------------

Debajo de la caja de escribir hay cinco niveles: Bajo, Medio, Alto, Extra
y J0KER. De momento SOLO cambian el aspecto de la página, no afectan a
cómo responde la IA — están puestos para ver cómo queda.

El nivel J0KER enciende la sala: el fondo se ilumina, la parte de arriba
de la ventana se baña en un degradado burdeos, y los palos de los
laterales dejan de ir cada uno por su lado — se paran en seco, tiemblan
un instante, y luego suben los dos juntos y más despacio.

El nivel elegido se recuerda entre visitas.

CUANDO QUIERAS QUE HAGA ALGO DE VERDAD (memoria, modelo, etc.), el nivel
está guardado en la variable `nivelActual` dentro del script de
templates/index.html. Basta con mandarlo a /api/chat junto al mensaje y
usarlo en app.py. Está comentado en el propio código.


EL MICRÓFONO DEL CHAT
-----------------------

Está al lado del botón de enviar, y TODAVÍA NO GRABA. Es solo el sitio
guardado para cuando toque conectarlo.

Se ve apagado a propósito, y al pulsarlo te lo dice él mismo en vez de
quedarse mudo: un botón que promete algo que no hace es peor que no
tenerlo. Cuando llegue su turno, el enganche va en el manejador del clic
de #microfono en templates/index.html, con la API de reconocimiento de voz
del navegador.


EL CLIMA
--------

JOKER te dice el tiempo y la temperatura de cualquier ciudad, pueblo o
país del mundo. No hace falta configurar nada: usa Open-Meteo, que es
gratis y no pide ninguna clave.

Pruébalo con cosas como:

  ¿Qué tiempo hace en Madrid?
  ¿Cuántos grados hace en Tokio?
  ¿Está lloviendo en Londres?
  ¿Hace frío en Buenos Aires?

Te devuelve el estado del cielo, la temperatura, la sensación térmica,
la humedad y el viento. Si quieres los grados en Fahrenheit, solo tienes
que pedírselo.


LO QUE JOKER SABE DEL MUNDO
-----------------------------

Hay DOS tools de buscar, y cada una sirve para una cosa distinta:

  search_web (Wikipedia)
    Para lo que ya es historia: quién fue Nikola Tesla, qué es la fotosíntesis,
    dónde está Katmandú. Es una enciclopedia, así que no sabe qué pasó ayer.

  buscar_noticias (RSS de Google Noticias)
    Para lo de AHORA: qué ha pasado hoy, cómo va un tema en marcha, quién ha
    ganado qué. Devuelve titulares de medios de verdad con su medio y su
    fecha, en español de España.

    Pídeselo con normalidad: "¿qué ha pasado hoy?", "ponme al día de los
    incendios", "¿cómo va el precio de la luz?".

    Lo que trae son TITULARES, no los artículos. JOKER tiene orden de contar
    lo que dicen los titulares citando el medio, y de NO rellenar con
    detalles del artículo, porque no lo ha leído. Es peor un resumen
    inventado que un titular escueto.

Las dos son gratis y no piden ninguna clave, que es la condición de todo
este proyecto. Si algún día quieres un buscador de verdad (páginas enteras,
no titulares), se puede añadir con Tavily o Serper: tienen capa gratuita,
pero piden registro.


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



JOKER IDEAS

Meterle copyright para que nadie me la robe.
Meterle Terminos y condiciones 
Poder meterle una combinación de teclas en mi pc, que haga que se despierte, y se "propague" en mi ordenador
Que me de las ultimas informaciones de las inversiones mias, de bolsa, y que en caso de un posible desplome que me avise con notoficaciones al móvil (no se si quiera si puedo hacer esto)
Que tenga una opción para que pueda decirle en que empresas tengo metido mi dinero, cuanto, y que (obviamente) esta información la encripte y la guarde, pudiendo solo acceder a ella al que le pertenece el portátil
Que tenga un apartado aparte para mi entrenamiento diario, que se llame "J0KER GYM", que sepa mi rutina, que me de recomendaciones, comidas con + o - calorías para todos los perfiles de entrenamiento.
También una opción en la que me ayude con mis gastos (esto ams que una ia parecería una pagina web/app con una ia que te arregle todo, me gusta la idea, me la guardo)
Wishlist, la cual se actualize cada 24 horas, para ver si hay una promo de dicha wishlist, y conseguirla.
 -------

CAMBIO DE IDEA

Joker, es una ia, pero todo lo que he dicho quiero convertirlo en una APP, en la que este todo metido junto
------

POR AHORA
--------

Seguimos con la pagina web, mas adelante haremos un cambio a PWA para que no haya tantos errores mientras seguimos con el proyecto, empezamos con JOKER GYM, que nos dará rutinas según el dia de la semana, comidas recomendadas según lo que busca el cliente (ganar peso, perderlo, ganar musculo...) y basarse en si es ectomorfo, mesomorfo... .También se basa en altura y peso. Cuanto tiempo tiene que rendir para llegar a sus metas y ajustalas según las necesidades y limitaciones que tenga (por ejemplo trabajo, tiempo libre, algún inconveniente, etc) 
