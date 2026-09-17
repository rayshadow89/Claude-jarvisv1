/* =========================================================================
   Las dos gráficas de J0KER GASTOS
   =========================================================================

   Están hechas a mano con SVG, sin librerías: son dos formas concretas y
   traer medio megabyte de dependencia para esto sería pagar de más.

   Sobre los colores. No están elegidos a ojo: se han pasado por el validador
   de paletas contra el fondo oscuro de la página (#14100f), comprobando
   luminosidad, saturación, separación con daltonismo (protanopia y
   deuteranopia) y contraste. Los seis del círculo pasan todas las
   comprobaciones, incluido el par que se cierra (el último trozo toca al
   primero, que es un fallo clásico en los gráficos de tarta).

   Y por si acaso, el color nunca es lo único que distingue: la línea prevista
   va discontinua, los trozos del círculo van separados por un hueco, y la
   leyenda lleva el nombre y la cifra de cada uno.
   ========================================================================= */

const COLOR_REAL = '#c33055';      // el burdeos de la casa: lo que te queda de verdad
const COLOR_IDEAL = '#3987e5';     // azul: el ritmo que deberías llevar
const SUPERFICIE = '#14100f';
const TINTA = '#a49197';           // el texto siempre en tinta, nunca del color de la serie
const REJILLA = '#2c2225';

// El orden es fijo: cada parte se queda con su color aunque cambies de regla.
const COLORES_PARTES = [
  '#c33055',  // burdeos
  '#c98500',  // ámbar
  '#199e70',  // verde
  '#3987e5',  // azul
  '#d95926',  // naranja
  '#9085e9',  // violeta
];

const NS = 'http://www.w3.org/2000/svg';
const crearSVG = (tipo, atributos) => {
  const el = document.createElementNS(NS, tipo);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
  return el;
};

const dinero = (n) => (n ?? 0).toLocaleString('es-ES',
  {style: 'currency', currency: 'EUR', maximumFractionDigits: 0});

// -------------------------------------------------------------------------
// La línea: cuánto te queda, día a día
// -------------------------------------------------------------------------
// Una sola escala vertical, en euros, para las dos series. Nada de dos ejes:
// comparar dos líneas con escalas distintas es engañar al que mira.

function dibujarLinea(graficas) {
  const caja = document.getElementById('grafica-linea');
  caja.innerHTML = '';

  const real = graficas.linea || [];
  const ideal = graficas.ideal || [];
  if (!ideal.length) return;

  if (!real.length) {
    const vacio = document.createElement('div');
    vacio.style.cssText = 'text-align:center;color:#6b585e;padding:44px 20px;line-height:1.7';
    vacio.textContent = 'Apunta tu primer gasto y aquí verás cuánto te va quedando, '
                      + 'frente al ritmo que te deja llegar a tu ahorro.';
    caja.appendChild(vacio);
    return;
  }

  const ancho = Math.max(caja.clientWidth || 620, 300);
  const alto = 280;
  const m = {arriba: 18, derecha: 16, abajo: 38, izquierda: 62};
  const anchoUtil = ancho - m.izquierda - m.derecha;
  const altoUtil = alto - m.arriba - m.abajo;

  const dias = ideal.length;
  const valores = [...real.map(d => d.queda), ...ideal.map(d => d.queda), 0];
  let vMin = Math.min(...valores), vMax = Math.max(...valores);
  const respiro = Math.max((vMax - vMin) * 0.1, 10);
  vMin -= respiro; vMax += respiro;

  const x = (i) => m.izquierda + (dias > 1 ? i / (dias - 1) * anchoUtil : anchoUtil / 2);
  const y = (v) => m.arriba + altoUtil - (v - vMin) / (vMax - vMin) * altoUtil;

  const svg = crearSVG('svg', {
    viewBox: `0 0 ${ancho} ${alto}`, width: '100%', height: alto,
    role: 'img',
    'aria-label': 'Lo que te queda cada día frente al ritmo previsto',
  });

  // Rejilla, discreta y continua
  for (let i = 0; i <= 4; i++) {
    const v = vMin + (vMax - vMin) * i / 4;
    const py = y(v);
    svg.appendChild(crearSVG('line', {
      x1: m.izquierda, y1: py, x2: ancho - m.derecha, y2: py,
      stroke: REJILLA, 'stroke-width': 1,
    }));
    const t = crearSVG('text', {
      x: m.izquierda - 9, y: py + 4, 'text-anchor': 'end',
      fill: TINTA, 'font-size': 11,
    });
    t.textContent = dinero(v);
    svg.appendChild(t);
  }

  // El cero: la raya que no hay que cruzar
  if (vMin < 0 && vMax > 0) {
    svg.appendChild(crearSVG('line', {
      x1: m.izquierda, y1: y(0), x2: ancho - m.derecha, y2: y(0),
      stroke: '#6b585e', 'stroke-width': 1, 'stroke-dasharray': '1 3',
    }));
  }

  // Fechas, unas pocas
  const marcas = Math.min(6, dias);
  for (let i = 0; i < marcas; i++) {
    const indice = Math.round(i * (dias - 1) / (marcas - 1 || 1));
    const t = crearSVG('text', {
      x: x(indice), y: alto - m.abajo + 19, 'text-anchor': 'middle',
      fill: TINTA, 'font-size': 11,
    });
    t.textContent = new Date(ideal[indice].fecha + 'T12:00:00')
      .toLocaleDateString('es-ES', {day: 'numeric', month: 'short'});
    svg.appendChild(t);
  }

  const camino = (serie, desde = 0) => serie.map((d, i) =>
    `${i === 0 ? 'M' : 'L'} ${x(i + desde).toFixed(1)} ${y(d.queda).toFixed(1)}`).join(' ');

  // El ritmo previsto: discontinuo, para que no dependa del color
  svg.appendChild(crearSVG('path', {
    d: camino(ideal), fill: 'none', stroke: COLOR_IDEAL,
    'stroke-width': 2, 'stroke-dasharray': '6 5', 'stroke-linecap': 'round',
  }));

  // Lo que te queda de verdad
  if (real.length > 1) {
    svg.appendChild(crearSVG('path', {
      d: camino(real), fill: 'none', stroke: COLOR_REAL,
      'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    }));
  }
  // El punto de hoy, con anillo del color del fondo para que se despegue
  const ultimo = real[real.length - 1];
  svg.appendChild(crearSVG('circle', {
    cx: x(real.length - 1), cy: y(ultimo.queda), r: 5,
    fill: COLOR_REAL, stroke: SUPERFICIE, 'stroke-width': 2,
  }));

  // Etiqueta directa sobre el punto de hoy: dos series, las dos con nombre
  const etiqueta = crearSVG('text', {
    x: Math.min(x(real.length - 1) + 9, ancho - m.derecha - 4),
    y: y(ultimo.queda) - 9,
    'text-anchor': x(real.length - 1) > ancho * 0.7 ? 'end' : 'start',
    fill: '#fff', 'font-size': 11, 'font-weight': 600,
  });
  etiqueta.textContent = dinero(ultimo.queda);
  svg.appendChild(etiqueta);

  // Capa de interacción
  const guia = crearSVG('line', {
    x1: 0, y1: m.arriba, x2: 0, y2: m.arriba + altoUtil,
    stroke: '#6b585e', 'stroke-width': 1, opacity: 0,
  });
  svg.appendChild(guia);
  const zona = crearSVG('rect', {
    x: m.izquierda, y: m.arriba, width: anchoUtil, height: altoUtil, fill: 'transparent',
  });
  svg.appendChild(zona);
  caja.appendChild(svg);

  const globo = document.createElement('div');
  globo.className = 'globo';
  caja.appendChild(globo);

  zona.addEventListener('mousemove', (e) => {
    const r = svg.getBoundingClientRect();
    const escala = ancho / r.width;
    const px = (e.clientX - r.left) * escala;
    const i = Math.max(0, Math.min(dias - 1,
      Math.round((px - m.izquierda) / anchoUtil * (dias - 1))));

    guia.setAttribute('x1', x(i));
    guia.setAttribute('x2', x(i));
    guia.setAttribute('opacity', 1);

    globo.innerHTML = '';
    const cab = document.createElement('div');
    cab.className = 'globo-fecha';
    cab.textContent = new Date(ideal[i].fecha + 'T12:00:00')
      .toLocaleDateString('es-ES', {day: 'numeric', month: 'long'});
    globo.appendChild(cab);

    const fila = (color, texto) => {
      const f = document.createElement('div');
      f.className = 'globo-fila';
      const p = document.createElement('span');
      p.className = 'globo-punto';
      p.style.background = color;
      const t = document.createElement('span');
      t.textContent = texto;
      f.append(p, t);
      return f;
    };
    if (real[i]) {
      globo.appendChild(fila(COLOR_REAL, `Te queda: ${dinero(real[i].queda)}`));
      globo.appendChild(fila(COLOR_REAL, `Llevas gastado: ${dinero(real[i].gastado)}`));
    }
    globo.appendChild(fila(COLOR_IDEAL, `Ritmo previsto: ${dinero(ideal[i].queda)}`));

    globo.style.opacity = 1;
    const izq = x(i) / escala;
    globo.style.left = Math.min(Math.max(izq, 92), r.width - 92) + 'px';
  });

  zona.addEventListener('mouseleave', () => {
    guia.setAttribute('opacity', 0);
    globo.style.opacity = 0;
  });
}

// -------------------------------------------------------------------------
// El círculo: cómo reparte tu regla el dinero
// -------------------------------------------------------------------------
// Es un donut y no una tarta a propósito: el agujero del medio sirve para la
// cifra que de verdad importa (lo que ingresas), y comparar arcos cuesta
// menos que comparar porciones que se tocan en el centro.
//
// Cada trozo lleva DOS anillos: el de fuera es lo que la regla le asigna, y
// el de dentro, más grueso, lo que llevas usado. Así se ve de un vistazo qué
// parte va sobrada y cuál se te ha ido de las manos.

function dibujarCirculo(graficas) {
  const caja = document.getElementById('grafica-circulo');
  const leyenda = document.getElementById('circulo-leyenda');
  caja.innerHTML = '';
  leyenda.innerHTML = '';

  const partes = graficas.circulo || [];
  if (!partes.length) return;

  const lado = 250;
  const centro = lado / 2;
  const rExterior = 106, rInterior = 74;   // el anillo del presupuesto
  const rUsadoFuera = 70, rUsadoDentro = 46;

  const svg = crearSVG('svg', {
    viewBox: `0 0 ${lado} ${lado}`, width: lado, height: lado,
    role: 'img', 'aria-label': 'Cómo reparte tu regla el dinero del mes',
  });

  // El hueco de 2 px entre trozos: separa por forma, no solo por color
  const HUECO = 1.4;   // grados

  const arco = (desde, hasta, rFuera, rDentro) => {
    const a1 = (desde - 90) * Math.PI / 180;
    const a2 = (hasta - 90) * Math.PI / 180;
    const grande = (hasta - desde) > 180 ? 1 : 0;
    const p = (r, a) => `${(centro + r * Math.cos(a)).toFixed(2)} ${(centro + r * Math.sin(a)).toFixed(2)}`;
    return `M ${p(rFuera, a1)} A ${rFuera} ${rFuera} 0 ${grande} 1 ${p(rFuera, a2)} `
         + `L ${p(rDentro, a2)} A ${rDentro} ${rDentro} 0 ${grande} 0 ${p(rDentro, a1)} Z`;
  };

  let angulo = 0;
  partes.forEach((parte, i) => {
    const color = COLORES_PARTES[i % COLORES_PARTES.length];
    const barrido = parte.pct * 3.6;
    if (barrido <= 0) return;

    const desde = angulo + HUECO / 2;
    const hasta = angulo + barrido - HUECO / 2;
    angulo += barrido;
    if (hasta <= desde) return;

    // Anillo de fuera: lo que la regla le da
    const presupuesto = crearSVG('path', {
      d: arco(desde, hasta, rExterior, rInterior),
      fill: color, opacity: 0.35,
    });
    svg.appendChild(presupuesto);

    // Anillo de dentro: lo que llevas usado, sobre el mismo barrido
    const usado = Math.min(parte.porcentaje_usado, 100) / 100;
    if (usado > 0) {
      const hastaUsado = desde + (hasta - desde) * usado;
      svg.appendChild(crearSVG('path', {
        d: arco(desde, hastaUsado, rUsadoFuera, rUsadoDentro),
        fill: color, opacity: 1,
      }));
    }
    // Si se ha pasado del 100%, un filo marcando el borde
    if (parte.porcentaje_usado > 100 && parte.tipo === 'gasto') {
      svg.appendChild(crearSVG('path', {
        d: arco(desde, hasta, rExterior + 5, rExterior + 2),
        fill: color, opacity: 1,
      }));
    }
  });

  // En el agujero, la cifra que manda
  const total = crearSVG('text', {
    x: centro, y: centro - 2, 'text-anchor': 'middle',
    fill: '#fff', 'font-size': 19, 'font-weight': 600,
  });
  total.textContent = dinero(graficas.ingreso);
  const pie = crearSVG('text', {
    x: centro, y: centro + 15, 'text-anchor': 'middle',
    fill: TINTA, 'font-size': 10, 'letter-spacing': 1.2,
  });
  pie.textContent = 'AL MES';
  svg.append(total, pie);
  caja.appendChild(svg);

  // La leyenda: nombre, porcentaje y cuánto llevas. El color acompaña, no
  // sustituye — quien no distinga dos tonos sigue teniendo toda la
  // información escrita.
  partes.forEach((parte, i) => {
    const fila = document.createElement('div');
    fila.className = 'fila';
    const punto = document.createElement('span');
    punto.className = 'punto';
    punto.style.background = COLORES_PARTES[i % COLORES_PARTES.length];
    const nombre = document.createElement('span');
    nombre.className = 'nombre';
    nombre.textContent = `${parte.nombre} · ${parte.pct.toLocaleString('es-ES')}%`;
    const valor = document.createElement('span');
    valor.className = 'valor';
    valor.textContent = `${dinero(parte.usado)} de ${dinero(parte.presupuesto)}`;
    fila.append(punto, nombre, valor);
    leyenda.appendChild(fila);
  });

  const nota = document.createElement('div');
  nota.style.cssText = 'font-size:0.72rem;color:#6b585e;line-height:1.5;margin-top:10px';
  nota.textContent = 'El anillo de fuera es lo que te toca; el de dentro, lo que llevas.';
  leyenda.appendChild(nota);
}
