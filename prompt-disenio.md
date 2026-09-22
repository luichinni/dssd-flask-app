Framework CSS: Tailwind CSS (clases utilitarias directas, sin archivos de estilos CSS personalizados masivos).

Estética General: Diseño SaaS moderno, limpio, corporativo y profesional. Prioriza la claridad visual, la legibilidad e interfaces con alta densidad de información estructurada.

Paleta de Colores:

Base/Fondos: Tonos neutros slate/gray suaves (bg-slate-50, bg-slate-100, bg-white).

Texto: Contraste alto con tonos oscuros (text-slate-900 para títulos, text-slate-600 para cuerpo de texto).

Color Primario/Acento: Añil/Índigo profesional (bg-indigo-600, hover:bg-indigo-700, text-indigo-600).

Estados/Roles: Indicadores de estado tipo badge utilizando colores semánticos suaves (amber para advertencias/operadores, blue para coordinación, emerald para ONGs/éxito, purple para auditoría, red para errores).

Componentes y Bordes:

Tarjetas y contenedores con fondo blanco (bg-white), bordes delgados y discretos (border border-slate-200) y esquinas redondeadas suaves (rounded-xl o rounded-2xl).

Sombras extremadamente sutiles (shadow-sm, hover:shadow-md) con transiciones suaves en las interacciones (transition).

Uso de micro-badges con texto en mayúsculas, tamaño reducido (text-xs font-semibold) y padding redondeado (rounded-full).

Diseño Responsive y Estructura:

Maquetación mediante Flexbox y CSS Grid (grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6).

Plantilla base modular con Jinja2 (layout.html), navbar superior sticky/fija, área de contenido central encapsulada con límites de ancho (max-w-7xl mx-auto px-4) y footer al pie.