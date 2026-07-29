/**
 * i18n Configuration
 *
 * Defines supported languages and their metadata.
 * This is the single source of truth for all locales.
 */

export interface LanguageConfig {
  code: string;
  label: string;
  flag: string;
  direction: 'ltr' | 'rtl';
}

/**
 * Supported languages.
 * English is the default (fallback) language.
 *
 * When adding a new language:
 * 1. Add its entry here
 * 2. Create corresponding locale files in src/locales/{code}/
 * 3. Add translations
 */
export const LANGUAGES: LanguageConfig[] = [
  { code: 'en', label: 'English', flag: '🇬🇧', direction: 'ltr' },
  { code: 'fr', label: 'Français', flag: '🇫🇷', direction: 'ltr' },
  { code: 'es', label: 'Español', flag: '🇪🇸', direction: 'ltr' },
  { code: 'de', label: 'Deutsch', flag: '🇩🇪', direction: 'ltr' },
  { code: 'pt', label: 'Português', flag: '🇵🇹', direction: 'ltr' },
];

/**
 * Default language code.
 * Always English — all other languages fall back to English for untranslated keys.
 */
export const DEFAULT_LANGUAGE = 'en';

/**
 * localStorage key for persisting language preference.
 */
export const LANGUAGE_STORAGE_KEY = 'tender-engine-language';

/**
 * Supported locale codes for formatting (dates, numbers, currency).
 */
export const LOCALE_MAP: Record<string, string> = {
  en: 'en-ZA',
  fr: 'fr-FR',
  es: 'es-ES',
  de: 'de-DE',
  pt: 'pt-PT',
};

/**
 * Get the display locale for a given language code.
 * Falls back to en-ZA if the language is not mapped.
 */
export function getLocaleCode(languageCode: string): string {
  return LOCALE_MAP[languageCode] ?? LOCALE_MAP[DEFAULT_LANGUAGE];
}

/**
 * Get language config by code.
 */
export function getLanguageConfig(code: string): LanguageConfig {
  return LANGUAGES.find((lang) => lang.code === code) ?? LANGUAGES[0];
}