/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Derived from the tellbooks.ir logo: cream/tile background, deep
        // red badge, dusty blue tile accent. Buyer side leans cream+maroon;
        // admin side leans in the dusty blue for a "workshop" feel.
        cream: {
          50: "#FFFDF9",
          100: "#FBF3E7",
          200: "#F5E7D3",
          300: "#EAD5B5",
        },
        maroon: {
          400: "#C4544A",
          500: "#A83E33",
          600: "#8C3128",
          700: "#6E251E",
        },
        dusty: {
          300: "#B7CBDC",
          400: "#93AFC7",
          500: "#7192AC",
          600: "#557894",
        },
        ink: {
          400: "#7A6C61",
          500: "#5A4C42",
          600: "#3F342C",
          700: "#2D251F",
        },
      },
      fontFamily: {
        sans: ["Vazirmatn", "Tahoma", "sans-serif"],
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [require("tailwindcss-rtl")],
}

