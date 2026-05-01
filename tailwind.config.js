/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.py",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        paper:          "#FBF9F4",
        "paper-2":      "#F5F1E8",
        "paper-3":      "#EDE7DA",
        rule:           "#E5DFCF",
        "rule-strong":  "#D4CCB8",
        ink:            "#1A1816",
        "ink-2":        "#3A352E",
        "ink-3":        "#6B655B",
        "ink-4":        "#948D80",
        gold:           "#B8862C",
        "gold-deep":    "#8C6520",
        "review-bg":    "#FBF7E8",
        "review-rule":  "#E8DCA8",
        danger:         "#A03A2A",
        ok:             "#4A6B3A",
        info:           "#3A5A7A",
      },
      fontFamily: {
        serif: ["Newsreader", "Georgia", "serif"],
        sans:  ["Public Sans", "system-ui", "sans-serif"],
        mono:  ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
}
