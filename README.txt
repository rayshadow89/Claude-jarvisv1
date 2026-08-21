READ ME

que hará mi jarvis.v1

Decir el tiempo y la hora de la ubicación pedida, buscar información en internet y resolver problemas básicos de matemáticas.

Cómo ejecutarlo
----------------

1. pip install -r requirements.txt
2. Configura tu clave de la API de Anthropic:
     export ANTHROPIC_API_KEY="sk-ant-..."
   (o usa `ant auth login` en vez de exportar la variable)
3. Opcional, para clima real: export OPENWEATHER_API_KEY="..."
   (clave gratis en https://openweathermap.org/api)
4. python jarvis.py

jarvis.py es el esqueleto: define nuevas tools (funciones Python + esquema
JSON) en TOOLS/TOOL_FUNCTIONS para ir ampliando lo que Jarvis sabe hacer.
