import en from "./locales/en.json";

export type LocaleKey = keyof typeof en;

const catalogs: Record<string, Record<string, string>> = {
  en: en as Record<string, string>,
};

let activeLocale = "en";

/** Localization seam — swap catalog by BCP-47 tag when more locales ship. */
export function setLocale(locale: string): void {
  if (catalogs[locale]) activeLocale = locale;
}

export function t(key: LocaleKey | string, fallback?: string): string {
  const catalog = catalogs[activeLocale] ?? catalogs.en;
  return catalog[key] ?? fallback ?? key;
}

export function availableLocales(): string[] {
  return Object.keys(catalogs);
}
