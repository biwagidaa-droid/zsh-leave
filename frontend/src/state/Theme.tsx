import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Mode = "light" | "dark";
const STORAGE_KEY = "zsh-theme";
const THEME_COLOR: Record<Mode, string> = { light: "#0f4c5c", dark: "#0b1c21" };

const Ctx = createContext<{ mode: Mode; toggle: () => void }>({ mode: "light", toggle: () => undefined });

function readSaved(): Mode | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "dark" || saved === "light" ? saved : null;
  } catch {
    return null; // حالت خصوصی/مسدودبودن storage
  }
}

function systemMode(): Mode {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

/** پیش از رندر React صدا زده می‌شود تا چشمک (flash) پوسته‌ی اشتباه ایجاد نشود. */
export function applyInitialTheme(): void {
  document.documentElement.dataset.theme = readSaved() ?? systemMode();
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => readSaved() ?? systemMode());

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[mode]);
    try { localStorage.setItem(STORAGE_KEY, mode); } catch { /* ignore */ }
  }, [mode]);

  const value = useMemo(() => ({ mode, toggle: () => setMode((m) => (m === "light" ? "dark" : "light")) }), [mode]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme() {
  return useContext(Ctx);
}
