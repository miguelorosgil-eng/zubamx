import React from 'react'
import Logo from '@/components/Logo'
import FAQ from '@/components/FAQ'
import PricingCard from '@/components/PricingCard'

const WA_LINK =
  'https://wa.me/525642926243?text=Hola%2C%20quiero%20una%20auditor%C3%ADa%20gratuita%20con%20ZUBA'

const factors = [
  {
    num: '01',
    title: 'Fotografía',
    desc: 'Las fotos HD aumentan la conversión hasta ×3. Sin fotos profesionales, el algoritmo te ignora.',
  },
  {
    num: '02',
    title: 'Rating',
    desc: 'Por debajo de 4.3 el algoritmo te penaliza activamente. Cada décima importa.',
  },
  {
    num: '03',
    title: 'Arquitectura de menú',
    desc: 'El orden de tus categorías y el naming de tus platillos afectan directamente el ticket promedio.',
  },
  {
    num: '04',
    title: 'Tiempo de entrega',
    desc: 'Cada minuto adicional de entrega cuesta conversión. Los clientes eligen al más rápido.',
  },
  {
    num: '05',
    title: 'Promociones',
    desc: 'Una promoción mal configurada destruye el margen. Bien configurada, domina la categoría.',
  },
]

const steps = [
  { num: '01', label: 'AUDITORÍA', days: 'Días 1–3', desc: 'Diagnóstico completo + baseline documentado de tus últimos 60 días.' },
  { num: '02', label: 'DISEÑO', days: 'Días 4–14', desc: 'Plan estratégico + fotografía profesional + reestructura del menú.' },
  { num: '03', label: 'EJECUCIÓN', days: 'Días 15–60', desc: 'Implementación total + visibilidad orgánica en plataformas.' },
  { num: '04', label: 'OPTIMIZACIÓN', days: 'Día 61+', desc: 'Ajuste continuo con datos reales + reportes mensuales.' },
]

const plans = [
  {
    name: 'Plan Base',
    setup: '$0 de setup',
    commission: '30% sobre el incremento real',
    features: [
      'Auditoría completa de tu perfil',
      'Optimización de menú',
      'Estrategia de rating',
      'Reporte mensual de resultados',
    ],
    highlighted: false,
  },
  {
    name: 'Plan Acelerador',
    badge: 'Más popular',
    setup: 'Setup + Retainer',
    commission: '+30% sobre el incremento real',
    features: [
      'Todo lo del Plan Base',
      'Fotografía profesional incluida',
      'Pauta en plataformas',
      'Optimización semanal',
    ],
    highlighted: true,
  },
  {
    name: 'Plan Premium',
    setup: 'Retainer $5,000 MXN',
    commission: '+20% sobre el incremento real',
    features: [
      'Todo lo del Plan Acelerador',
      'Account manager dedicado',
      'Dashboard de métricas en vivo',
      'Reportes ejecutivos semanales',
    ],
    highlighted: false,
  },
]

export default function Home() {
  return (
    <div className="min-h-screen bg-crema text-negro">
      {/* NAV */}
      <nav className="sticky top-0 z-50 bg-crema/90 backdrop-blur-sm border-b border-negro/5">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Logo size={36} />
          <a
            href={WA_LINK}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-naranja text-white text-sm font-bold px-5 py-2.5 rounded-xl hover:bg-naranja-oscuro transition-colors duration-200"
          >
            Auditoría gratis
          </a>
        </div>
      </nav>

      {/* HERO */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-24 text-center">
        <p className="text-naranja text-sm font-bold uppercase tracking-widest mb-4">
          Uber Eats · DiDi Food · Rappi
        </p>
        <h1 className="text-5xl md:text-7xl font-black leading-none tracking-tight text-balance mb-6">
          Delivery que<br />
          <span className="text-naranja">vende solo.</span>
        </h1>
        <p className="text-lg md:text-xl text-negro/60 max-w-2xl mx-auto mb-4 leading-relaxed">
          Tu restaurante está en las plataformas.<br />
          <strong className="text-negro">¿Por qué no vende lo que debería?</strong>
        </p>
        <p className="text-base text-negro/50 max-w-xl mx-auto mb-10">
          Cada día que no estás optimizado, tu competencia se queda con tus clientes.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a
            href={WA_LINK}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-naranja text-white font-bold text-base px-8 py-4 rounded-xl hover:bg-naranja-oscuro transition-colors duration-200 shadow-lg shadow-naranja/30"
          >
            Quiero mi auditoría gratuita
          </a>
          <a
            href="#planes"
            className="bg-negro/5 text-negro font-bold text-base px-8 py-4 rounded-xl hover:bg-negro/10 transition-colors duration-200"
          >
            Ver planes →
          </a>
        </div>
      </section>

      {/* SOCIAL PROOF */}
      <section className="bg-negro text-white py-16">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-center text-white/40 text-xs font-bold uppercase tracking-widest mb-10">
            Resultado real · Taquería CDMX · $0 de pauta
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <p className="text-4xl md:text-5xl font-black text-naranja">3.8</p>
              <p className="text-white/50 text-sm mt-1">Rating inicial</p>
            </div>
            <div>
              <p className="text-4xl md:text-5xl font-black text-naranja">4.7</p>
              <p className="text-white/50 text-sm mt-1">Rating final</p>
            </div>
            <div>
              <p className="text-4xl md:text-5xl font-black text-naranja">×3</p>
              <p className="text-white/50 text-sm mt-1">Conversión con fotos HD</p>
            </div>
            <div>
              <p className="text-4xl md:text-5xl font-black text-naranja">Top 3</p>
              <p className="text-white/50 text-sm mt-1">En su categoría</p>
            </div>
          </div>
        </div>
      </section>

      {/* 5 FACTORES */}
      <section className="max-w-6xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <p className="text-naranja text-sm font-bold uppercase tracking-widest mb-3">El diagnóstico</p>
          <h2 className="text-3xl md:text-5xl font-black tracking-tight">
            5 factores que deciden<br />si vendes o no vendes.
          </h2>
          <p className="text-negro/50 mt-4 max-w-xl mx-auto">
            El algoritmo de Uber Eats no es aleatorio. Tiene reglas. ZUBA las conoce.
          </p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {factors.map((f) => (
            <div
              key={f.num}
              className="bg-white rounded-2xl p-7 shadow-sm hover:shadow-md transition-shadow duration-200 group"
            >
              <p className="text-naranja text-xs font-black uppercase tracking-widest mb-3 group-hover:text-naranja-oscuro transition-colors">
                {f.num}
              </p>
              <h3 className="text-xl font-black mb-2">{f.title}</h3>
              <p className="text-negro/60 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
          {/* 5th card is at index 4 so grid has odd one out — add a CTA card */}
          <div className="bg-naranja rounded-2xl p-7 flex flex-col justify-between">
            <p className="text-white font-black text-lg leading-snug">
              ¿Cuántos de estos 5 factores tienes optimizados?
            </p>
            <a
              href={WA_LINK}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 inline-block bg-white text-naranja font-bold text-sm px-5 py-3 rounded-xl hover:bg-crema transition-colors duration-200 text-center"
            >
              Descúbrelo gratis →
            </a>
          </div>
        </div>
      </section>

      {/* EL MÉTODO */}
      <section className="bg-negro text-white py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <p className="text-naranja text-sm font-bold uppercase tracking-widest mb-3">El proceso</p>
            <h2 className="text-3xl md:text-5xl font-black tracking-tight">
              4 pasos. Resultados reales.
            </h2>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map((s) => (
              <div key={s.num} className="border border-white/10 rounded-2xl p-7">
                <p className="text-naranja text-xs font-black uppercase tracking-widest mb-1">{s.num}</p>
                <h3 className="text-lg font-black mb-1">{s.label}</h3>
                <p className="text-white/40 text-xs font-semibold mb-4">{s.days}</p>
                <p className="text-white/60 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PLANES */}
      <section id="planes" className="max-w-6xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <p className="text-naranja text-sm font-bold uppercase tracking-widest mb-3">Transparencia total</p>
          <h2 className="text-3xl md:text-5xl font-black tracking-tight">
            Solo cobramos cuando<br />tú creces.
          </h2>
          <p className="text-negro/50 mt-4 max-w-xl mx-auto">
            Baseline documentado de los últimos 60 días. Si no crece, no cobramos de más.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-8 items-start mt-8">
          {plans.map((plan) => (
            <PricingCard key={plan.name} {...plan} />
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="bg-white py-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-16">
            <p className="text-naranja text-sm font-bold uppercase tracking-widest mb-3">Preguntas frecuentes</p>
            <h2 className="text-3xl md:text-5xl font-black tracking-tight">
              Sin letra chica.
            </h2>
          </div>
          <FAQ />
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="max-w-6xl mx-auto px-6 py-24 text-center">
        <h2 className="text-3xl md:text-6xl font-black tracking-tight mb-6">
          Tu competencia ya<br />
          está optimizada.<br />
          <span className="text-naranja">¿Tú sí?</span>
        </h2>
        <p className="text-negro/50 mb-10 max-w-lg mx-auto">
          Auditoría gratuita. 20 minutos. Sin compromiso. Te decimos exactamente qué está frenando tus pedidos.
        </p>
        <a
          href={WA_LINK}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block bg-naranja text-white font-black text-lg px-10 py-5 rounded-2xl hover:bg-naranja-oscuro transition-colors duration-200 shadow-xl shadow-naranja/30"
        >
          Quiero mi auditoría gratuita →
        </a>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-negro/10 py-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <Logo size={32} />
          <div className="flex items-center gap-6 text-sm text-negro/40">
            <a
              href={WA_LINK}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-naranja transition-colors"
            >
              WhatsApp
            </a>
            <a
              href="https://www.facebook.com/ZubaMX"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-naranja transition-colors"
            >
              Facebook
            </a>
          </div>
          <p className="text-xs text-negro/30">© {new Date().getFullYear()} ZUBA. Todos los derechos reservados.</p>
        </div>
      </footer>
    </div>
  )
}
