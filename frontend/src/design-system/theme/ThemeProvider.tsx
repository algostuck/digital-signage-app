import { App as AntApp, ConfigProvider } from "antd";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { buildTheme, type ThemeMode } from "./buildTheme";

const STORAGE_KEY = "dsc.theme";

interface ThemeContextValue {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function initialMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Private mode / storage disabled — fall through to the OS setting.
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Owns the light/dark mode and feeds antd's algorithm + tokens. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(initialMode);

  const setMode = useCallback((next: ThemeMode) => {
    // Suppress colour transitions for the swap itself: cross-fading every
    // surface at once makes text pass through its own background colour
    // and briefly become unreadable. An instant swap also reads as more
    // deliberate.
    const root = document.documentElement;
    root.classList.add("theme-switching");
    window.setTimeout(() => root.classList.remove("theme-switching"), 220);
    setModeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Persistence is a convenience; the session still themes correctly.
    }
  }, []);

  // Keeps native UI (scrollbars, form controls, autofill) in step with
  // the app theme, and lets the small body-background rule react.
  useEffect(() => {
    document.documentElement.dataset.theme = mode;
    document.documentElement.style.colorScheme = mode;
  }, [mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, setMode, toggle: () => setMode(mode === "dark" ? "light" : "dark") }),
    [mode, setMode],
  );

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider theme={buildTheme(mode)}>
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useThemeMode(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useThemeMode must be used within ThemeProvider");
  return ctx;
}
