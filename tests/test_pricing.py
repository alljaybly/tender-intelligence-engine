"""
Phase 1 -- Pricing Engine Integration Tests

Run:  python -m pytest tests/test_pricing.py -v
Or:   python tests/test_pricing.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.pricing_engine import PricingEngine


def test_pricing_engine_cleaning():
    engine = PricingEngine()
    tender_data = {
        "sector": "cleaning",
        "cost_per_hour": 23.50,
        "_cost_source": "user",
        "duration_months": 12,
        "workforce": {"total_workers": 10, "supervisors": 2, "unskilled_workers": 8},
        "requirements": {"shifts_per_day": 2, "hours_per_day": 8},
        "scope": {"area_sqm": 5000},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("sector") == "cleaning"
    assert result["labour_cost"] > 0
    assert result["equipment_cost"] > 0
    assert result["materials_cost"] > 0
    assert result["transport_cost"] > 0
    assert result["subtotal"] > 0
    assert result["overheads"] > 0
    assert result["profit"] > 0
    assert result["vat"] > 0
    assert result["total_monthly"] > 0
    assert result["total_contract_value"] > 0
    assert result["final_price"] > 0
    assert result.get("breakdown") is not None
    assert result["total_monthly"] > result["subtotal"]
    print("[OK] Cleaning sector tests passed")


def test_pricing_engine_construction():
    engine = PricingEngine()
    tender_data = {
        "sector": "construction",
        "cost_per_hour": 30.00,
        "_cost_source": "user",
        "duration_months": 6,
        "workforce": {"total_workers": 15, "supervisors": 2, "skilled_workers": 8, "unskilled_workers": 5},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("sector") == "construction"
    assert result["final_price"] > 0
    assert result.get("calculation_method") == "construction_sector_formula"
    print("[OK] Construction sector tests passed")


def test_pricing_engine_electrical():
    engine = PricingEngine()
    tender_data = {
        "sector": "electrical",
        "cost_per_hour": 45.00,
        "_cost_source": "user",
        "duration_months": 3,
        "workforce": {"skilled_workers": 3, "unskilled_workers": 2},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("sector") == "electrical"
    assert result["final_price"] > 0
    print("[OK] Electrical sector tests passed")


def test_pricing_engine_security():
    engine = PricingEngine()
    tender_data = {
        "sector": "security",
        "cost_per_hour": 22.00,
        "_cost_source": "user",
        "duration_months": 12,
        "workforce": {"total_workers": 5},
        "requirements": {"shifts_per_day": 3},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("sector") == "security"
    assert result["final_price"] > 0
    print("[OK] Security sector tests passed")


def test_pricing_engine_gardening():
    engine = PricingEngine()
    tender_data = {
        "sector": "gardening",
        "cost_per_hour": 18.00,
        "_cost_source": "user",
        "duration_months": 12,
        "workforce": {"total_workers": 4},
        "scope": {"area_sqm": 2000},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("sector") == "gardening"
    assert result["final_price"] > 0
    print("[OK] Gardening sector tests passed")


def test_pricing_engine_location_factor():
    engine = PricingEngine()
    tender_data = {
        "sector": "cleaning",
        "cost_per_hour": 23.50,
        "_cost_source": "user",
        "duration_months": 12,
        "workforce": {"total_workers": 10, "supervisors": 2, "unskilled_workers": 8},
        "requirements": {"shifts_per_day": 2, "hours_per_day": 8},
        "scope": {"area_sqm": 5000},
    }
    base_result = engine.calculate(tender_data, {}, {})
    wc_result = engine.apply_location_factor(base_result.copy(), "western cape")
    assert wc_result.get("location") == "western cape"
    assert wc_result.get("location_multiplier") == 1.1
    assert wc_result["total_monthly"] > base_result["total_monthly"]
    print("[OK] Location factor tests passed")


def test_reprice():
    engine = PricingEngine()
    sample = {"subtotal": 50000.00, "overheads": 7500.00, "profit": 8625.00, "vat": 9918.75, "total_monthly": 76043.75, "duration_months": 12}
    result = engine.reprice(sample, "optimize_win")
    assert result.get("profit") is not None
    assert result.get("total_monthly") is not None
    assert result.get("total_contract_value") is not None
    print("[OK] Reprice tests passed")


def test_general_sector():
    engine = PricingEngine()
    tender_data = {
        "sector": "general",
        "cost_per_hour": 35.00,
        "_cost_source": "user",
        "duration_months": 12,
        "workforce": {"total_workers": 10},
        "requirements": {"shifts_per_day": 1, "hours_per_day": 8},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("sector") == "general"
    assert result["final_price"] > 0
    print("[OK] General sector tests passed")


def test_emergency_premium():
    engine = PricingEngine()
    tender_data = {
        "sector": "cleaning",
        "cost_per_hour": 23.50,
        "_cost_source": "user",
        "duration_months": 3,
        "workforce": {"total_workers": 5, "supervisors": 1, "unskilled_workers": 4},
        "requirements": {"shifts_per_day": 1, "hours_per_day": 8},
        "scope": {"area_sqm": 500, "is_emergency": True},
    }
    result = engine.calculate(tender_data, {}, {})
    assert result.get("emergency_premium") is not None
    assert result["emergency_premium"] > 0
    assert result["subtotal"] > result["labour_cost"] + result["equipment_cost"] + result["materials_cost"] + result["transport_cost"]
    print("[OK] Emergency premium tests passed")


if __name__ == "__main__":
    test_pricing_engine_cleaning()
    test_pricing_engine_construction()
    test_pricing_engine_electrical()
    test_pricing_engine_security()
    test_pricing_engine_gardening()
    test_pricing_engine_location_factor()
    test_reprice()
    test_general_sector()
    test_emergency_premium()
    print("\n" + "=" * 50)
    print("ALL PRICING ENGINE TESTS PASSED")
    print("=" * 50)