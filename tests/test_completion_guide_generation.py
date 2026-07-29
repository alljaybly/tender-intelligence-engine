"""
Test script to generate a sample Tender Completion Guide PDF for visual validation.
Run: python -m tests.test_completion_guide_generation
"""
import sys
import os
from pathlib import Path

# Add api directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.tender_completion_guide import generate_completion_guide


def build_sample_result() -> dict:
    """Build a realistic sample result_data dict for testing."""
    return {
        "filename": "ZNT-012345-2026-Construction-Upgrade.pdf",
        "status": "completed",
        "metadata": {
            "tender_number": "ZNT 012345/2026",
            "employer": "KwaZulu-Natal Department of Public Works",
            "project_title": "Upgrade of N2 Highway Section 3: Phase 2",
        },
        "detected_sector": "Construction (Civil Engineering)",
        "detected_duration_months": 18,
        "detected_locations": ["Durban", "Pietermaritzburg", "Stanger"],
        "detected_currency": {
            "currency_code": "ZAR",
            "currency_name": "South African Rand",
            "currency_symbol": "R",
            "confidence": 0.99,
        },
        "detected_workforce": {
            "total_workers": 45,
            "skilled": 15,
            "semi_skilled": 20,
            "unskilled": 10,
        },
        "detected_schedule": {
            "start_date": "2026-09-01",
            "end_date": "2028-02-28",
            "milestones": [
                {"name": "Site handover", "date": "2026-09-15"},
                {"name": "Foundation complete", "date": "2027-01-30"},
                {"name": "Structural completion", "date": "2027-08-15"},
                {"name": "Practical completion", "date": "2028-02-28"},
            ],
        },
        "boq_items": [
            {"item_no": 1, "description": "Site clearance", "unit": "m²", "quantity": 5000, "rate": 12.50},
            {"item_no": 2, "description": "Earthworks", "unit": "m³", "quantity": 2500, "rate": 85.00},
            {"item_no": 3, "description": "Concrete works Grade 30", "unit": "m³", "quantity": 800, "rate": 1450.00},
            {"item_no": 4, "description": "Reinforcement steel", "unit": "kg", "quantity": 45000, "rate": 18.50},
            {"item_no": 5, "description": "Road base layer", "unit": "m³", "quantity": 3200, "rate": 220.00},
            {"item_no": 6, "description": "Asphalt surfacing", "unit": "m²", "quantity": 18000, "rate": 185.00},
            {"item_no": 7, "description": "Drainage system", "unit": "m", "quantity": 1200, "rate": 450.00},
            {"item_no": 8, "description": "Guardrails and barriers", "unit": "m", "quantity": 3500, "rate": 320.00},
            {"item_no": 9, "description": "Road marking and signage", "unit": "lot", "quantity": 1, "rate": 850000.00},
            {"item_no": 10, "description": "Landscaping and rehabilitation", "unit": "m²", "quantity": 8000, "rate": 45.00},
        ],
        "pricing_result": {
            "total": 28500000.00,
            "subtotal": 25000000.00,
            "vat": 3500000.00,
            "currency": "ZAR",
            "items_priced": 10,
        },
    }


def main():
    print("=" * 60)
    print("Tender Completion Guide - Sample Generation")
    print("=" * 60)
    
    job_id = "test-job-2026-001"
    result_data = build_sample_result()
    
    print(f"\nGenerating sample PDF for job: {job_id}")
    print(f"Document: {result_data['filename']}")
    print(f"Sector: {result_data['detected_sector']}")
    print(f"BOQ items: {len(result_data['boq_items'])}")
    print(f"Pricing: {'Available' if result_data['pricing_result'] else 'Missing'}")
    
    # Generate the PDF
    pdf_buffer = generate_completion_guide(job_id, result_data)
    
    # Save to file
    output_path = Path(__file__).parent.parent / "sample_completion_guide.pdf"
    with open(output_path, "wb") as f:
        f.write(pdf_buffer.getvalue())
    
    file_size = len(pdf_buffer.getvalue())
    print(f"\n[OK] PDF generated successfully!")
    print(f"   File: {output_path}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    
    # Quick validation
    pdf_content = pdf_buffer.getvalue()
    if pdf_content.startswith(b"%PDF"):
        print("   Format: Valid PDF")
    else:
        print("   [FAIL] ERROR: Not a valid PDF!")
        return 1
    
    # Check for key content
    text_content = pdf_content.decode("latin-1", errors="replace")
    checks = [
        ("TENDER COMPLETION GUIDE", "Cover title"),
        ("READY FOR FINAL ASSEMBLY", "Status badge"),
        ("Confidence Summary", "Confidence section"),
        ("Estimated Completion", "Estimated completion section"),
        ("Missing Information", "Missing info section"),
        ("Missing Documents", "Missing documents section"),
        ("Recommended Workflow", "Workflow section"),
        ("Printable Submission Checklist", "Checklist section"),
        ("Common Disqualification Mistakes", "Mistakes section"),
        ("Helpful Tender Tips", "Tips section"),
        ("Final Submission Readiness", "Readiness section"),
        ("Tender Engine", "Footer branding"),
        ("Evidence-Based Document Processing", "Footer subtitle"),
        ("v3.1.0", "Version number"),
        ("Page ", "Page numbering"),
        ("Job:", "Job ID in header"),
        ("No information has been invented", "Verification notice"),
    ]
    
    print("\n--- Content Validation ---")
    all_passed = True
    for search_text, label in checks:
        if search_text in text_content:
            print(f"   [OK] {label}")
        else:
            print(f"   [FAIL] {label} - MISSING!")
            all_passed = False
    
    # Check for QR code (look for PNG signature in PDF)
    if b"\x89PNG" in pdf_content:
        print("   [OK] QR Code embedded")
    else:
        print("   [WARN] QR Code not found (may be drawn differently)")
    
    # Check for badge patterns
    badge_checks = [
        ("Critical", "Critical badge"),
        ("High", "High badge"),
        ("Medium", "Medium badge"),
        ("Complete", "Complete badge"),
        ("Pending", "Pending badge"),
        ("Missing", "Missing badge"),
    ]
    for search_text, label in badge_checks:
        if search_text in text_content:
            print(f"   [OK] {label}")
        else:
            print(f"   [WARN] {label} - not found (may be context-dependent)")
    
    print(f"\n{'=' * 60}")
    if all_passed:
        print("[PASS] ALL CONTENT CHECKS PASSED")
    else:
        print("[WARN] Some content checks failed - review output")
    print(f"{'=' * 60}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())