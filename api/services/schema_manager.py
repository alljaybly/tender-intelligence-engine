"""
Schema Manager Service for Tender Engine.

Dynamically loads compliance schemas by jurisdiction.
Falls back to South Africa (SA) schema if jurisdiction can't be determined.
"""
import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SchemaManager:
    """Manages compliance schemas for different jurisdictions."""

    _schemas_cache: Dict[str, Dict[str, Any]] = {}
    _default_schema: Optional[Dict[str, Any]] = None

    @classmethod
    def _get_schemas_dir(cls) -> str:
        """Get the absolute path to the compliance_schemas directory."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(os.path.dirname(current_dir), "compliance_schemas")

    @classmethod
    def _load_schema(cls, schema_filename: str) -> Optional[Dict[str, Any]]:
        """Load a schema from a JSON file.

        Args:
            schema_filename: Name of the schema file (e.g., "sa_schema.json").

        Returns:
            The loaded schema as a dict, or None if loading fails.
        """
        schemas_dir = cls._get_schemas_dir()
        schema_path = os.path.join(schemas_dir, schema_filename)

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
            logger.info(f"Successfully loaded schema: {schema_filename}")
            return schema
        except FileNotFoundError:
            logger.error(f"Schema file not found: {schema_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema file {schema_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading schema {schema_filename}: {e}")
        return None

    @classmethod
    def get_default_schema(cls) -> Dict[str, Any]:
        """Get the default schema (South Africa).

        Returns:
            The default schema dictionary.
        """
        if cls._default_schema is None:
            cls._default_schema = cls._load_schema("sa_schema.json")
            if cls._default_schema is None:
                raise RuntimeError("Failed to load default schema (sa_schema.json)")
        return cls._default_schema

    @classmethod
    def get_schema_for_jurisdiction(cls, jurisdiction_code: Optional[str] = None) -> Dict[str, Any]:
        """Get the schema for a given jurisdiction.

        Args:
            jurisdiction_code: ISO country code (e.g., "ZA", "US") or jurisdiction name.
                              If None or unknown, returns the default schema.

        Returns:
            The schema dictionary for the jurisdiction, or the default schema.
        """
        if jurisdiction_code is None:
            logger.info("No jurisdiction provided, using default schema")
            return cls.get_default_schema()

        # Normalize jurisdiction code
        normalized_code = jurisdiction_code.strip().upper()

        # Check cache
        if normalized_code in cls._schemas_cache:
            return cls._schemas_cache[normalized_code]

        # Map common jurisdiction identifiers to schema filenames
        schema_mapping = {
            "ZA": "sa_schema.json",
            "SOUTH AFRICA": "sa_schema.json",
            "ZAF": "sa_schema.json",
        }

        schema_filename = schema_mapping.get(normalized_code)
        if schema_filename:
            schema = cls._load_schema(schema_filename)
            if schema:
                cls._schemas_cache[normalized_code] = schema
                return schema

        # If no schema found, fall back to default
        logger.warning(f"No schema found for jurisdiction {jurisdiction_code}, using default schema")
        return cls.get_default_schema()

    @classmethod
    def detect_jurisdiction(cls, result_data: Dict[str, Any]) -> Optional[str]:
        """Try to detect the jurisdiction from the tender result data.

        Args:
            result_data: The tender processing result data.

        Returns:
            Detected jurisdiction code or name, or None if unsure.
        """
        # Look for jurisdiction clues in metadata
        metadata = result_data.get("metadata", {}) or {}
        full_text = (result_data.get("full_text", "") or "").lower()
        locations = result_data.get("detected_locations", []) or []

        # Check for South Africa clues
        sa_keywords = [
            "south africa", "sa", "zaf", "western cape", "gauteng", "kwazulu-natal",
            "capitec", "abs", "fnb", "nedbank", "standard bank",
            "rand", "zar", "sars", "cidb", "bbbee"
        ]

        for location in locations:
            loc_str = str(location).lower()
            for keyword in sa_keywords:
                if keyword in loc_str:
                    return "ZA"

        for keyword in sa_keywords:
            if keyword in full_text:
                return "ZA"

        # Check metadata fields
        for key, value in metadata.items():
            value_str = str(value).lower()
            for keyword in sa_keywords:
                if keyword in value_str:
                    return "ZA"

        # If we can't confidently detect, return None (default schema will be used)
        return None
