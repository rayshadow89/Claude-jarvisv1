#!/bin/sh
# ---------------------------------------------------------------------------
# revisar-secretos.sh — la revisión completa, a mano
# ---------------------------------------------------------------------------
# El guardián (.githooks/pre-commit) mira lo que estás a punto de subir.
# Esto mira TODO: los ficheros de ahora y los 54 commits de atrás, porque
# borrar una clave de un fichero no la borra del historial.
#
# Se ejecuta desde la carpeta del proyecto. En Windows, con Git Bash
# (clic derecho en la carpeta → "Git Bash Here"):
#
#     sh herramientas/revisar-secretos.sh
#
# No cambia nada. Solo mira y te cuenta. Puedes lanzarlo cuando quieras.
# ---------------------------------------------------------------------------

rojo='\033[0;31m'; verde='\033[0;32m'; amarillo='\033[0;33m'
gris='\033[0;90m'; negrita='\033[1m'; fin='\033[0m'

cd "$(dirname "$0")/.." || exit 1

if [ ! -d .git ]; then
    printf "${rojo}Esto no es la carpeta del proyecto (no hay .git).${fin}\n"
    exit 1
fi

hallazgos=0
avisos=0

titulo() {
    printf "\n${negrita}%s${fin}\n" "$1"
}

bien() {
    printf "  ${verde}✓${fin} %s\n" "$1"
}

mal() {
    printf "  ${rojo}✗ %s${fin}\n" "$1"
    hallazgos=$((hallazgos + 1))
}

ojo() {
    printf "  ${amarillo}!${fin} %s\n" "$1"
    avisos=$((avisos + 1))
}

# Los mismos patrones que el guardián, para que no digan cosas distintas.
# El "20+ caracteres" es a propósito: así los marcadores del README
# ("tu-clave") no cuentan como hallazgo.
PATRONES="
gsk_[A-Za-z0-9]{20,}|una clave de Groq
sk-[A-Za-z0-9_-]{20,}|una clave de OpenAI
sk-ant-[A-Za-z0-9_-]{20,}|una clave de Anthropic
AIza[A-Za-z0-9_-]{30,}|una clave de Google
gh[pousr]_[A-Za-z0-9]{20,}|un token de GitHub
AKIA[A-Z0-9]{16}|una clave de AWS
xox[baprs]-[A-Za-z0-9-]{20,}|un token de Slack
"

printf "\n${negrita}================================================${fin}\n"
printf "${negrita}  JOKER — revisión de secretos${fin}\n"
printf "${negrita}================================================${fin}\n"

# --- 1. Los ficheros de ahora -----------------------------------------------

titulo "1. Los ficheros que hay ahora mismo"

encontrado_algo=0
printf "%s\n" "$PATRONES" | while IFS='|' read -r patron nombre; do
    [ -z "$patron" ] && continue
    hits=$(git grep -n -I -E "$patron" -- . 2>/dev/null | head -5)
    if [ -n "$hits" ]; then
        printf "  ${rojo}✗ hay %s${fin}\n" "$nombre"
        # Solo el fichero y la línea. Nunca el valor: este informe no puede
        # convertirse en otro sitio donde la clave está escrita.
        printf "%s\n" "$hits" | cut -d: -f1,2 | sed 's/^/      en /'
        echo "x" >> "$(git rev-parse --git-dir)/revision-hallazgos"
    fi
done

if [ -f "$(git rev-parse --git-dir)/revision-hallazgos" ]; then
    hallazgos=$((hallazgos + $(wc -l < "$(git rev-parse --git-dir)/revision-hallazgos")))
    rm -f "$(git rev-parse --git-dir)/revision-hallazgos"
else
    bien "ninguna clave en los ficheros del proyecto"
fi

# --- 2. El historial completo ------------------------------------------------

titulo "2. El historial completo (todos los commits, todas las ramas)"

commits=$(git rev-list --all 2>/dev/null)
cuantos=$(printf "%s\n" "$commits" | grep -c . )
printf "  ${gris}revisando %s commits...${fin}\n" "$cuantos"

if [ -z "$commits" ]; then
    ojo "no hay commits todavía"
else
    printf "%s\n" "$PATRONES" | while IFS='|' read -r patron nombre; do
        [ -z "$patron" ] && continue
        hits=$(git grep -n -I -E "$patron" $commits -- . 2>/dev/null | head -5)
        if [ -n "$hits" ]; then
            printf "  ${rojo}✗ hubo %s en algún commit${fin}\n" "$nombre"
            printf "%s\n" "$hits" | cut -d: -f1,2 | sed 's/^/      en /'
            echo "x" >> "$(git rev-parse --git-dir)/revision-hallazgos"
        fi
    done

    if [ -f "$(git rev-parse --git-dir)/revision-hallazgos" ]; then
        hallazgos=$((hallazgos + $(wc -l < "$(git rev-parse --git-dir)/revision-hallazgos")))
        rm -f "$(git rev-parse --git-dir)/revision-hallazgos"
    else
        bien "ninguna clave, en ningún commit, en ninguna rama"
    fi
fi

# --- 3. Ficheros que nunca debieron subirse ----------------------------------

titulo "3. Ficheros con tus datos, alguna vez subidos"

subidos=$(git log --all --pretty=format: --name-only --diff-filter=A 2>/dev/null \
          | sort -u | grep -v '^$')

peligrosos=$(printf "%s\n" "$subidos" | grep -E '(^|/)\.env($|\.)|\.db$|\.sqlite[0-9]?$|joker-copia-.*\.json$|\.bak$|\.backup$' \
             | grep -v '\.env\.example$')

if [ -n "$peligrosos" ]; then
    printf "%s\n" "$peligrosos" | while IFS= read -r f; do
        mal "$f estuvo en el repositorio"
    done
    hallazgos=$((hallazgos + 1))
else
    bien "ni un .env, ni la base de datos, ni una copia de seguridad"
fi

# --- 4. El .gitignore hace su trabajo ----------------------------------------

titulo "4. El .gitignore tapa lo que debe"

for f in .env .env.local joker.db datos.sqlite joker-copia-2026-01-01.json notas.bak app.log; do
    if git check-ignore -q "$f"; then
        bien "$f está tapado"
    else
        mal "$f NO está tapado: si lo creas, git lo vería"
    fi
done

if git check-ignore -q .env.example; then
    mal ".env.example está tapado, y debería subirse (es la plantilla)"
else
    bien ".env.example se sube, como debe (es la plantilla sin valores)"
fi

# --- 5. El guardián está puesto ----------------------------------------------

titulo "5. El guardián está instalado"

ruta=$(git config --get core.hooksPath)
if [ "$ruta" = ".githooks" ] && [ -f .githooks/pre-commit ]; then
    bien "el guardián revisa cada commit"
else
    ojo "el guardián NO está activo. Actívalo con:  git config core.hooksPath .githooks"
fi

# --- 6. Rincones olvidados ---------------------------------------------------

titulo "6. Rincones donde se esconden las cosas"

# Un objeto huérfano es un trozo de un commit deshecho: ya no lo apunta
# nada, pero sigue en el .git hasta que se limpia. No se sube a GitHub con
# un push normal, pero si ahí dentro hubo una clave, sigue en tu disco.
huerfanos=$(git fsck --unreachable --no-progress 2>/dev/null | grep -c 'unreachable blob')
if [ "$huerfanos" -eq 0 ]; then
    bien "no hay objetos huérfanos (trozos de commits deshechos)"
elif [ "$huerfanos" -eq 1 ]; then
    ojo "hay 1 objeto huérfano. Para borrarlo del todo:"
    printf "      ${gris}git reflog expire --expire=now --all && git gc --prune=now${fin}\n"
else
    ojo "hay $huerfanos objetos huérfanos. Para borrarlos del todo:"
    printf "      ${gris}git reflog expire --expire=now --all && git gc --prune=now${fin}\n"
fi

guardados=$(git stash list 2>/dev/null | grep -c .)
if [ "$guardados" -eq 0 ]; then
    bien "no hay nada en el 'stash'"
elif [ "$guardados" -eq 1 ]; then
    ojo "hay 1 cosa guardada en el 'stash' (git stash list)"
else
    ojo "hay $guardados cosas guardadas en el 'stash' (git stash list)"
fi

# --- Veredicto ---------------------------------------------------------------

printf "\n${negrita}================================================${fin}\n"

if [ "$hallazgos" -gt 0 ]; then
    printf "${rojo}${negrita}  $hallazgos COSAS QUE ARREGLAR${fin}\n\n"
    printf "  Si ha salido una clave, el orden es este y no otro:\n\n"
    printf "  ${negrita}1.${fin} Ve a ${gris}https://console.groq.com/keys${fin} y revócala.\n"
    printf "     Saca otra y ponla en tu .env.\n"
    printf "     ${gris}Esto es el 95%% del trabajo: una clave revocada no vale${fin}\n"
    printf "     ${gris}nada aunque esté en mil sitios.${fin}\n\n"
    printf "  ${negrita}2.${fin} Solo después, y si te apetece, limpia el historial.\n"
    printf "     Mira la sección SEGURIDAD del README.txt.\n\n"
    printf "  ${negrita}Nunca al revés.${fin} Limpiar el historial sin revocar deja la\n"
    printf "  clave viva en los caches de GitHub y en Google.\n\n"
    exit 1
fi

if [ "$avisos" -gt 0 ]; then
    printf "${amarillo}${negrita}  LIMPIO, con $avisos aviso(s) de arriba${fin}\n\n"
    exit 0
fi

printf "${verde}${negrita}  TODO LIMPIO${fin}\n"
printf "  ${gris}Ninguna clave, ni ahora ni en ningún commit de atrás.${fin}\n\n"
exit 0
