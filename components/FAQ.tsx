'use client'

import React, { useState } from 'react'

interface FAQItem {
  question: string
  answer: string
}

const faqs: FAQItem[] = [
  {
    question: '¿ZUBA es una agencia de marketing?',
    answer:
      'No. ZUBA no crea anuncios ni maneja redes. Entramos a la operación en plataformas y la optimizamos. Es trabajo técnico, no creativo.',
  },
  {
    question: '¿Qué pasa si no suben mis ventas?',
    answer:
      'Documentamos tu baseline de los últimos 60 días. Si no crece, no cobramos de más. Así de simple.',
  },
  {
    question: '¿Funciona para cualquier tipo de restaurante?',
    answer:
      'Sí. Restaurantes, cafeterías, panaderías, fondas, taquerías. En plataformas o queriendo entrar bien desde el día 1.',
  },
  {
    question: '¿Cuánto tiempo toma ver resultados?',
    answer:
      'El trabajo empieza el día 1 y se mide con datos reales. Sin atajos. Sin promesas vacías.',
  },
  {
    question: '¿Cuánto cuesta?',
    answer:
      'Depende del plan. El Plan Base no tiene costo de setup — solo cobramos sobre el incremento real. Agenda una auditoría gratuita y te damos los números exactos.',
  },
]

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  function toggle(index: number) {
    setOpenIndex((prev) => (prev === index ? null : index))
  }

  return (
    <div className="w-full max-w-3xl mx-auto divide-y divide-naranja/20">
      {faqs.map((item, index) => {
        const isOpen = openIndex === index
        return (
          <div key={index} className="py-0">
            <button
              type="button"
              onClick={() => toggle(index)}
              aria-expanded={isOpen}
              className="w-full flex items-center justify-between py-5 px-0 text-left gap-4 group focus:outline-none focus-visible:ring-2 focus-visible:ring-naranja rounded"
            >
              <span className="text-base md:text-lg font-semibold text-negro group-hover:text-naranja transition-colors duration-200">
                {item.question}
              </span>
              <span
                className={`flex-shrink-0 w-7 h-7 rounded-full border-2 border-naranja flex items-center justify-center transition-transform duration-300 ${
                  isOpen ? 'rotate-45 bg-naranja' : 'bg-transparent'
                }`}
                aria-hidden="true"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M7 1V13M1 7H13"
                    stroke={isOpen ? '#FFFFFF' : '#FF6B35'}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  />
                </svg>
              </span>
            </button>

            {/* Answer panel — CSS max-height animation */}
            <div
              className="overflow-hidden transition-all duration-300 ease-in-out"
              style={{ maxHeight: isOpen ? '400px' : '0px' }}
            >
              <p className="pb-5 text-sm md:text-base text-negro/70 leading-relaxed">
                {item.answer}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
