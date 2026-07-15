export type ContrastMode = "default" | "high";
export type DensityMode = "comfortable" | "compact";

export interface ThemePrefs {
  contrast: ContrastMode;
  density: DensityMode;
  /** When true, force reduced motion regardless of OS. */
  reduceMotion: boolean;
}

const STORAGE_KEY = "brainflow.themePrefs";

export const DEFAULT_THEME: ThemePrefs = {
  contrast: "default",
  density: "comfortable",
  reduceMotion: false,
};

export function loadThemePrefs(): ThemePrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_THEME };
    const parsed = JSON.parse(raw) as Partial<ThemePrefs>;
    return {
      contrast: parsed.contrast === "high" ? "high" : "default",
      density: parsed.density === "compact" ? "compact" : "comfortable",
      reduceMotion: Boolean(parsed.reduceMotion),
    };
  } catch {
    return { ...DEFAULT_THEME };
  }
}

export function saveThemePrefs(prefs: ThemePrefs): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

/** Apply semantic token hooks on `<html>` for CSS + a11y consumers. */
export function applyThemePrefs(prefs: ThemePrefs): void {
  const root = document.documentElement;
  root.dataset.contrast = prefs.contrast;
  root.dataset.density = prefs.density;
  const osReduce =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  root.dataset.reducedMotion = prefs.reduceMotion || osReduce ? "true" : "false";
}

export function watchSystemReducedMotion(onChange: () => void): () => void {
  const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  if (!mq) return () => undefined;
  const handler = () => onChange();
  mq.addEventListener("change", handler);
  return () => mq.removeEventListener("change", handler);
}
