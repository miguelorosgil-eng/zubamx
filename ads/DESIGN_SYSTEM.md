# ZUBA Ads — Sistema de Diseño Base

## Paleta de color

| Token         | Hex       | Uso                                      |
|---------------|-----------|------------------------------------------|
| `--orange`    | `#FF6B35` | Acento principal, CTAs, highlights       |
| `--orange-lt` | `#FF8C5A` | Gradiente del logo, sombras cálidas      |
| `--bg-warm`   | `#FFF8F5` | Fondo cálido (l1)                        |
| `--bg-cool`   | `#FAFAF8` | Fondo frío (l2, l3)                      |
| `--text-900`  | `#111827` | Titulares, texto principal               |
| `--text-800`  | `#1F2937` | Subtítulos, etiquetas                    |
| `--text-700`  | `#374151` | Texto secundario, notas — NUNCA más gris |
| `--green`     | `#10B981` | Métricas positivas, live dot             |
| `--green-dk`  | `#059669` | Texto sobre badge verde                  |

**Regla:** Ningún texto sobre fondo crema usa gris puro. Mínimo `#374151`.

---

## Layout — Estructura fija 1080×1350

```
┌────────────────────────┐  ↑
│                        │  │
│   CONTENT ZONE         │  810px  (60%)
│   z-index: 10          │  │
│   padding: 52px 56px   │  │
│                        │  ↓
├────────────────────────┤  fade CSS
│                        │  ↑
│   PHOTO ZONE           │  540px  (40%)
│   z-index: 1           │  │
│   object-fit: cover    │  ↓
└────────────────────────┘
```

**Regla:** Texto arriba, imagen abajo. La imagen nunca ocupa más del 40%.

### CSS base del layout

```css
.photo-zone {
  position:absolute; bottom:0; left:0; right:0;
  height:540px; overflow:hidden; z-index:1;
}
.photo-zone img {
  width:100%; height:100%;
  object-fit:cover;
}
.photo-zone::before {          /* fade superior: foto → fondo */
  content:''; position:absolute; top:0; left:0; right:0;
  height:150–180px; z-index:2;
  background:linear-gradient(to bottom, VAR_BG 0%, transparent 100%);
}
.photo-zone::after {           /* vignette inferior para profundidad */
  content:''; position:absolute; bottom:0; left:0; right:0;
  height:160–200px; z-index:2;
  background:linear-gradient(to top, rgba(0,0,0,0.40–0.50) 0%, transparent 100%);
}
.content {
  position:relative; z-index:10;
  padding:52px 56px 0; height:810px;
  display:flex; flex-direction:column;
}
```

---

## Logo

```html
<div class="logo-bar">
  <div class="logo-inner">
    <div class="logo-icon">Z</div>
    <div class="logo-name">ZUBA</div>
  </div>
  <!-- badge variable por ad -->
</div>
```

```css
.logo-icon {
  width:48px; height:48px;
  background:linear-gradient(145deg,#FF8C5A,#FF6B35);
  border-radius:12px;
  font-size:28px; font-weight:900; font-style:italic; color:#fff;
  box-shadow:0 4px 16px rgba(255,107,53,0.40);
}
.logo-name { font-size:28px; font-weight:700; color:#111827; letter-spacing:-0.5px; }
```

---

## Tipografía

- Fuente: **Inter** (Google Fonts) — pesos: 400, 500, 600, 700, 900
- Eyebrow: `12px / 700 / #FF6B35 / letter-spacing 2.5px / uppercase`
- Headline: `82–86px / 900 / italic / line-height 0.90 / letter-spacing -3.5–4px`
- Bridge: `17–19px / 500 / #111827 / line-height 1.50`

```css
.headline { font-size:86px; font-weight:900; font-style:italic;
  line-height:0.90; letter-spacing:-4px; color:#111827; }
.headline .accent { color:#FF6B35; }
```

---

## CTA Button

```css
.cta-btn {
  background:#FF6B35; color:#fff;
  font-size:17px; font-weight:900;
  padding:20px 40px; border-radius:14px;
  box-shadow:0 8px 28px rgba(255,107,53,0.42);
}
```

---

## Fotos disponibles (`ads/luxury/photos/`)

| Archivo                | Contenido                              | Usado en |
|------------------------|----------------------------------------|----------|
| `taco-lime.jpg`        | Lima exprimida sobre fila de tacos     | L1       |
| `taco-overhead.jpg`    | 3 tacos coloridos vista cenital        | L2       |
| `taco-street.jpg`      | Tacos callejeros auténticos            | —        |
| `delivery-cyclist.jpg` | Ciclista Uber Eats en ciudad           | L3       |
| `delivery-ue-bag.jpg`  | Bolsa verde Uber Eats México           | —        |
| `delivery/`            | 8 fotos Pexels adicionales de delivery | —        |

**Criterio de selección:** editorial, alta resolución, contexto CDMX/México, nada genérico.

---

## Ads actuales

| Archivo              | Concepto              | Hook principal                              |
|----------------------|-----------------------|---------------------------------------------|
| `l1-algoritmo.html`  | Posicionamiento       | "¿Por qué tu vecino tiene 52 pedidos y tú 3?" |
| `l2-comparativa.html`| Antes/Después         | "En 30 días con ZUBA esto cambia"           |
| `l3-notificaciones.html` | Prueba social     | "Tu celular debería no parar"               |

---

## Generación de PNGs

```bash
cd /home/user/zubamx
python3 generate-luxury.py
# → output/luxury/*.png  (device_scale_factor=2, ~2MB c/u)
# → ZUBA_KIT_LUXURY_ADS.zip
```

---

## Próximas iteraciones sugeridas

- **L4 — Testimonial:** foto de restaurantero real + quote + métricas
- **L5 — Urgencia:** contador de restaurantes que ya usan ZUBA en su zona
- **L6 — Plataformas:** logos UE + Rappi + DiDi + headline "¿Estás en las 3?"
- Variar `object-position` según la foto para controlar el crop
- Probar fondo `#F5F0EB` (más cálido) para ads de temporada
