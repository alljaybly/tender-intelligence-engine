/**
 * LanguageContext
 *
 * Provides the current language and a method to change it.
 * Persists the user's language preference in localStorage.
 * Automatically restores the preference on page refresh.
 * Preloads locale data when the language changes.
 *
 * Usage:
 *   import { useLanguage } from '../context/LanguageContext';
 *   const { language, setLanguage, direction, isRTL } = useLanguage();
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  LANGUAGES,
  getLanguageConfig,
  type LanguageConfig,
} from '../i18n/config';
import {
  setCurrentLanguage,
  preloadLanguage,
  getCurrentDirection,
  isRTL as checkIsRTL,
} from '../i18n';

export interface LanguageContextType {
  /** Current language code (e.g. 'en', 'fr') */
  language: string;
  /** Full language config for the current language */
  languageConfig: LanguageConfig;
  /** Change the current language */
  setLanguage: (code: string) => Promise<void>;
  /** All available languages */
  availableLanguages: LanguageConfig[];
  /** Text direction for the current language */
  direction: 'ltr' | 'rtl';
  /** Whether the current language is RTL */
  isRTL: boolean;
  /** Whether locale data is currently loading */
  isLoading: boolean;
}

const LanguageContext = createContext<LanguageContextType | null>(null);

/**
 * Get the initial language from localStorage or default to English.
 */
function getInitialLanguage(): string {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored && LANGUAGES.some((lang) => lang.code === stored)) {
      return stored;
    }
  } catch {
    // localStorage unavailable — use default
  }
  return DEFAULT_LANGUAGE;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<string>(getInitialLanguage);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize: preload locale data for the initial language
  useEffect(() => {
    const initialLang = getInitialLanguage();
    setCurrentLanguage(initialLang);
    setLanguageState(initialLang);

    preloadLanguage(initialLang).catch((err) => {
      console.error('[LanguageContext] Failed to preload locale:', err);
    });
  }, []);

  const setLanguage = useCallback(async (code: string) => {
    // Validate the language code
    const config = LANGUAGES.find((lang) => lang.code === code);
    if (!config) {
      console.warn(`[LanguageContext] Unknown language code: ${code}`);
      return;
    }

    setIsLoading(true);

    try {
      // Preload locale data
      await preloadLanguage(code);

      // Update state
      setCurrentLanguage(code);
      setLanguageState(code);

      // Persist to localStorage
      try {
        localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
      } catch {
        // localStorage unavailable — preference won't persist
      }

      // Update document direction for RTL support
      document.documentElement.dir = config.direction;
      document.documentElement.lang = code;
    } catch (err) {
      console.error(`[LanguageContext] Failed to set language ${code}:`, err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const languageConfig = getLanguageConfig(language);
  const direction = getCurrentDirection();
  const isRTLValue = checkIsRTL();

  const value: LanguageContextType = {
    language,
    languageConfig,
    setLanguage,
    availableLanguages: LANGUAGES,
    direction,
    isRTL: isRTLValue,
    isLoading,
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}

export default LanguageContext;