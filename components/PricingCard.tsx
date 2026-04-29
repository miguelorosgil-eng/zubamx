import React from 'react'

interface PricingCardProps {
  name: string
  badge?: string
  setup: string
  commission: string
  features: string[]
  highlighted?: boolean
  ctaLabel?: string
  ctaHref?: string
}

export default function PricingCard({
  name,
  badge,
  setup,
  commission,
  features,
  highlighted = false,
  ctaLabel = 'Agendar auditoría gratis',
  ctaHref = 'https://wa.me/525642926243?text=Hola%2C%20quiero%20una%20auditor%C3%ADa%20gratuita%20con%20ZUBA',
}: PricingCardProps) {
  return (
    <div
      className={`relative flex flex-col rounded-2xl p-8 transition-transform duration-200 hover:-translate-y-1 ${
        highlighted
          ? 'bg-negro text-white shadow-2xl ring-2 ring-naranja'
          : 'bg-white text-negro shadow-md'
      }`}
    >
      {/* Badge */}
      {badge && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <span className="bg-naranja text-white text-xs font-bold uppercase tracking-wider px-4 py-1.5 rounded-full shadow-md whitespace-nowrap">
            {badge}
          </span>
        </div>
      )}

      {/* Plan name */}
      <h3
        className={`text-xs font-bold uppercase tracking-widest mb-3 ${
          highlighted ? 'text-naranja' : 'text-naranja'
        }`}
      >
        {name}
      </h3>

      {/* Pricing */}
      <div className="mb-1">
        <p
          className={`text-2xl font-black leading-tight ${
            highlighted ? 'text-white' : 'text-negro'
          }`}
        >
          {setup}
        </p>
        <p
          className={`text-sm font-semibold mt-1 ${
            highlighted ? 'text-naranja' : 'text-naranja-oscuro'
          }`}
        >
          {commission}
        </p>
      </div>

      {/* Divider */}
      <div
        className={`my-6 border-t ${
          highlighted ? 'border-white/10' : 'border-negro/10'
        }`}
      />

      {/* Features */}
      <ul className="flex flex-col gap-3 mb-8 flex-1">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-3">
            <svg
              className="flex-shrink-0 mt-0.5"
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <circle cx="9" cy="9" r="9" fill="#FF6B35" />
              <path
                d="M5 9L7.5 11.5L13 6"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span
              className={`text-sm leading-snug ${
                highlighted ? 'text-white/80' : 'text-negro/70'
              }`}
            >
              {feature}
            </span>
          </li>
        ))}
      </ul>

      {/* CTA */}
      <a
        href={ctaHref}
        target="_blank"
        rel="noopener noreferrer"
        className={`block text-center py-3.5 px-6 rounded-xl font-bold text-sm transition-all duration-200 ${
          highlighted
            ? 'bg-naranja text-white hover:bg-naranja-oscuro'
            : 'bg-negro text-white hover:bg-naranja'
        }`}
      >
        {ctaLabel}
      </a>
    </div>
  )
}
