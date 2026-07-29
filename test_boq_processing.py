import pytest
from decimal import Decimal
# Import your actual accumulate_total function here
# from api.services.boq_extractor import accumulate_total

def test_perfect_tender_calculation():
    # Simulated data extracted from your new Perfect PDF
    clean_items = [
        {"amount": Decimal("12505.00")},
        {"amount": Decimal("4525.00")},
        {"amount": Decimal("17000.00")},
        {"amount": Decimal("2500.00")},
        {"amount": Decimal("104000.00")},
    ]
    
    result = accumulate_total(clean_items)
    
    # Expected results based on the test PDF
    assert result["subtotal"] == Decimal("136530.00")
    assert result["vat"] == Decimal("20479.50")
    assert result["grand_total"] == Decimal("157009.50")
    print("Test Passed: Perfect tender processed with 100% precision.")

if __name__ == "__main__":
    test_perfect_tender_calculation()