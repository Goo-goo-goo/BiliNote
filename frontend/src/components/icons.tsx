// 极简线性图标（内联 SVG，零外部依赖）
type IconProps = { size?: number }

function svgProps(size = 18) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
}

export function IconHome({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5.5 9.5V21h13V9.5" />
      <path d="M9.5 21v-6h5v6" />
    </svg>
  )
}

export function IconClock({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  )
}

export function IconNote({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
      <path d="M10 12h6M10 16h4" />
    </svg>
  )
}

export function IconFolder({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M4 6h5.5l2 2.5H20V19H4z" />
    </svg>
  )
}

export function IconCheck({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.5 12.5 11 15l4.5-5" />
    </svg>
  )
}

export function IconFlag({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M6 3v18" />
      <path d="M6 4.5h11l-2 4 2 4H6z" />
    </svg>
  )
}

export function IconReview({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H12v16H7.5A2.5 2.5 0 0 0 5 21.5z" />
      <path d="M19 5.5A2.5 2.5 0 0 0 16.5 3H12v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" />
    </svg>
  )
}

export function IconGear({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M4 8h9M17 8h3M4 16h3M11 16h9" />
      <circle cx="15" cy="8" r="2" />
      <circle cx="9" cy="16" r="2" />
    </svg>
  )
}

export function IconSun({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4" />
    </svg>
  )
}

export function IconMoon({ size }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z" />
    </svg>
  )
}

/** 品牌标记：圆角方块里的「字幕播放」符号 */
export function BrandMark({ size = 26 }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <rect width="24" height="24" rx="7" fill="var(--brand)" />
      <path d="M9.5 8.2 16 12l-6.5 3.8z" fill="#fff" />
      <rect x="6.5" y="17" width="11" height="1.6" rx="0.8" fill="var(--warn)" />
    </svg>
  )
}
