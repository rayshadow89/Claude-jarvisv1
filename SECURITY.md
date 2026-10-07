# Seguridad

## Si encuentras un problema

Abre una [incidencia](https://github.com/rayshadow89/joker-asistente/issues) o
escríbeme por [GitHub](https://github.com/rayshadow89). Contesto.

Si lo que has encontrado es **una clave filtrada** (mía o de cualquiera), no la
pegues en la incidencia: dime en qué fichero y en qué línea está, y nada más. Un
aviso no debería ser otro sitio donde la clave queda escrita.

## Qué entra y qué no

JOKER es un proyecto personal que corre en `127.0.0.1` en el ordenador de su
dueño. No es un servicio, no hay servidor público, no hay usuarios ajenos y no
hay datos de terceros. Con eso en la mano:

**Interesa saberlo:**

- Una forma de leer la cartera de inversiones sin la contraseña.
- Una forma de saltarse el PIN de entrada que no sea tener el fichero
  `joker.db` (eso ya está documentado, ver abajo).
- Un fallo que haga que una clave de API, un dato personal o una copia de
  seguridad acabe en el repositorio, en un registro o en una petición de red.
- Inyección de SQL, recorrido de rutas o ejecución de código.

**No es un fallo, es el diseño, y está escrito en el README:**

- **El PIN no cifra nada.** Es una cortina para que quien abra el portátil no
  vea de entrada tu peso y tus deudas. Quien tenga el fichero `joker.db` lo abre
  con cualquier visor de SQLite y lee el gimnasio, los gastos y las notas sin
  PIN ninguno. Lo único cifrado de verdad es la cartera de inversiones.
- **No hay HTTPS.** Escucha en `127.0.0.1`: el tráfico no sale de la máquina.
- **No hay límite de intentos ni gestión de sesiones robusta.** No está pensado
  para exponerse a una red. Si lo abres con `host="0.0.0.0"`, nada de esto
  aguanta, y el README lo advierte.
- **Las copias de seguridad van en claro** (salvo la cartera, que viaja
  cifrada). Es deliberado y está avisado al descargarlas.

## Lo que hay puesto

- **`.gitignore`** — tapa el `.env`, la base de datos y las copias de seguridad.
- **`.githooks/pre-commit`** — para el commit si ve una clave o un fichero con
  datos personales. Se activa con `git config core.hooksPath .githooks`.
- **`herramientas/revisar-secretos.sh`** — la misma revisión sobre todo el
  historial de git, lanzable a mano.
- **Escaneo de secretos de GitHub**, como segunda red por debajo del hook.
- **Cartera cifrada** con AES-256-GCM y clave derivada por scrypt.
- **PIN** guardado solo como huella scrypt, comparado con `hmac.compare_digest`.

El detalle completo está en la sección **SEGURIDAD** del
[README.txt](README.txt).

## Versiones

Esto no se distribuye en versiones: lo que vale es la rama `main`. No hay
parches para etiquetas anteriores.
