import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ZUBA — Delivery que vende solo.',
  description:
    'Consultoría estratégica que optimiza restaurantes en Uber Eats, DiDi Food y Rappi en México. Auditoría, optimización y resultados reales.',
  keywords: 'restaurante, Uber Eats, DiDi Food, Rappi, optimización, delivery, México, consultoría',
  openGraph: {
    title: 'ZUBA — Delivery que vende solo.',
    description:
      'Consultoría estratégica que optimiza restaurantes en Uber Eats, DiDi Food y Rappi en México.',
    url: 'https://zubamx.vercel.app',
    siteName: 'ZUBA',
    locale: 'es_MX',
    type: 'website',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es-MX">
      <body>{children}</body>
    </html>
  )
}
