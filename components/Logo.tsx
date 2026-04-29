import React from 'react'

interface LogoProps {
  /** Show only the icon (Z square), no wordmark */
  iconOnly?: boolean
  /** Size of the icon in px */
  size?: number
  /** Color of the wordmark text — defaults to #080808 */
  wordmarkColor?: string
}

export default function Logo({
  iconOnly = false,
  size = 40,
  wordmarkColor = '#080808',
}: LogoProps) {
  const radius = size * 0.2

  return (
    <div className="flex items-center gap-3" aria-label="ZUBA logo">
      {/* Z icon */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="zuba-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FF6B35" />
            <stop offset="100%" stopColor="#E85520" />
          </linearGradient>
          <clipPath id="zuba-clip">
            <rect width="40" height="40" rx={radius} ry={radius} />
          </clipPath>
        </defs>
        {/* Background */}
        <rect
          width="40"
          height="40"
          rx={radius}
          ry={radius}
          fill="url(#zuba-grad)"
        />
        {/* Bold Z */}
        <text
          x="20"
          y="29"
          textAnchor="middle"
          fontFamily="Inter, system-ui, sans-serif"
          fontWeight="900"
          fontSize="26"
          fill="#FFFFFF"
          letterSpacing="-1"
        >
          Z
        </text>
      </svg>

      {/* Wordmark */}
      {!iconOnly && (
        <span
          style={{ color: wordmarkColor }}
          className="text-2xl font-black tracking-tight leading-none select-none"
        >
          ZUBA
        </span>
      )}
    </div>
  )
}
