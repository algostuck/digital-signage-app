/** Decorative hero for the auth panel: a screen with a profile form and a
 * padlock — the same idea as the reference, drawn inline so it ships with
 * the bundle and inherits no third-party licence. Purely decorative, so it
 * is hidden from assistive tech. */
export function HeroIllustration() {
  return (
    <svg
      viewBox="0 0 520 380"
      className="h-auto w-full max-w-[460px]"
      aria-hidden
      focusable="false"
    >
      <defs>
        <linearGradient id="dsc-hero-blob" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.16" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0.04" />
        </linearGradient>
      </defs>

      {/* soft blob */}
      <path
        d="M78 214c-22-66 24-140 96-158 70-18 132 18 194 6 62-12 118 30 118 96 0 74-58 128-136 146-78 18-160 12-214-22-30-19-50-40-58-68z"
        fill="url(#dsc-hero-blob)"
      />

      {/* leaves */}
      <g fill="#5EEAD4" opacity="0.85">
        <path d="M84 246c-30-38-6-96 44-104-8 44 4 84-44 104z" />
        <path d="M456 256c26-42-6-100-58-106 12 46-4 88 58 106z" />
      </g>
      <g fill="#99F6E4" opacity="0.75">
        <path d="M112 300c-16-28 4-66 42-70-6 30 2 58-42 70z" />
        <path d="M418 300c16-30-6-70-46-74 8 32 0 62 46 74z" />
      </g>

      {/* monitor */}
      <rect x="150" y="82" width="230" height="160" rx="12" fill="#FFFFFF" />
      <rect x="150" y="82" width="230" height="160" rx="12" fill="none" stroke="#1D4ED8" strokeWidth="5" />
      <rect x="248" y="242" width="34" height="26" fill="#1D4ED8" />
      <rect x="205" y="266" width="120" height="10" rx="5" fill="#1D4ED8" />

      {/* avatar */}
      <circle cx="265" cy="128" r="22" fill="#DBEAFE" />
      <circle cx="265" cy="121" r="9" fill="#3B82F6" />
      <path d="M247 145c4-10 12-14 18-14s14 4 18 14" fill="#3B82F6" />

      {/* fields + button */}
      <rect x="196" y="162" width="138" height="12" rx="6" fill="#C7D2FE" />
      <rect x="196" y="184" width="138" height="12" rx="6" fill="#C7D2FE" />
      <g fill="#1E3A8A">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <circle key={i} cx={210 + i * 12} cy={190} r="2.6" />
        ))}
      </g>
      <rect x="236" y="206" width="58" height="16" rx="8" fill="#3B82F6" />

      {/* padlock */}
      <rect x="352" y="228" width="72" height="62" rx="12" fill="#F97316" />
      <path
        d="M366 228v-18a22 22 0 0 1 44 0v18"
        fill="none"
        stroke="#FB923C"
        strokeWidth="10"
        strokeLinecap="round"
      />
      <circle cx="388" cy="254" r="8" fill="#7C2D12" />
      <rect x="384" y="256" width="8" height="16" rx="3" fill="#7C2D12" />

      {/* key */}
      <g transform="rotate(-32 120 250)">
        <circle cx="120" cy="250" r="14" fill="none" stroke="#FFFFFF" strokeWidth="7" />
        <rect x="132" y="246" width="60" height="8" rx="4" fill="#FFFFFF" />
        <rect x="170" y="254" width="8" height="12" fill="#FFFFFF" />
        <rect x="184" y="254" width="8" height="16" fill="#FFFFFF" />
      </g>

      {/* ground */}
      <ellipse cx="262" cy="318" rx="170" ry="14" fill="#FFFFFF" opacity="0.14" />
    </svg>
  );
}
