import type { Config } from "tailwindcss";

// RTL is structural (docs/architecture/stack.md). Use logical-property utilities only —
// ms-*, me-*, ps-*, pe-*, start-*, end-*. Never ml-*, mr-*, pl-*, pr-*, left-*, right-*.
// (Tailwind generates both physical and logical variants from the same margin/padding/inset
// core plugins, so this boundary is enforced by code review discipline, not a corePlugins
// toggle — disabling those plugins would remove the logical utilities too.) One stylesheet
// serves both directions; `dir` is set on <html> from the active locale, never per-component.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        arabic: ["IBM Plex Sans Arabic", "Noto Sans Arabic", "Cairo", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
