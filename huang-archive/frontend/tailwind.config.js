/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        rice: '#F7F4EB',
        parchment: '#FCFBF7',
        clay: '#E2D9C8',
        ink: '#262422',
        mute: '#6E685F',
        cinnabar: '#9E2A2B',
        celadon: '#2E5B70',
      },
      fontFamily: {
        song: ['"Songti SC"', '"Noto Serif SC"', 'STSong', 'SimSun', 'serif'],
        sans: ['"Noto Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      minHeight: {
        tap: '48px',
      },
    },
  },
  plugins: [],
}
