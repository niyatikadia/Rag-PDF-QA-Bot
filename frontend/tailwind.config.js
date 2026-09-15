/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  // The `brand` palette that used to live here was byte-identical to Tailwind's
  // own blue-50/500/600/700 and was referenced nowhere in src/ — removed Day 9.
  theme: {
    extend: {},
  },
  plugins: [],
}
