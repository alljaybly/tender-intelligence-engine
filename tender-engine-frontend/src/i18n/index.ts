/**
 * Translation Service (i18n)
 *
 * Lightweight centralized translation service.
 *
 * Usage:
 *   import { t } from '../i18n';
 *   t('common.nav.home')           // → "Home"
 *   t('common.warnings.warnings', { count: 3 })  // → "3 Warnings"
 *   t('demo.hero_title')            // → "See exactly what..."
 *
 * Features:
 *   - Dot-notation key access (e.g. "nav.home")
 *   - Interpolation with {variable} syntax
 *   - Automatic fallback to English for untranslated keys
 *   - Namespace-based file loading (common, landing, dashboard, demo, auth, errors)
 *   - No spread of translation logic across components
 */

import { DEFAULT_LANGUAGE, getLanguageConfig } from './config';

/**
 * Map of available locale namespaces.
 * Each namespace corresponds to a JSON file in src/locales/{lang}/{namespace}.json
 */
const LOCALE_NAMESPACES = [
  'common',
  'landing',
  'dashboard',
  'demo',
  'auth',
  'errors',
] as const;

export type LocaleNamespace = (typeof LOCALE_NAMESPACES)[number];

/**
 * Cache for loaded locale data.
 * Structure: cache[languageCode][namespace] = Record<string, unknown>
 */
const cache: Record<string, Record<string, Record<string, unknown>>> = {};

/**
 * Load a locale file from the JSON bundle.
 * Uses Vite's JSON import — files are bundled at build time.
 */
async function loadLocale(
  languageCode: string,
  namespace: LocaleNamespace,
): Promise<Record<string, unknown>> {
  try {
    // Dynamic import of locale files
    const module = await import(`../locales/${languageCode}/${namespace}.json`);
    return module.default ?? module;
  } catch {
    // Fall back to English if the locale file doesn't exist
    if (languageCode !== DEFAULT_LANGUAGE) {
      return loadLocale(DEFAULT_LANGUAGE, namespace);
    }
    return {};
  }
}

/**
 * Ensure a locale namespace is loaded for a given language.
 * Uses cached data if already loaded.
 */
async function ensureLocale(
  languageCode: string,
  namespace: LocaleNamespace,
): Promise<Record<string, unknown>> {
  if (!cache[languageCode]) {
    cache[languageCode] = {};
  }

  if (!cache[languageCode][namespace]) {
    cache[languageCode][namespace] = await loadLocale(languageCode, namespace);
  }

  return cache[languageCode][namespace];
}

/**
 * Get a nested value from an object using a dot-notation path.
 * E.g., getNested({ a: { b: 'c' } }, 'a.b') → 'c'
 */
function getNested(
  obj: Record<string, unknown>,
  path: string,
): unknown {
  return path.split('.').reduce<unknown>((current, key) => {
    if (current && typeof current === 'object' && key in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

/**
 * Interpolate {variable} placeholders in a string.
 */
function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;

  return template.replace(/\{(\w+)\}/g, (_match, key) => {
    const value = params[key];
    return value != null ? String(value) : `{${key}}`;
  });
}

/**
 * The currently active language code.
 * Updated by LanguageContext when the user changes language.
 * Defaults to English until context initializes.
 */
let currentLanguage = DEFAULT_LANGUAGE;

/**
 * Set the active language for the translation service.
 * Called by LanguageContext on initialization and language change.
 */
export function setCurrentLanguage(code: string): void {
  currentLanguage = code;
}

/**
 * Get the currently active language code.
 */
export function getCurrentLanguage(): string {
  return currentLanguage;
}

/**
 * Translate a key to the current language.
 *
 * Supports dot-notation: "common.nav.home", "demo.hero_title"
 * Supports interpolation: t("common.warnings.warnings", { count: 3 })
 *
 * If the key is not found in the current language, falls back to English.
 * If still not found, returns the key itself as a last resort.
 *
 * @param key - Dot-notation key like "common.nav.home"
 * @param params - Optional interpolation parameters
 * @returns The translated string
 */
export function t(key: string, params?: Record<string, string | number>): string {
  // Parse key into namespace and path
  const parts = key.split('.');
  const namespace = parts[0] as LocaleNamespace;
  const path = parts.slice(1).join('.');

  // Get the current language's translations
  const langData = cache[currentLanguage]?.[namespace];
  const fallbackData = currentLanguage !== DEFAULT_LANGUAGE
    ? cache[DEFAULT_LANGUAGE]?.[namespace]
    : undefined;

  // Try current language first, then fallback to English
  let value = langData ? getNested(langData, path) : undefined;

  // Fallback to English if not found in current language
  if (value === undefined && fallbackData) {
    value = getNested(fallbackData, path);
  }

  // If string, interpolate and return
  if (typeof value === 'string') {
    return interpolate(value, params);
  }

  // If array, stringify (for features lists etc.)
  if (Array.isArray(value)) {
    return value.join(', ');
  }

  // Key not found — return key as last resort
  return key;
}

/**
 * Preload all locale namespaces for a given language.
 * This ensures translations are ready before render.
 *
 * Called by LanguageContext on initialization and language change.
 */
export async function preloadLanguage(languageCode: string): Promise<void> {
  const loadPromises = LOCALE_NAMESPACES.map((ns) => ensureLocale(languageCode, ns));

  // Also ensure English is loaded for fallback
  if (languageCode !== DEFAULT_LANGUAGE) {
    loadPromises.push(...LOCALE_NAMESPACES.map((ns) => ensureLocale(DEFAULT_LANGUAGE, ns)));
  }

  await Promise.all(loadPromises);
}

/**
 * Get the direction (ltr/rtl) for the current language.
 * RTL support is prepared but unused until RTL languages are added.
 */
export function getCurrentDirection(): 'ltr' | 'rtl' {
  return getLanguageConfig(currentLanguage).direction;
}

/**
 * Check if the current language is RTL.
 */
export function isRTL(): boolean {
  return getCurrentDirection() === 'rtl';
}