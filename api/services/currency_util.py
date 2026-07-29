"""
Currency utility module for Tender Engine.

Handles currency normalization and formatting according to detected evidence.
Does NOT perform exchange rate conversion.
Never defaults to ZAR. Unknown is better than incorrect.
"""
from __future__ import annotations
import re
import logging
from typing import Dict, Optional, Tuple, Union

from ..schemas.currency import CurrencyEvidence

logger = logging.getLogger(__name__)

# ISO 4217 currency locale formatting rules
CURRENCY_LOCALE: Dict[str, Dict[str, str]] = {
    "ZAR": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "USD": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "EUR": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "GBP": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "DKK": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "NOK": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "SEK": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "CHF": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "CAD": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "AUD": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "NZD": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "JPY": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "AED": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "SAR": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "QAR": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "NGN": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "KES": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "EGP": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "GHS": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "MAD": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "TZS": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "UGX": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "ZMW": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "BWP": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "MUR": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "NAD": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "LSL": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "SZL": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "CNY": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "INR": {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"},
    "BRL": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "prefix"},
    "RUB": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "TRY": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
    "PLN": {"decimal_separator": ",", "thousand_separator": ".", "symbol_position": "suffix"},
}

# Default locale for unknown currencies (comma thousand, dot decimal)
DEFAULT_LOCALE = {"decimal_separator": ".", "thousand_separator": ",", "symbol_position": "prefix"}


class CurrencyUtil:
    """Utility class for deterministic currency operations."""

    # Symbols for display - populated lazily at first access
    _symbols_loaded: bool = False
    CURRENCY_SYMBOLS: Dict[str, str] = {}

    @classmethod
    def _ensure_symbols(cls) -> None:
        """Lazy-load currency symbols to avoid circular import at class definition time."""
        if not cls._symbols_loaded:
            from .currency_detector import CURRENCY_REGISTRY
            cls.CURRENCY_SYMBOLS = {
                code: info.get("symbol", code)
                for code, info in CURRENCY_REGISTRY.items()
            }
            cls._symbols_loaded = True

    @classmethod
    def normalize_currency(
        cls,
        value: Union[str, int, float, None],
        currency_code: Optional[str] = None,
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Normalize a currency value to a float and detect currency code if possible.

        Args:
            value: The currency value to normalize (string, int, float, or None).
            currency_code: Optional known currency code (ISO 4217).

        Returns:
            Tuple of (normalized_float_value, detected_currency_code).
            Returns (None, None) if value cannot be normalized.
        """
        if value is None:
            return (None, currency_code)

        if isinstance(value, (int, float)):
            return (float(value), currency_code)

        # If value is a string, try to parse it
        normalized_str: str = str(value).strip()
        if not normalized_str:
            return (None, currency_code)

        detected_currency: Optional[str] = currency_code

        # Try to detect currency from the string using the full registry
        cls._ensure_symbols()
        for code, symbol in cls.CURRENCY_SYMBOLS.items():
            if symbol and symbol in normalized_str:
                detected_currency = code
                break
            if code in normalized_str.upper():
                detected_currency = code
                break

        # Clean the string to extract just the number
        cleaned_str: str = re.sub(r"[^0-9.,]", "", normalized_str)

        # Handle cases like "1,234.56" or "1.234,56"
        has_comma: bool = "," in cleaned_str
        has_dot: bool = "." in cleaned_str

        decimal_sep: Optional[str] = None
        thousand_sep: Optional[str] = None

        if has_comma and has_dot:
            comma_pos = cleaned_str.rfind(",")
            dot_pos = cleaned_str.rfind(".")
            if comma_pos > dot_pos:
                decimal_sep = ","
                thousand_sep = "."
            else:
                decimal_sep = "."
                thousand_sep = ","
        elif has_comma:
            if cleaned_str.count(",") > 1:
                thousand_sep = ","
                decimal_sep = "."
            else:
                decimal_sep = ","
        elif has_dot:
            if cleaned_str.count(".") > 1:
                thousand_sep = "."
                decimal_sep = ","
            else:
                decimal_sep = "."
        else:
            decimal_sep = "."

        # Apply cleaning
        if thousand_sep:
            cleaned_str = cleaned_str.replace(thousand_sep, "")
        if decimal_sep and decimal_sep != ".":
            cleaned_str = cleaned_str.replace(decimal_sep, ".")

        try:
            normalized_float: float = float(cleaned_str)
            return (normalized_float, detected_currency)
        except ValueError:
            logger.warning(f"[CURRENCY_UTIL] Could not normalize value: {value}")
            return (None, detected_currency)

    @classmethod
    def format_currency(
        cls,
        value: Union[int, float, None],
        currency_code: Optional[str] = None,
        include_symbol: bool = True,
        decimal_places: int = 2,
    ) -> str:
        """
        Format a currency value according to the jurisdiction's conventions.

        Args:
            value: The numeric value to format (int, float, or None).
            currency_code: ISO 4217 currency code (optional).
            include_symbol: Whether to include the currency symbol (default True).
            decimal_places: Number of decimal places to display (default 2).

        Returns:
            Formatted currency string. Returns "—" if value is None.
            Returns "Unknown currency" if no currency code provided.
        """
        if value is None:
            return "—"

        if not currency_code:
            # No detected currency — just format the number
            formatted_number: str = f"{value:,.{decimal_places}f}"
            return formatted_number

        # Get locale settings (or default)
        locale = CURRENCY_LOCALE.get(currency_code, DEFAULT_LOCALE)

        # Format the number part
        formatted_number: str = f"{value:.{decimal_places}f}"

        # Split into integer and decimal parts
        if "." in formatted_number:
            integer_part, decimal_part = formatted_number.split(".", 1)
        else:
            integer_part, decimal_part = formatted_number, ""

        # Add thousand separators
        reversed_integer: str = integer_part[::-1]
        chunks = []
        for i in range(0, len(reversed_integer), 3):
            chunks.append(reversed_integer[i:i + 3])
        formatted_integer: str = locale["thousand_separator"].join(chunks)[::-1]

        # Combine integer and decimal parts
        if decimal_part:
            full_number = f"{formatted_integer}{locale['decimal_separator']}{decimal_part}"
        else:
            full_number = formatted_integer

        # Add currency symbol
        if include_symbol:
            symbol = cls.CURRENCY_SYMBOLS.get(currency_code, currency_code)
            if locale.get("symbol_position", "prefix") == "prefix":
                return f"{symbol}{full_number}"
            else:
                return f"{full_number}{symbol}"
        else:
            return full_number

    @classmethod
    def format_currency_with_evidence(
        cls,
        value: Union[int, float, None],
        currency_evidence: Optional[CurrencyEvidence],
        include_symbol: bool = True,
        decimal_places: int = 2,
    ) -> str:
        """
        Format a currency value using CurrencyEvidence.

        If no currency evidence is available, formats as plain number with
        a note that currency is unknown.

        Args:
            value: The numeric value to format.
            currency_evidence: CurrencyEvidence object from detection.
            include_symbol: Whether to include the currency symbol.
            decimal_places: Number of decimal places.

        Returns:
            Formatted currency string.
        """
        if value is None:
            return "—"

        if not currency_evidence or not currency_evidence.is_detected:
            # No detected currency — format number with unknown note
            formatted = f"{value:,.{decimal_places}f}"
            return formatted

        return cls.format_currency(
            value=value,
            currency_code=currency_evidence.currency_code,
            include_symbol=include_symbol,
            decimal_places=decimal_places,
        )


# Convenience exports
normalize_currency = CurrencyUtil.normalize_currency
format_currency = CurrencyUtil.format_currency
format_currency_with_evidence = CurrencyUtil.format_currency_with_evidence