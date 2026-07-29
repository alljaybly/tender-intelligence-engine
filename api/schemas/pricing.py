from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PricingInput(BaseModel):
    """Input payload for pricing calculation."""
    sector: str = Field(
        ...,
        description="Industry sector - e.g. cleaning, construction, electrical, security, gardening, it_services, maintenance, supply, general",
        examples=["cleaning"],
    )
    cost_per_hour: float = Field(
        ...,
        gt=0,
        description="Cost per hour rate (provided by user, document extraction, or config)",
        examples=[23.50],
    )
    cost_source: str = Field(
        default="user",
        description="Source of cost_per_hour: 'user', 'document', or 'config'",
        examples=["user"],
    )
    duration_months: Optional[int] = Field(
        default=None,
        description="Contract duration in months",
        examples=[12],
    )
    workforce: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Workforce breakdown: total_workers, skilled_workers, unskilled_workers, supervisors, etc.",
        examples=[{"total_workers": 10, "supervisors": 2, "unskilled_workers": 8}],
    )
    requirements: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Operational requirements: shifts_per_day, hours_per_day, etc.",
        examples=[{"shifts_per_day": 2, "hours_per_day": 8}],
    )
    scope: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Scope details: area_sqm, is_emergency, etc.",
        examples=[{"area_sqm": 5000}],
    )
    location: Optional[str] = Field(
        default=None,
        description="Geographic location for cost adjustment (e.g. gauteng, western cape, limpopo)",
        examples=["gauteng"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sector": "cleaning",
                "cost_per_hour": 23.50,
                "cost_source": "user",
                "duration_months": 12,
                "workforce": {
                    "total_workers": 10,
                    "supervisors": 2,
                    "unskilled_workers": 8,
                },
                "requirements": {
                    "shifts_per_day": 2,
                    "hours_per_day": 8,
                },
                "scope": {
                    "area_sqm": 5000,
                },
                "location": "gauteng",
            }
        }


class RepriceInput(BaseModel):
    """Input payload for repricing an existing calculation."""
    pricing_result: Dict[str, Any] = Field(
        ...,
        description="Existing pricing result dictionary (output from /api/pricing/calculate)",
        examples=[{
            "labour_cost": 15000.00,
            "equipment_cost": 6000.00,
            "materials_cost": 8800.00,
            "subtotal": 29800.00,
            "overheads": 4470.00,
            "profit": 5140.50,
            "vat": 5911.58,
            "total_monthly": 45322.08,
            "duration_months": 12,
        }],
    )
    mode: str = Field(
        ...,
        description="Reprice mode: 'optimize_win', 'maximize_profit', or 'reduce_margin'",
        examples=["optimize_win"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pricing_result": {
                    "sector": "cleaning",
                    "labour_cost": 15000.00,
                    "equipment_cost": 6000.00,
                    "materials_cost": 8800.00,
                    "transport_cost": 6600.00,
                    "subtotal": 36400.00,
                    "overheads": 5460.00,
                    "profit": 6279.00,
                    "vat": 7220.85,
                    "total_monthly": 55359.85,
                    "duration_months": 12,
                },
                "mode": "optimize_win",
            }
        }


class PricingOutput(BaseModel):
    """Standardised output schema for pricing calculation results."""
    sector: str = Field(..., description="Industry sector")
    labour_cost: Optional[float] = Field(default=None, description="Monthly labour cost")
    equipment_cost: Optional[float] = Field(default=None, description="Monthly equipment cost")
    materials_cost: Optional[float] = Field(default=None, description="Monthly materials cost")
    transport_cost: Optional[float] = Field(default=None, description="Monthly transport cost")
    emergency_premium: Optional[float] = Field(default=None, description="Emergency premium (if applicable)")
    subtotal: Optional[float] = Field(default=None, description="Cost subtotal before overheads/profit/vat")
    overheads: Optional[float] = Field(default=None, description="Overheads applied")
    profit: Optional[float] = Field(default=None, description="Profit margin")
    vat: Optional[float] = Field(default=None, description="VAT (15%)")
    total_monthly: Optional[float] = Field(default=None, description="Total monthly cost (incl. overheads, profit, VAT)")
    total_contract_value: Optional[float] = Field(default=None, description="Total contract value")
    final_price: Optional[float] = Field(default=None, description="Final computed price")
    breakdown: Optional[Dict[str, Any]] = Field(default=None, description="Detailed cost breakdown")
    confidence: Optional[str] = Field(default=None, description="Confidence level: High, Medium, Low")
    assumptions: Optional[List[str]] = Field(default=None, description="Assumptions used in calculation")
    calculation_method: Optional[str] = Field(default=None, description="Sector-specific formula used")
    duration_months: Optional[int] = Field(default=None, description="Contract duration in months")
    location: Optional[str] = Field(default=None, description="Geographic location applied")
    location_multiplier: Optional[float] = Field(default=None, description="Location-based cost multiplier")
    workers: Optional[int] = Field(default=None, description="Total workers used in calculation")
    shifts_per_day: Optional[float] = Field(default=None, description="Shifts per day")
    hours_per_day: Optional[float] = Field(default=None, description="Hours per day")
    rate_source: Optional[str] = Field(default=None, description="Source of rate: user, document, config")
    Extraction_Error_Mismatch: Optional[bool] = Field(
        default=None,
        description="True when Labour + Materials + Overheads exceeds final contract value",
    )
    extraction_error_code: Optional[str] = Field(default=None, description="Structured extraction/pricing error code")
    pricing_validation_status: Optional[str] = Field(default=None, description="Validation status for pricing totals")
    mismatch_details: Optional[Dict[str, Any]] = Field(default=None, description="Component-value mismatch details")

    class Config:
        json_schema_extra = {
            "example": {
                "sector": "cleaning",
                "labour_cost": 18593.75,
                "equipment_cost": 12000.00,
                "materials_cost": 13700.00,
                "transport_cost": 6600.00,
                "subtotal": 50893.75,
                "overheads": 7634.06,
                "profit": 8779.17,
                "vat": 10096.05,
                "total_monthly": 77403.03,
                "total_contract_value": 928836.36,
                "final_price": 928836.36,
                "breakdown": {
                    "cleaners": 8,
                    "cleaners_hourly_rate": 23.50,
                    "supervisors": 2,
                    "supervisor_monthly_salary": 8500.00,
                    "total_personnel": 10,
                    "area_sqm": 5000,
                    "shifts": 2,
                },
                "confidence": "High",
                "assumptions": ["cost_per_hour provided by user input"],
                "calculation_method": "cleaning_sector_formula",
                "duration_months": 12,
                "location": "gauteng",
                "location_multiplier": 1.0,
            }
        }
