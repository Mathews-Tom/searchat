/** Alpine.js theme store — manages light/dark/auto theme switching. */

import type { ThemeMode } from "@app-types/api";

interface ThemeTokens {
  [key: string]: string;
}

const LIGHT_TOKENS: ThemeTokens = {
  "--bg-base": "240 20% 97%",
  "--bg-elevated": "0 0% 100%",
  "--bg-glass": "0 0% 100% / 0.55",
  "--bg-glass-hover": "0 0% 100% / 0.72",
  "--bg-glass-active": "0 0% 100% / 0.85",
  "--bg-surface": "220 14% 96%",
  "--bg-surface-hover": "220 14% 93%",
  "--bg-overlay": "220 20% 96% / 0.8",
  "--border-glass": "0 0% 100% / 0.6",
  "--border-subtle": "220 13% 91%",
  "--border-focus": "221 83% 53%",
  "--text-primary": "220 14% 10%",
  "--text-secondary": "220 9% 43%",
  "--text-tertiary": "220 9% 60%",
  "--text-inverse": "0 0% 100%",
  "--accent": "221 83% 53%",
  "--accent-hover": "221 83% 47%",
  "--accent-subtle": "221 83% 53% / 0.08",
  "--accent-glow": "221 83% 53% / 0.15",
  "--success": "142 71% 45%",
  "--warning": "38 92% 50%",
  "--danger": "0 72% 51%",
  "--danger-subtle": "0 72% 51% / 0.08",
  "--shadow-sm":
    "0 1px 2px hsl(220 14% 10% / 0.04), 0 1px 3px hsl(220 14% 10% / 0.03)",
  "--shadow-md":
    "0 4px 6px hsl(220 14% 10% / 0.04), 0 2px 4px hsl(220 14% 10% / 0.03)",
  "--shadow-lg":
    "0 10px 25px hsl(220 14% 10% / 0.06), 0 4px 10px hsl(220 14% 10% / 0.04)",
  "--shadow-glass":
    "0 8px 32px hsl(220 14% 10% / 0.06), inset 0 1px 0 hsl(0 0% 100% / 0.6)",
  "--blur-glass": "20px",
  "--blur-bg": "40px",
  "--noise-opacity": "0.015",
  "--scrollbar-track": "220 14% 96%",
  "--scrollbar-thumb": "220 9% 82%",
  "--code-bg": "220 14% 96%",
};

const DARK_TOKENS: ThemeTokens = {
  "--bg-base": "224 25% 8%",
  "--bg-elevated": "224 22% 12%",
  "--bg-glass": "224 22% 14% / 0.6",
  "--bg-glass-hover": "224 22% 16% / 0.72",
  "--bg-glass-active": "224 22% 18% / 0.85",
  "--bg-surface": "224 20% 14%",
  "--bg-surface-hover": "224 20% 18%",
  "--bg-overlay": "224 25% 8% / 0.85",
  "--border-glass": "224 15% 22% / 0.6",
  "--border-subtle": "224 15% 20%",
  "--border-focus": "217 91% 60%",
  "--text-primary": "220 14% 95%",
  "--text-secondary": "220 9% 65%",
  "--text-tertiary": "220 9% 46%",
  "--text-inverse": "220 14% 10%",
  "--accent": "217 91% 60%",
  "--accent-hover": "217 91% 67%",
  "--accent-subtle": "217 91% 60% / 0.1",
  "--accent-glow": "217 91% 60% / 0.12",
  "--success": "142 71% 45%",
  "--warning": "38 92% 50%",
  "--danger": "0 72% 55%",
  "--danger-subtle": "0 72% 55% / 0.1",
  "--shadow-sm":
    "0 1px 2px hsl(0 0% 0% / 0.2), 0 1px 3px hsl(0 0% 0% / 0.15)",
  "--shadow-md":
    "0 4px 6px hsl(0 0% 0% / 0.2), 0 2px 4px hsl(0 0% 0% / 0.15)",
  "--shadow-lg":
    "0 10px 25px hsl(0 0% 0% / 0.3), 0 4px 10px hsl(0 0% 0% / 0.2)",
  "--shadow-glass":
    "0 8px 32px hsl(0 0% 0% / 0.25), inset 0 1px 0 hsl(0 0% 100% / 0.04)",
  "--blur-glass": "20px",
  "--blur-bg": "40px",
  "--noise-opacity": "0.03",
  "--scrollbar-track": "224 20% 12%",
  "--scrollbar-thumb": "224 15% 26%",
  "--code-bg": "224 20% 10%",
};

const THEME_TOKENS: Record<string, ThemeTokens> = {
  light: LIGHT_TOKENS,
  dark: DARK_TOKENS,
};

function resolve(mode: ThemeMode): "light" | "dark" {
  if (mode === "auto") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return mode;
}

function applyTokens(resolved: "light" | "dark"): void {
  const root = document.documentElement;
  root.setAttribute("data-theme", resolved);
  const tokens = THEME_TOKENS[resolved];
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(key, value);
  }
}

export const themeStore = {
  mode: "auto" as ThemeMode,
  resolved: "dark" as "light" | "dark",

  init() {
    let saved = (localStorage.getItem("theme-preference") || "auto") as string;
    // Migrate legacy values
    if (["future", "system"].includes(saved)) saved = "dark";
    if (saved === "bare") saved = "light";
    if (!["light", "dark", "auto"].includes(saved)) saved = "auto";

    this.mode = saved as ThemeMode;
    this.resolved = resolve(this.mode);
    applyTokens(this.resolved);
    localStorage.setItem("theme-preference", this.mode);

    // Listen for system preference changes
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", () => {
        if (this.mode === "auto") {
          this.resolved = resolve("auto");
          applyTokens(this.resolved);
        }
      });
  },

  set(mode: ThemeMode) {
    this.mode = mode;
    this.resolved = resolve(mode);
    applyTokens(this.resolved);
    localStorage.setItem("theme-preference", mode);
  },
};
