/* =========================================================================
   LA MESA — el resumen y los ajustes
   ========================================================================= */

const $ = (id) => document.getElementById(id);

function crearSVG(tipo, atributos) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tipo);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
  return el;
}

function pintarError(caja, texto) {
  caja.innerHTML = '';
  if (!texto) return;
  const d = document.createElement('div');
  d.className = 'error';
  d.textContent = texto;
  caja.appendChild(d);
}

function pintarOk(caja, texto) {
  caja.innerHTML = '';
  if (!texto) return;
  const d = document.createElement('div');
  d.className = 'ok';
  d.textContent = texto;
  caja.appendChild(d);
}

// ---------------------------------------------------------------------------
// La mano de cartas
// ---------------------------------------------------------------------------

function cartaSala(t) {
  const a = document.createElement('a');
  a.className = 'carta-sala'
    + (t.estrenada ? '' : ' nueva')
    + (t.bloqueada ? ' cerrada' : '');
  a.href = t.enlace;

  const indice = document.createElement('span');
  indice.className = 'indice';
  indice.setAttribute('aria-hidden', 'true');
  indice.textContent = t.palo;

  const nombre = document.createElement('div');
  nombre.className = 'nombre';
  const palito = document.createElement('span');
  palito.className = 'palito';
  palito.setAttribute('aria-hidden', 'true');
  palito.textContent = t.palo;
  nombre.append(palito, document.createTextNode(t.titulo));

  a.append(indice, nombre);

  if (t.bloqueada) {
    const candado = document.createElement('div');
    candado.className = 'candadito-carta';
    candado.setAttribute('aria-hidden', 'true');
    candado.textContent = '\u{1F512}';
    a.appendChild(candado);
  } else if (t.cifra) {
    const cifra = document.createElement('div');
    cifra.className = 'cifra' + (t.signo ? ' ' + t.signo : '');
    cifra.textContent = t.cifra;
    const pie = document.createElement('div');
    pie.className = 'cifra-pie';
    pie.textContent = t.cifra_pie || '';
    a.append(cifra, pie);
  }

  if (t.titular) {
    const tit = document.createElement('div');
    tit.className = 'titular';
    tit.textContent = t.titular;
    a.appendChild(tit);
  }
  if (t.detalle) {
    const det = document.createElement('div');
    det.className = 'detalle';
    det.textContent = t.detalle;
    a.appendChild(det);
  }

  if (typeof t.progreso === 'number') {
    const barra = document.createElement('div');
    barra.className = 'barra';
    const relleno = document.createElement('i');
    relleno.style.width = '0%';
    barra.appendChild(relleno);
    a.appendChild(barra);
    requestAnimationFrame(() => { relleno.style.width = t.progreso + '%'; });
  }

  if (t.extra) {
    const ex = document.createElement('div');
    ex.className = 'extra';
    ex.textContent = t.extra;
    a.appendChild(ex);
  }
  if (t.invitacion) {
    const inv = document.createElement('div');
    inv.className = 'llamada';
    inv.textContent = t.invitacion + '  →';
    a.appendChild(inv);
  }
  return a;
}

async function pintarMesa() {
  let datos;
  try {
    datos = await (await fetch('/api/mesa')).json();
  } catch (e) {
    return;
  }

  $('saludo').textContent = datos.saludo + '.';
  $('dia').textContent = new Date(datos.fecha + 'T12:00:00')
    .toLocaleDateString('es-ES', {weekday: 'long', day: 'numeric', month: 'long'});

  const mano = $('mano');
  mano.innerHTML = '';
  for (const t of datos.tarjetas) mano.appendChild(cartaSala(t));
}

// ---------------------------------------------------------------------------
// Los ajustes que se pliegan
// ---------------------------------------------------------------------------

for (const cabeza of document.querySelectorAll('.ajuste-cabeza')) {
  cabeza.addEventListener('click', () => {
    document.getElementById(cabeza.dataset.abre).classList.toggle('abierto');
  });
}

// ---------------------------------------------------------------------------
// Copia de seguridad
// ---------------------------------------------------------------------------

$('descargar').addEventListener('click', () => {
  // Una descarga normal: el servidor ya manda el fichero con su nombre
  window.location.href = '/api/copia/exportar';
});

let copiaTraida = null;

$('soltar').addEventListener('click', () => $('fichero').click());
$('fichero').addEventListener('change', (e) => {
  if (e.target.files[0]) leerCopia(e.target.files[0]);
});

for (const evento of ['dragenter', 'dragover']) {
  $('soltar').addEventListener(evento, (e) => {
    e.preventDefault();
    $('soltar').classList.add('encima');
  });
}
for (const evento of ['dragleave', 'drop']) {
  $('soltar').addEventListener(evento, (e) => {
    e.preventDefault();
    $('soltar').classList.remove('encima');
  });
}
$('soltar').addEventListener('drop', (e) => {
  const f = e.dataTransfer.files[0];
  if (f) leerCopia(f);
});

async function leerCopia(fichero) {
  pintarError($('error-copia'), '');
  $('traida').innerHTML = '';
  copiaTraida = null;

  if (fichero.size > 40 * 1024 * 1024) {
    pintarError($('error-copia'), 'Ese fichero pesa demasiado para ser una copia de JOKER.');
    return;
  }

  let texto;
  try {
    texto = await fichero.text();
  } catch (e) {
    pintarError($('error-copia'), 'No he podido leer ese fichero.');
    return;
  }

  let datos;
  try {
    datos = JSON.parse(texto);
  } catch (e) {
    pintarError($('error-copia'), 'Ese fichero no es un JSON válido. ¿Seguro que es '
                                + 'la copia que descargaste de JOKER?');
    return;
  }

  const r = await fetch('/api/copia/mirar', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(datos),
  });
  const resp = await r.json();
  if (resp.error) {
    pintarError($('error-copia'), resp.error);
    return;
  }

  copiaTraida = datos;
  pintarTraida(resp.resumen, fichero.name);
}

function pintarTraida(res, nombre) {
  const caja = $('traida');
  caja.innerHTML = '';

  const div = document.createElement('div');
  div.className = 'traida';

  const tit = document.createElement('div');
  tit.style.color = 'var(--texto)';
  const cuando = res.fecha !== 'desconocida'
    ? new Date(res.fecha).toLocaleString('es-ES',
        {day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'})
    : 'fecha desconocida';
  tit.textContent = `${nombre} — copia del ${cuando}`;

  const lista = document.createElement('ul');
  const cosas = [
    [res.hay_gym, 'Perfil del gimnasio' + (res.pesos ? ` y ${res.pesos} pesos apuntados` : '')],
    [res.hay_gastos, `Cuentas: ${res.gastos} gastos y ${res.deudas} deudas`],
    [res.notas, `${res.notas} ${res.notas === 1 ? 'nota' : 'notas'} en la libreta`],
    [res.hay_cartera, 'Cartera de inversiones (cifrada: pedirá su contraseña)'],
    [res.hay_pin, 'El PIN de entrada que tenía esa copia'],
  ];
  for (const [hay, texto] of cosas) {
    if (!hay) continue;
    const li = document.createElement('li');
    li.textContent = '✓  ' + texto;
    lista.appendChild(li);
  }
  if (!lista.children.length) {
    const li = document.createElement('li');
    li.style.color = 'var(--texto-suave)';
    li.textContent = 'La copia está vacía.';
    lista.appendChild(li);
  }

  const aviso = document.createElement('div');
  aviso.style.cssText = 'margin-top:12px;color:var(--acento-texto);font-size:0.8rem';
  aviso.textContent = 'Al restaurar se pierde lo que tengas ahora en JOKER.';

  const botones = document.createElement('div');
  botones.className = 'fila-botones';
  botones.style.marginTop = '14px';

  const si = document.createElement('button');
  si.className = 'boton';
  si.textContent = 'Restaurar esta copia';
  si.addEventListener('click', restaurar);

  const no = document.createElement('button');
  no.className = 'boton secundario';
  no.textContent = 'Cancelar';
  no.addEventListener('click', () => {
    copiaTraida = null;
    caja.innerHTML = '';
    $('fichero').value = '';
  });

  botones.append(si, no);
  div.append(tit, lista, aviso, botones);
  caja.appendChild(div);
}

async function restaurar() {
  if (!copiaTraida) return;
  if (!window.confirm('Esto borra todo lo que tienes ahora en JOKER y lo cambia '
                    + 'por lo de la copia.\n\n¿Seguro?')) return;

  pintarError($('error-copia'), '');
  const r = await fetch('/api/copia/restaurar', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(copiaTraida),
  });
  const datos = await r.json();
  if (datos.error) {
    pintarError($('error-copia'), datos.error);
    return;
  }
  window.alert('Copia restaurada. JOKER se va a recargar: si esa copia traía PIN '
             + 'o cartera, te los volverá a pedir.');
  window.location.reload();
}

// ---------------------------------------------------------------------------
// El PIN
// ---------------------------------------------------------------------------

let hayPin = false;

async function estadoPin() {
  try {
    const datos = await (await fetch('/api/acceso/estado')).json();
    hayPin = datos.hay_pin;
  } catch (e) {
    return;
  }

  $('estado-pin').textContent = hayPin
    ? 'Puesto. JOKER pide el PIN al abrirse.'
    : 'Sin poner. Cualquiera que abra el portátil entra.';
  $('campo-pin-actual').classList.toggle('oculto', !hayPin);
  $('quitar-pin').classList.toggle('oculto', !hayPin);
  $('salir').classList.toggle('oculto', !hayPin);
  $('guardar-pin').textContent = hayPin ? 'Cambiar el PIN' : 'Poner el PIN';
}

$('guardar-pin').addEventListener('click', async () => {
  pintarError($('error-pin'), '');
  pintarOk($('ok-pin'), '');

  const boton = $('guardar-pin');
  boton.disabled = true;
  try {
    const r = await fetch('/api/acceso/poner', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        actual: $('pin-actual').value,
        pin: $('pin-nuevo').value,
        repetido: $('pin-repetido').value,
      }),
    });
    const datos = await r.json();
    if (datos.error) { pintarError($('error-pin'), datos.error); return; }

    for (const id of ['pin-actual', 'pin-nuevo', 'pin-repetido']) $(id).value = '';
    pintarOk($('ok-pin'), 'Listo. A partir de ahora JOKER pedirá este PIN al abrirse.');
    estadoPin();
  } finally {
    boton.disabled = false;
  }
});

$('quitar-pin').addEventListener('click', async () => {
  pintarError($('error-pin'), '');
  pintarOk($('ok-pin'), '');

  const pin = window.prompt('Escribe tu PIN actual para quitarlo:');
  if (pin === null) return;

  const r = await fetch('/api/acceso/quitar', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pin}),
  });
  const datos = await r.json();
  if (datos.error) { pintarError($('error-pin'), datos.error); return; }
  pintarOk($('ok-pin'), 'PIN quitado. JOKER vuelve a abrirse sin pedir nada.');
  estadoPin();
});

$('salir').addEventListener('click', async () => {
  await fetch('/api/acceso/salir', {method: 'POST'});
  window.location.href = '/bloqueo';
});

pintarMesa();
estadoPin();
