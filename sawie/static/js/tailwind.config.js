/* Tailwind design tokens for SAWIE.
   The CDN build reads this at runtime. For production run the Tailwind CLI
   against the same token set — see docs/DEPLOYMENT.md. */
tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        /* Natural agriculture palette — warm olive/leaf greens instead of the
           old flat emerald. Feels earthy and organic rather than "tech green". */
        brand: {
          50:  '#F2F6EC',
          100: '#E1EBD1',
          200: '#C4D8A9',
          300: '#9FC077',
          400: '#7BA84E',
          500: '#5C8A34',
          600: '#4A7129',
          700: '#3B5A22',
          800: '#2F471C',
          900: '#233619',
        },
        accent: {
          200: '#DCE9C4',
          300: '#BFD79A',
          400: '#9DC46A',
          500: '#7BA84E',
        },
        /* Warm soil tones for small highlights (badges, harvest chips) */
        soil: {
          100: '#EDE4D3',
          300: '#C9AE86',
          500: '#9C7B4F',
          700: '#6B5233',
        },
        canvas: '#F6F7F3',
        forest: '#14261A',
      },
      boxShadow: {
        card: '0 1px 2px rgba(28, 40, 24, 0.04), 0 1px 3px rgba(28, 40, 24, 0.06)',
        lift: '0 12px 32px -12px rgba(28, 40, 24, 0.22)',
        'inner-glow': 'inset 0 0 0 1px rgba(255,255,255,0.06)',
      },
      borderRadius: { xl: '0.875rem', '2xl': '1.125rem' },
    },
  },
};
