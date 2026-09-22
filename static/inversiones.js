/* =========================================================================
   J0KER INVERSIONES — la parte del navegador
   =========================================================================

   Dos reglas que se siguen en todo el fichero:

   1. NADA DE DATOS INVENTADOS. Si no se puede saber un precio, se dice. En
      una página que habla del dinero de alguien, una cifra de adorno es
      peor que un hueco.

   2. POCO A LA VISTA, TODO A UN CLIC. Cada posición enseña tres cosas:
      dónde está, cuánto vale y cómo va. Lo demás (cuántas participaciones,
      a qué precio, la gráfica, los botones) vive detrás de la flechita.
   ========================================================================= */

const $ = (id) => document.getElementById(id);

let estado = null;        // { existe, abierta, ... }
let cartera = null;       // la valoración que devuelve el servidor
let editando = null;      // id de la posición que se está editando, o null
const abiertas = new Set();   // qué posiciones están desplegadas

const NS = 'http://www.w3.org/2000/svg';

// ---------------------------------------------------------------------------
// Formato
// ---------------------------------------------------------------------------

const SIMBOLOS = {EUR: '€', USD: '$', GBP: '£'};

function dinero(n, moneda = 'EUR', decimales = 2) {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('es-ES', {
    minimumFractionDigits: decimales, maximumFractionDigits: decimales,
  }) + ' ' + (SIMBOLOS[moneda] || moneda);
}

function porcentaje(n) {
  if (n === null || n === undefined) return '—';
  // El signo va SIEMPRE, también en las subidas: así la diferencia entre ganar
  // y perder no depende de distinguir el verde del rojo.
  return (n >= 0 ? '+' : '−') + Math.abs(n).toLocaleString('es-ES',
    {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%';
}

function pintarError(caja, texto) {
  caja.innerHTML = '';
  if (!texto) return;
  const d = document.createElement('div');
  d.className = 'error';
  d.textContent = texto;
  caja.appendChild(d);
}

function crearSVG(tipo, atributos) {
  const el = document.createElementNS(NS, tipo);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
  return el;
}

// Un color estable por posición, sacado de su nombre: la misma empresa tiene
// siempre el mismo cuadradito, aunque cambie de sitio en la lista.
const COLORES_MARCA = ['#3187c4', '#199e70', '#c98500', '#9085e9', '#d95926', '#c33055'];
function colorDe(texto) {
  let suma = 0;
  for (const c of texto) suma = (suma * 31 + c.charCodeAt(0)) % 9973;
  return COLORES_MARCA[suma % COLORES_MARCA.length];
}

// ---------------------------------------------------------------------------
// La cinta del mercado
// ---------------------------------------------------------------------------

async function pintarMercado() {
  const pista = $('pista-mercado');
  let indices = [];
  try {
    indices = (await (await fetch('/api/inversiones/mercado')).json()).indices || [];
  } catch (e) {
    indices = [];
  }

  const conDato = indices.filter(i => i.hay_dato);

  // Si no hay ni un dato, no se enseña una cinta vacía dando vueltas: se dice
  // lo que pasa Y se ofrece averiguar por qué, que "no hay datos" a secas no
  // sirve para arreglar nada.
  if (!conDato.length) {
    const caja = $('franja-mercado');
    caja.innerHTML = '';

    const aviso = document.createElement('div');
    aviso.className = 'mercado-caido';

    const texto = document.createElement('div');
    texto.textContent = 'No he podido leer las cotizaciones. Lo tuyo sigue guardado '
                      + 'igual: esto solo afecta a los precios de hoy.';

    const boton = document.createElement('button');
    boton.className = 'boton secundario';
    boton.style.cssText = 'margin-top:10px;padding:7px 16px;font-size:0.78rem';
    boton.textContent = '¿Por qué?';
    boton.addEventListener('click', () => diagnosticar(boton));

    aviso.append(texto, boton);
    caja.appendChild(aviso);
    return;
  }

  const grupo = document.createDocumentFragment();
  for (const i of indices) grupo.appendChild(fichaMercado(i));
  // Duplicada, para que el bucle encaje al desplazar el 50%
  pista.appendChild(grupo.cloneNode(true));
  pista.appendChild(grupo);
}

// Qué está fallando exactamente: sin internet, una fuente caída, o un símbolo
// mal escrito. Son tres problemas distintos con tres arreglos distintos.
async function diagnosticar(boton) {
  boton.disabled = true;
  boton.textContent = 'Preguntando…';

  let d;
  try {
    d = await (await fetch('/api/inversiones/diagnostico')).json();
  } catch (e) {
    boton.textContent = 'No he podido ni preguntar';
    return;
  }

  const caja = document.createElement('div');
  caja.style.cssText = 'margin-top:14px;text-align:left;max-width:560px;'
                     + 'margin-left:auto;margin-right:auto;font-size:0.78rem;'
                     + 'line-height:1.65';

  const titulo = document.createElement('div');
  titulo.style.cssText = 'color:var(--texto);margin-bottom:8px';
  titulo.textContent = `Probando con ${d.simbolo_probado} (que en Yahoo es `
                     + `${d.traducido_a_yahoo}):`;
  caja.appendChild(titulo);

  for (const f of d.fuentes) {
    const linea = document.createElement('div');
    linea.style.cssText = 'padding:3px 0;color:'
      + (f.ok ? 'var(--verde-vivo)' : 'var(--texto-suave)');
    const estado = f.ok
      ? `responde bien (precio ${f.precio})`
      : (f.codigo ? `contesta ${f.codigo} pero no entiendo lo que manda`
                  : 'no contesta');
    linea.textContent = `${f.ok ? '\u2713' : '\u2717'}  ${f.nombre}: ${estado}`;
    caja.appendChild(linea);
  }

  const conclusion = document.createElement('div');
  conclusion.style.cssText = 'margin-top:10px;color:var(--acento-texto)';
  conclusion.textContent = !d.hay_internet
    ? 'Ninguna de las dos contesta: lo más probable es que este ordenador no '
      + 'tenga internet, o que un antivirus o el cortafuegos las esté bloqueando.'
    : (d.fuentes.some(f => f.ok)
        ? 'Una fuente sí funciona. Si aun así no ves precios, puede que los '
          + 'símbolos de tus posiciones estén mal escritos.'
        : 'Hay internet, pero las dos fuentes contestan algo que no entiendo. '
          + 'Puede que hayan cambiado. Cuéntamelo y lo miro.');
  caja.appendChild(conclusion);

  boton.replaceWith(caja);
}

function fichaMercado(indice) {
  const caja = document.createElement('div');
  caja.className = 'ficha' + (indice.hay_dato ? '' : ' sin-dato');

  const cab = document.createElement('div');
  cab.className = 'cabeza';
  const nom = document.createElement('span');
  nom.className = 'nombre';
  nom.textContent = indice.nombre;
  cab.appendChild(nom);

  const precio = document.createElement('div');
  precio.className = 'precio';

  if (indice.hay_dato) {
    const c = indice.cotizacion;
    const v = document.createElement('span');
    const sube = (c.variacion_dia ?? 0) > 0;
    const baja = (c.variacion_dia ?? 0) < 0;
    v.className = 'var ' + (sube ? 'sube' : baja ? 'baja' : 'plano');
    v.textContent = c.variacion_dia === null ? '' : porcentaje(c.variacion_dia);
    cab.appendChild(v);
    precio.textContent = c.precio.toLocaleString('es-ES',
      {maximumFractionDigits: c.precio < 10 ? 4 : 2});
  } else {
    precio.textContent = 'sin dato ahora';
  }

  const que = document.createElement('div');
  que.className = 'quees';
  que.textContent = indice.que_es;

  caja.append(cab, precio, que);
  return caja;
}

// ---------------------------------------------------------------------------
// El candado
// ---------------------------------------------------------------------------

function pintarCandado() {
  const crear = !estado.existe;
  $('candado-icono').textContent = crear ? '\u{1F0CF}' : '\u{1F512}';
  $('candado-titulo').textContent = crear ? 'Crea tu cartera' : 'Tu cartera está cerrada';
  $('campo-repetida').classList.toggle('oculto', !crear);
  $('abrir-cartera').textContent = crear ? 'Crear la cartera' : 'Abrir';
  $('clave').placeholder = crear ? 'Elige una contraseña' : 'La que elegiste';
  $('clave').autocomplete = crear ? 'new-password' : 'current-password';

  $('candado-explica').textContent = crear
    ? 'Aquí puedes apuntar dónde tienes metido el dinero y cuánto. Se guarda '
      + 'cifrado en este ordenador con una contraseña que eliges tú: sin ella, '
      + 'el fichero no son más que bytes sin sentido. Ni yo puedo leerlo.'
    : 'Los datos están cifrados. Escribe tu contraseña para abrirlos. Se quedará '
      + `en memoria mientras uses la página y se olvidará sola a los `
      + `${estado.minutos_sin_tocar} minutos sin tocar nada, o al cerrar el servidor.`;

  const aviso = $('candado-aviso');
  aviso.innerHTML = '';
  if (crear) {
    const d = document.createElement('div');
    d.className = 'aviso-fuerte';
    d.textContent = 'Apúntala donde no se pierda. No hay "he olvidado mi '
      + 'contraseña": si la pierdes, los datos se pierden con ella. Si hubiera '
      + 'forma de recuperarlos, también la habría para quien cogiese tu portátil.';
    aviso.appendChild(d);
  }

  $('cerrada').classList.remove('oculto');
  $('abierta').classList.add('oculto');
  setTimeout(() => $('clave').focus(), 60);
}

async function abrirOCrear() {
  const boton = $('abrir-cartera');
  const clave = $('clave').value;
  pintarError($('error-clave'), '');

  if (!clave) {
    pintarError($('error-clave'), 'Escribe la contraseña.');
    return;
  }

  boton.disabled = true;
  boton.textContent = 'Un momento…';   // scrypt tarda a propósito
  try {
    const crear = !estado.existe;
    const r = await fetch(crear ? '/api/inversiones/crear' : '/api/inversiones/abrir', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(crear
        ? {clave, repetida: $('clave2').value}
        : {clave}),
    });
    const datos = await r.json();
    if (datos.error) {
      pintarError($('error-clave'), datos.error);
      return;
    }
    $('clave').value = '';
    $('clave2').value = '';
    estado.existe = true;
    estado.abierta = true;
    mostrarCartera(datos.cartera);
  } finally {
    boton.disabled = false;
    pintarCandado.textoBoton = null;
    boton.textContent = estado.existe && estado.abierta ? 'Abrir'
      : (estado.existe ? 'Abrir' : 'Crear la cartera');
  }
}

// ---------------------------------------------------------------------------
// La cartera
// ---------------------------------------------------------------------------

function mostrarCartera(valoracion) {
  cartera = valoracion;
  $('cerrada').classList.add('oculto');
  $('abierta').classList.remove('oculto');

  pintarTotales();
  pintarPosiciones();
  pintarAvisos();
  $('candadito').textContent =
    `Se bloquea sola a los ${estado.minutos_sin_tocar} min sin usarla`;
}

function tarjetaTotal(valor, etiqueta, detalle, clase) {
  const d = document.createElement('div');
  d.className = 'total' + (clase ? ' ' + clase : '');
  const v = document.createElement('div');
  v.className = 'v';
  v.textContent = valor;
  const e = document.createElement('div');
  e.className = 'e';
  e.textContent = etiqueta;
  d.append(v, e);
  if (detalle) {
    const x = document.createElement('div');
    x.className = 'd';
    x.textContent = detalle;
    d.appendChild(x);
  }
  return d;
}

function pintarTotales() {
  const caja = $('totales');
  caja.innerHTML = '';

  if (!cartera.cuantas) {
    const v = document.createElement('div');
    v.className = 'vacio';
    v.style.gridColumn = '1 / -1';
    v.textContent = 'Tu cartera está creada y vacía. Añade lo primero que tengas '
                  + 'y empezaré a decirte cómo va.';
    caja.appendChild(v);
    return;
  }

  const g = cartera.ganancia;
  const hayGanancia = cartera.valor_total !== cartera.coste_total;
  const moneda = cartera.varias_monedas ? '' : (cartera.monedas[0] || 'EUR');

  caja.append(
    tarjetaTotal(dinero(cartera.coste_total, moneda), 'Lo que pusiste',
                 `${cartera.cuantas} ${cartera.cuantas === 1 ? 'posición' : 'posiciones'}`),
    tarjetaTotal(dinero(cartera.valor_total, moneda), 'Lo que vale hoy',
                 cartera.sin_precio
                   ? `${cartera.sin_precio} sin precio de mercado`
                   : 'Con precios de hoy'),
    tarjetaTotal(hayGanancia ? dinero(g, moneda) : '—',
                 g >= 0 ? 'Lo que ganas' : 'Lo que pierdes',
                 hayGanancia ? porcentaje(cartera.ganancia_pct) : 'Sin precios que comparar',
                 hayGanancia ? (g >= 0 ? 'gana' : 'pierde') : ''),
  );
}

// El corazón de la página: cada posición, con tres datos fuera y el resto
// detrás de la flechita.
function pintarPosiciones() {
  const caja = $('posiciones');
  caja.innerHTML = '';

  if (!cartera.posiciones.length) return;

  for (const p of cartera.posiciones) {
    const div = document.createElement('div');
    div.className = 'posicion' + (abiertas.has(p.id) ? ' abierta' : '');

    // --- la fila de siempre ---
    const fila = document.createElement('button');
    fila.className = 'resumen';
    fila.type = 'button';
    fila.setAttribute('aria-expanded', abiertas.has(p.id) ? 'true' : 'false');

    const marca = document.createElement('span');
    marca.className = 'marca';
    marca.style.background = colorDe(p.empresa);
    marca.textContent = p.empresa.trim().charAt(0).toUpperCase();
    marca.setAttribute('aria-hidden', 'true');

    const quien = document.createElement('span');
    quien.className = 'quien';
    const nom = document.createElement('span');
    nom.className = 'nom';
    nom.textContent = p.empresa;
    quien.appendChild(nom);
    if (p.simbolo) {
      const sim = document.createElement('span');
      sim.className = 'sim';
      sim.textContent = p.simbolo;
      quien.appendChild(document.createElement('br'));
      quien.appendChild(sim);
    }

    const cuanto = document.createElement('span');
    cuanto.className = 'cuanto';
    cuanto.textContent = dinero(p.hay_precio ? p.valor : p.coste, p.moneda);
    const peso = document.createElement('span');
    peso.className = 'peso';
    peso.textContent = `${p.peso.toLocaleString('es-ES')}% de la cartera`;
    cuanto.appendChild(peso);

    const como = document.createElement('span');
    if (p.hay_precio) {
      como.className = 'como ' + (p.ganancia >= 0 ? 'sube' : 'baja');
      como.textContent = porcentaje(p.ganancia_pct);
    } else {
      como.className = 'como gris';
      como.textContent = p.motivo_sin_precio === 'sin_simbolo' ? 'no cotiza' : 'sin precio';
    }

    const flecha = document.createElement('span');
    flecha.className = 'flechita';
    flecha.setAttribute('aria-hidden', 'true');
    const svg = crearSVG('svg', {viewBox: '0 0 8 12'});
    svg.appendChild(crearSVG('path', {d: 'M1.4 0.6 L7 6 L1.4 11.4 L0 10 L4 6 L0 2 Z'}));
    flecha.appendChild(svg);

    fila.append(marca, quien, cuanto, como, flecha);
    fila.addEventListener('click', () => {
      if (abiertas.has(p.id)) abiertas.delete(p.id);
      else { abiertas.add(p.id); cargarGrafica(p); }
      pintarPosiciones();
    });

    // --- la barra de peso, finísima ---
    const barra = document.createElement('div');
    barra.className = 'barra-peso';
    const relleno = document.createElement('i');
    relleno.style.width = '0%';
    barra.appendChild(relleno);
    requestAnimationFrame(() => { relleno.style.width = Math.min(p.peso, 100) + '%'; });

    div.append(fila, barra, detallePosicion(p));
    caja.appendChild(div);
  }
}

function detallePosicion(p) {
  const envoltura = document.createElement('div');
  envoltura.className = 'detalle';
  const interior = document.createElement('div');
  const cuerpo = document.createElement('div');
  cuerpo.className = 'detalle-cuerpo';

  // La gráfica solo si hay símbolo: sin él no hay nada que dibujar
  if (p.simbolo) {
    const g = document.createElement('div');
    g.className = 'grafica-pos';
    g.id = 'g-' + p.id;
    const cargando = document.createElement('div');
    cargando.className = 'cargando-mini';
    cargando.textContent = 'Buscando su histórico…';
    g.appendChild(cargando);
    cuerpo.appendChild(g);
  }

  const datos = document.createElement('div');
  datos.className = 'datos-pos';
  const filas = [
    ['Cuántas', p.participaciones.toLocaleString('es-ES', {maximumFractionDigits: 6})],
    ['Precio de compra', dinero(p.precio_compra, p.moneda)],
    ['Te costó', dinero(p.coste, p.moneda)],
  ];
  if (p.hay_precio) {
    filas.push(['Precio de hoy', dinero(p.precio_actual, p.moneda)]);
    filas.push(['Vale ahora', dinero(p.valor, p.moneda)]);
    filas.push([p.ganancia >= 0 ? 'Ganas' : 'Pierdes',
                dinero(Math.abs(p.ganancia), p.moneda) + '  ' + porcentaje(p.ganancia_pct)]);
    if (p.variacion_dia !== null && p.variacion_dia !== undefined) {
      filas.push(['Hoy', porcentaje(p.variacion_dia)]);
    }
    if (p.fecha_precio) filas.push(['Precio del', p.fecha_precio]);
  } else {
    filas.push(['Precio de hoy',
      p.motivo_sin_precio === 'sin_simbolo'
        ? 'No cotiza: cuento lo que pagaste'
        : 'No he podido consultarlo']);
  }
  if (p.fecha) {
    filas.push(['La compraste', new Date(p.fecha + 'T12:00:00')
      .toLocaleDateString('es-ES', {day: 'numeric', month: 'long', year: 'numeric'})]);
  }

  for (const [e, v] of filas) {
    const d = document.createElement('div');
    d.className = 'dato';
    const et = document.createElement('div');
    et.className = 'e';
    et.textContent = e;
    const va = document.createElement('div');
    va.className = 'v';
    va.textContent = v;
    d.append(et, va);
    datos.appendChild(d);
  }
  cuerpo.appendChild(datos);

  if (p.nota) {
    const nota = document.createElement('div');
    nota.className = 'nota-pos';
    nota.textContent = p.nota;
    cuerpo.appendChild(nota);
  }

  const acciones = document.createElement('div');
  acciones.className = 'acciones-pos';
  const editar = document.createElement('button');
  editar.textContent = 'Editar';
  editar.addEventListener('click', () => rellenarFormulario(p));
  const borrar = document.createElement('button');
  borrar.className = 'peligro';
  borrar.textContent = 'Quitar de la cartera';
  borrar.addEventListener('click', () => borrarPosicion(p));
  acciones.append(editar, borrar);
  cuerpo.appendChild(acciones);

  interior.appendChild(cuerpo);
  envoltura.appendChild(interior);
  return envoltura;
}

// La línea del histórico. Una sola serie, así que no hace falta leyenda: el
// título de la tarjeta ya dice de qué es.
async function cargarGrafica(p) {
  if (!p.simbolo) return;
  let puntos = [];
  try {
    const r = await fetch('/api/inversiones/historico?s=' + encodeURIComponent(p.simbolo));
    puntos = (await r.json()).puntos || [];
  } catch (e) {
    puntos = [];
  }

  const caja = $('g-' + p.id);
  if (!caja) return;                 // la ha cerrado mientras cargaba
  caja.innerHTML = '';

  if (puntos.length < 2) {
    const vacio = document.createElement('div');
    vacio.className = 'cargando-mini';
    vacio.textContent = 'No he podido traer su histórico.';
    caja.appendChild(vacio);
    return;
  }

  const ancho = 600, alto = 62;
  const valores = puntos.map(x => x.cierre);
  const min = Math.min(...valores), max = Math.max(...valores);
  const rango = (max - min) || 1;
  const sube = valores[valores.length - 1] >= valores[0];
  const color = sube ? 'var(--verde-vivo)' : 'var(--rojo-vivo)';

  const svg = crearSVG('svg', {
    viewBox: `0 0 ${ancho} ${alto}`, preserveAspectRatio: 'none',
    role: 'img',
    'aria-label': `Evolución de ${p.empresa}: de ${valores[0]} a ${valores[valores.length - 1]}`,
  });

  const d = valores.map((v, i) =>
    `${i === 0 ? 'M' : 'L'} ${(i / (valores.length - 1) * ancho).toFixed(1)} `
    + `${(alto - 4 - (v - min) / rango * (alto - 12)).toFixed(1)}`).join(' ');

  svg.appendChild(crearSVG('path', {
    d: d + ` L ${ancho} ${alto} L 0 ${alto} Z`, fill: color, opacity: 0.12,
  }));
  svg.appendChild(crearSVG('path', {
    d, fill: 'none', stroke: color, 'stroke-width': 1.6,
    'stroke-linejoin': 'round', 'stroke-linecap': 'round',
    'vector-effect': 'non-scaling-stroke',
  }));
  caja.appendChild(svg);

  const pie = document.createElement('div');
  pie.style.cssText = 'font-size:0.68rem;color:#5f6d73;margin-top:3px';
  pie.textContent = `${puntos.length} días · de ${puntos[0].fecha} a `
                  + `${puntos[puntos.length - 1].fecha}`;
  caja.appendChild(pie);
}

// ---------------------------------------------------------------------------
// Añadir y editar
// ---------------------------------------------------------------------------

function abrirFormulario(abrir) {
  $('anadir-caja').classList.toggle('abierta', abrir);
  $('mostrar-anadir').textContent = abrir ? 'Cerrar el formulario' : '+ Añadir una posición';
  if (abrir) setTimeout(() => $('p-empresa').focus(), 120);
}

function limpiarFormulario() {
  editando = null;
  for (const id of ['p-empresa', 'p-simbolo', 'p-participaciones', 'p-precio',
                    'p-fecha', 'p-nota']) $(id).value = '';
  $('p-moneda').value = 'EUR';
  pintarError($('error-posicion'), '');
  $('guardar-posicion').textContent = 'Guardar';
}

function rellenarFormulario(p) {
  editando = p.id;
  $('p-empresa').value = p.empresa;
  $('p-simbolo').value = p.simbolo || '';
  $('p-participaciones').value = p.participaciones;
  $('p-precio').value = p.precio_compra;
  $('p-moneda').value = p.moneda;
  $('p-fecha').value = p.fecha || '';
  $('p-nota').value = p.nota || '';
  $('guardar-posicion').textContent = 'Guardar los cambios';
  abrirFormulario(true);

  // Solo se baja a por el formulario si NO se ve ya: mover la página cuando
  // el usuario la tiene delante es de las cosas que más molestan, porque el
  // sitio donde ibas a pulsar deja de estar donde estaba.
  const caja = $('anadir-caja').getBoundingClientRect();
  const fuera = caja.top < 0 || caja.bottom > window.innerHeight;
  if (fuera) $('anadir-caja').scrollIntoView({behavior: 'smooth', block: 'center'});
}

async function guardarPosicion() {
  pintarError($('error-posicion'), '');
  const cuerpo = {
    id: editando || undefined,
    empresa: $('p-empresa').value,
    simbolo: $('p-simbolo').value,
    participaciones: $('p-participaciones').value,
    precio_compra: $('p-precio').value,
    moneda: $('p-moneda').value,
    fecha: $('p-fecha').value,
    nota: $('p-nota').value,
  };

  const boton = $('guardar-posicion');
  boton.disabled = true;
  try {
    const r = await fetch('/api/inversiones/posicion', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(cuerpo),
    });
    if (r.status === 401) return bloquear(true);
    const datos = await r.json();
    if (datos.error) {
      pintarError($('error-posicion'), datos.error);
      return;
    }

    // Si estabas EDITANDO una, ya has terminado con ella: se cierra.
    // Si estabas AÑADIENDO, lo normal es que vengas a meter la cartera entera
    // de una sentada, así que el formulario se queda abierto y limpio, con el
    // cursor puesto. Cerrarlo y obligarte a volver a abrirlo en cada línea era
    // una pelea tonta.
    const eraEdicion = Boolean(editando);
    limpiarFormulario();
    mostrarCartera(datos.cartera);

    if (eraEdicion) {
      abrirFormulario(false);
    } else {
      $('p-empresa').focus();
      const hecho = document.createElement('div');
      hecho.className = 'apuntado';
      hecho.textContent = 'Apuntado. Sigue con la siguiente, o cierra el formulario.';
      $('error-posicion').appendChild(hecho);
      setTimeout(() => hecho.remove(), 3000);
    }
  } finally {
    boton.disabled = false;
  }
}

async function borrarPosicion(p) {
  if (!window.confirm(`¿Quitar ${p.empresa} de la cartera? Esto no borra nada `
                    + `de tu dinero de verdad, solo el apunte.`)) return;
  const r = await fetch('/api/inversiones/posicion/' + encodeURIComponent(p.id),
                        {method: 'DELETE'});
  if (r.status === 401) return bloquear(true);
  const datos = await r.json();
  if (datos.cartera) {
    abiertas.delete(p.id);
    mostrarCartera(datos.cartera);
  }
}

// ---------------------------------------------------------------------------
// Avisos
// ---------------------------------------------------------------------------

function pintarAvisos() {
  const caja = $('avisos');
  caja.innerHTML = '';
  const avisos = cartera.avisos || [];

  $('seccion-avisos').classList.toggle('oculto', !avisos.length && !cartera.cuantas);

  if (!avisos.length) {
    const v = document.createElement('div');
    v.className = 'vacio';
    v.textContent = cartera.cuantas
      ? 'Nada que señalar por ahora.'
      : 'Cuando apuntes lo que tienes, aquí saldrán avisos con tus cifras: '
        + 'si vas muy concentrado en una sola cosa, cómo llevas el año, y poco más. '
        + 'No te voy a decir qué comprar.';
    caja.appendChild(v);
    return;
  }

  for (const a of avisos) {
    const div = document.createElement('div');
    div.className = 'aviso ' + (a.tipo === 'aviso' ? 'rojo' : a.tipo === 'bien' ? 'verde' : '');
    const c = document.createElement('span');
    c.className = 'clase';
    c.textContent = a.clase;
    const t = document.createElement('div');
    t.textContent = a.texto;
    div.append(c, t);
    caja.appendChild(div);
  }
}

// ---------------------------------------------------------------------------
// Cerrar, cambiar contraseña, borrar
// ---------------------------------------------------------------------------

function bloquear(porCaducidad) {
  estado.abierta = false;
  cartera = null;
  abiertas.clear();
  pintarCandado();
  if (porCaducidad) {
    pintarError($('error-clave'),
      'La cartera se ha vuelto a cerrar. Escribe la contraseña otra vez.');
  }
}

async function cambiarClave() {
  pintarError($('error-cambio'), '');
  $('ok-cambio').innerHTML = '';

  const boton = $('cambiar-clave');
  boton.disabled = true;
  boton.textContent = 'Recifrando…';
  try {
    const r = await fetch('/api/inversiones/clave', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        vieja: $('c-vieja').value, nueva: $('c-nueva').value,
        repetida: $('c-repetida').value,
      }),
    });
    const datos = await r.json();
    if (datos.error) {
      pintarError($('error-cambio'), datos.error);
      return;
    }
    for (const id of ['c-vieja', 'c-nueva', 'c-repetida']) $(id).value = '';
    const ok = document.createElement('div');
    ok.className = 'aviso verde';
    ok.style.marginTop = '14px';
    ok.textContent = 'Hecho. La cartera se ha vuelto a cifrar con la contraseña '
                   + 'nueva; la anterior ya no sirve.';
    $('ok-cambio').appendChild(ok);
  } finally {
    boton.disabled = false;
    boton.textContent = 'Cambiar la contraseña';
  }
}

async function borrarCartera() {
  const clave = window.prompt(
    'Esto borra TODA tu cartera y no se puede deshacer.\n\n'
    + 'Escribe tu contraseña para confirmar:');
  if (clave === null) return;

  const r = await fetch('/api/inversiones/borrar', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({clave}),
  });
  const datos = await r.json();
  if (datos.error) {
    window.alert(datos.error);
    return;
  }
  window.location.reload();
}

// ---------------------------------------------------------------------------
// La entrada: de burdeos a azul
// ---------------------------------------------------------------------------

const sinAnimaciones = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function entrar() {
  const ritmo = sinAnimaciones ? 0 : 1;

  // 1. Las columnas de los laterales se van por su borde más cercano
  const columnas = [...document.querySelectorAll('.palos')];
  columnas.forEach(c => c.classList.add('fuera'));

  // 2. A media salida, la sala vira a azul y la luz cambia de sitio
  setTimeout(() => {
    document.documentElement.classList.add('azul');
    $('halo-arriba').classList.add('apagado');
    $('halo-abajo').classList.add('encendido');
  }, 260 * ritmo);

  // 3. Entran los dos márgenes de palos, cada uno por su lado
  setTimeout(() => {
    $('palos-arriba').classList.add('entrada');
    setTimeout(() => $('palos-abajo').classList.add('entrada'), 120 * ritmo);
    columnas.forEach(c => { c.style.display = 'none'; });
  }, 620 * ritmo);

  // 4. Y por último la cinta del mercado
  setTimeout(() => $('franja-mercado').classList.add('visible'), 1180 * ritmo);
}

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------

$('abrir-cartera').addEventListener('click', abrirOCrear);
for (const id of ['clave', 'clave2']) {
  $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') abrirOCrear(); });
}
$('mostrar-anadir').addEventListener('click',
  () => abrirFormulario(!$('anadir-caja').classList.contains('abierta')));
$('guardar-posicion').addEventListener('click', guardarPosicion);
$('cancelar-posicion').addEventListener('click', () => { limpiarFormulario(); abrirFormulario(false); });
$('bloquear').addEventListener('click', async () => {
  await fetch('/api/inversiones/cerrar', {method: 'POST'});
  bloquear(false);
});
$('cambiar-clave').addEventListener('click', cambiarClave);
$('borrar-cartera').addEventListener('click', borrarCartera);

(async function arrancar() {
  // Los palos de los dos márgenes los monta la misma función que las columnas
  document.querySelectorAll('.palos-fila').forEach(
    (fila, i) => window.rellenarPalos(fila, i + 1, 16));

  pintarMercado();
  entrar();

  try {
    estado = await (await fetch('/api/inversiones/estado')).json();
  } catch (e) {
    estado = {existe: false, abierta: false, minutos_sin_tocar: 30, clave_minima: 8};
  }
  $('cargando').classList.add('oculto');

  if (estado.abierta) {
    const r = await fetch('/api/inversiones/cartera');
    if (r.ok) {
      const datos = await r.json();
      mostrarCartera(datos.cartera);
      return;
    }
  }
  pintarCandado();
})();
