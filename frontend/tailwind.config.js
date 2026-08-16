/**
 * Hakk shared design system.
 *
 * Every screen inherits from here — no page restyles its own palette, type or
 * spacing. Powder green is the accent, not the canvas: it earns its place on
 * active states, key CTAs and status, while the base stays warm off-white.
 *
 * Colours resolve through CSS variables declared in src/index.css, which is
 * what makes the dark theme a single override there rather than a `dark:`
 * variant on every element in every page. The token names carry the meaning
 * (canvas, surface, ink, line); the theme decides what they resolve to.
 */

/** `<alpha-value>` keeps Tailwind's /opacity modifiers working through vars. */
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Warm off-white base in light; a warm near-black in dark.
        canvas: v('--c-canvas'),
        'canvas-sunk': v('--c-canvas-sunk'),
        surface: v('--c-surface'),
        'surface-warm': v('--c-surface-warm'),

        // Soft charcoal ink — never pure black, and never pure white in dark.
        ink: {
          DEFAULT: v('--c-ink'),
          soft: v('--c-ink-soft'),
          muted: v('--c-ink-muted'),
          faint: v('--c-ink-faint'),
          inverse: v('--c-ink-inverse'),
        },

        line: {
          DEFAULT: v('--c-line'),
          soft: v('--c-line-soft'),
          strong: v('--c-line-strong'),
        },

        // Powder green: the accent scale. In dark the scale is re-pointed so
        // that "100" still means "a quiet tinted background" and "800" still
        // means "text that reads on it" — otherwise every bg-powder-100 with
        // text-powder-900 on it would inverse into white-on-white.
        powder: {
          50: v('--c-powder-50'),
          100: v('--c-powder-100'),
          200: v('--c-powder-200'),
          300: v('--c-powder-300'),
          400: v('--c-powder-400'),
          500: v('--c-powder-500'),
          600: v('--c-powder-600'),
          700: v('--c-powder-700'),
          800: v('--c-powder-800'),
          900: v('--c-powder-900'),
        },

        // Muted, non-alarming status hues that sit with the sage.
        clay: {
          100: v('--c-clay-100'),
          300: v('--c-clay-300'),
          500: v('--c-clay-500'),
          700: v('--c-clay-700'),
        },
        rust: {
          100: v('--c-rust-100'),
          300: v('--c-rust-300'),
          500: v('--c-rust-500'),
          700: v('--c-rust-700'),
        },
      },

      fontFamily: {
        display: ['Fraunces', 'Georgia', 'Cambria', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },

      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.06em' }],
        display: ['clamp(2.4rem, 5vw, 3.6rem)', { lineHeight: '1.06', letterSpacing: '-0.025em' }],
        title: ['clamp(1.75rem, 3vw, 2.35rem)', { lineHeight: '1.15', letterSpacing: '-0.02em' }],
      },

      // Generous, non-cramped rhythm.
      spacing: {
        18: '4.5rem',
        22: '5.5rem',
        30: '7.5rem',
        38: '9.5rem',
      },
      maxWidth: {
        prose: '68ch',
        shell: '76rem',
      },

      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.25rem',
        '3xl': '1.75rem',
        '4xl': '2.25rem',
      },

      // Gently lifted, never boxed in or harshly dropped. Both the shadow colour
      // and its strength come from variables: a shadow tuned for ink-on-paper is
      // invisible on a dark canvas, so the dark theme deepens it rather than
      // dropping shadows altogether and flattening the whole page.
      boxShadow: {
        soft: '0 1px 2px rgb(var(--c-shadow) / calc(0.04 * var(--shadow-boost))), 0 1px 3px rgb(var(--c-shadow) / calc(0.03 * var(--shadow-boost)))',
        lift: '0 1px 2px rgb(var(--c-shadow) / calc(0.03 * var(--shadow-boost))), 0 12px 28px -14px rgb(var(--c-shadow) / calc(0.16 * var(--shadow-boost)))',
        float: '0 2px 4px rgb(var(--c-shadow) / calc(0.03 * var(--shadow-boost))), 0 24px 48px -20px rgb(var(--c-shadow) / calc(0.20 * var(--shadow-boost)))',
        inset: 'inset 0 1px 2px rgb(var(--c-shadow) / calc(0.05 * var(--shadow-boost)))',
        glow: '0 0 0 4px rgb(var(--c-powder-300) / 0.28)',
      },

      transitionTimingFunction: {
        gentle: 'cubic-bezier(0.32, 0.72, 0.28, 1)',
      },
      transitionDuration: {
        180: '180ms',
        220: '220ms',
      },

      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(16px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'draw-line': { from: { height: '0%' }, to: { height: '100%' } },
      },
      animation: {
        'fade-up': 'fade-up 520ms cubic-bezier(0.32,0.72,0.28,1) both',
        'fade-in': 'fade-in 400ms ease both',
        'scale-in': 'scale-in 220ms cubic-bezier(0.32,0.72,0.28,1) both',
        'slide-in-right': 'slide-in-right 300ms cubic-bezier(0.32,0.72,0.28,1) both',
        'pulse-soft': 'pulse-soft 2.4s ease-in-out infinite',
        shimmer: 'shimmer 1.8s infinite',
      },
    },
  },
  plugins: [],
};
