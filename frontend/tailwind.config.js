/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-body)', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      colors: {
        surface: {
          DEFAULT: '#0d0f14',
          raised: '#13161e',
          overlay: '#1a1e29',
          border: '#252a38',
        },
        brand: {
          DEFAULT: '#4f7cff',
          dim: '#3a5fd4',
          glow: 'rgba(79,124,255,0.25)',
        },
        accent: {
          green: '#1de9a4',
          amber: '#f5a623',
          red: '#ff4d6a',
        },
        ink: {
          DEFAULT: '#f0f2ff',
          muted: '#8891b0',
          faint: '#4a5068',
        },
      },
      boxShadow: {
        'glow-brand': '0 0 32px rgba(79,124,255,0.2)',
        'glow-green': '0 0 24px rgba(29,233,164,0.2)',
        'card': '0 2px 20px rgba(0,0,0,0.4)',
      },
      backgroundImage: {
        'grid-pattern': 'radial-gradient(circle, #252a38 1px, transparent 1px)',
        'brand-gradient': 'linear-gradient(135deg, #4f7cff 0%, #1de9a4 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'slide-up': 'slideUp 0.5s ease forwards',
        'fade-in': 'fadeIn 0.4s ease forwards',
      },
      keyframes: {
        slideUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
