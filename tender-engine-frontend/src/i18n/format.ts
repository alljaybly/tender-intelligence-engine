/**
 * Formatting Utilities (i18n)
 *
 * Reusable formatting helpers that respect the currently selected locale.
 *
 * Supports:
 *   - Dates
 *   - Times
 *   - Numbers
 *   - Currency (formatting only — no conversion)
 *   - Percentages
 *
 * All functions use the locale corresponding to the current language,
 * so switching languages automatically updates formatting.
 *
 * Usage:
 *   import { formatCurrency, formatDate, formatNumber, formatPercent } from '../i18n/format';
 *   formatCurrency(1500000)   // → "R1 500 000"
 *   formatDate(new Date())     // → "15 Jan 2026"
 *   formatNumber(1234567.89)  // → "1 234 567,89"
 *   formatPercent(0.85)       // → "85%"
 */

import { getLocaleCode } from './config';
import { getCurrentLanguage } from './index';

/**
 * Get the Intl locale code for the current language.
 */
function getEffectiveLocale(): string {
  return getLocaleCode(getCurrentLanguage());
}

/**
 * Format a number with locale-aware grouping and decimals.
 *
 * @param value - The number to format
 * @param options - Intl.NumberFormat options
 */
export function formatNumber(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  const locale = getEffectiveLocale();
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
    ...options,
  }).format(value);
}

/**
 * Format a currency amount.
 * Uses ZAR by default (South African Rand).
 * Does NOT perform currency conversion — only formatting.
 *
 * @param value - The amount to format
 * @param currency - ISO 4217 currency code (default: 'ZAR')
 * @param options - Additional Intl.NumberFormat options
 */
export function formatCurrency(
  value: number,
  currency: string = 'ZAR',
  options?: Intl.NumberFormatOptions,
): string {
  const locale = getEffectiveLocale();
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    ...options,
  }).format(value);
}

/**
 * Format a percentage value.
 * E.g., 0.85 → "85%", 0.1234 → "12,3%"
 *
 * @param value - The decimal value (0-1)
 * @param options - Additional Intl.NumberFormat options
 */
export function formatPercent(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  const locale = getEffectiveLocale();
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
    ...options,
  }).format(value);
}

/**
 * Format a date.
 *
 * @param date - Date object, ISO string, or timestamp
 * @param options - Intl.DateTimeFormat options
 */
export function formatDate(
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions,
): string {
  const locale = getEffectiveLocale();
  const dateObj = typeof date === 'object' ? date : new Date(date);

  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    ...options,
  }).format(dateObj);
}

/**
 * Format a time.
 *
 * @param date - Date object, ISO string, or timestamp
 * @param options - Intl.DateTimeFormat options
 */
export function formatTime(
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions,
): string {
  const locale = getEffectiveLocale();
  const dateObj = typeof date === 'object' ? date : new Date(date);

  return new Intl.DateTimeFormat(locale, {
    hour: '2-digit',
    minute: '2-digit',
    ...options,
  }).format(dateObj);
}

/**
 * Format a date and time together.
 *
 * @param date - Date object, ISO string, or timestamp
 * @param options - Intl.DateTimeFormat options
 */
export function formatDateTime(
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions,
): string {
  const locale = getEffectiveLocale();
  const dateObj = typeof date === 'object' ? date : new Date(date);

  return new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    ...options,
  }).format(dateObj);
}

/**
 * Format a number as a compact representation (e.g., 1 500 → "1.5k").
 * Useful for dashboard metrics.
 *
 * @param value - The number to format
 * @param options - Additional Intl.NumberFormat options
 */
export function formatCompact(
  value: number,
  options?: Intl.NumberFormatOptions,
): string {
  const locale = getEffectiveLocale();
  return new Intl.NumberFormat(locale, {
    notation: 'compact',
    compactDisplay: 'short',
    maximumFractionDigits: 1,
    ...options,
  }).format(value);
}

/**
 * Format a duration in months to a human-readable string.
 * E.g., 18 → "18 mo", 6 → "6 mo"
 *
 * @param months - Number of months
 * @param label - The unit label (defaults to "mo")
 */
export function formatDuration(months: number, label: string = 'mo'): string {
  return `${months} ${label}`;
}