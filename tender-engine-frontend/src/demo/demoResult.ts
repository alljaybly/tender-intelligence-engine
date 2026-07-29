/**
 * Hardcoded demo processing result for the interactive demo experience.
 *
 * This data represents a realistic processed tender result.
 * It is clearly labelled as demonstration data.
 */

export const DEMO_LABEL = "Sample Demonstration Data";

export const demoResult = {
  job_id: "demo-2026-001",
  status: "completed" as const,
  filename: "Muni_Infra_Tender_2026_Q2.pdf",
  completed_stages: [
    "extract_text",
    "detect_sector",
    "detect_duration",
    "detect_locations",
    "extract_workforce",
    "extract_schedule",
    "extract_boq",
    "pricing",
  ],
  failed_stages: [],
  metadata: {
    sector: "Infrastructure",
    duration_months: 24,
    locations: ["Gauteng", "Johannesburg", "Sandton"],
    extraction_method: "hybrid",
    pipeline_version: "v2.1.0",
  },
  detected_sector: "Infrastructure — Road & Civil Works",
  detected_duration_months: 24,
  detected_locations: ["Gauteng", "Johannesburg", "Sandton"],
  detected_workforce: {
    "Civil Engineers": { count: 8, source: "extracted" },
    "Site Supervisors": { count: 12, source: "extracted" },
    "General Labour": { count: 85, source: "inferred" },
    "Equipment Operators": { count: 24, source: "extracted" },
    "Safety Officers": { count: 4, source: "extracted" },
    total_personnel: 133,
  },
  detected_schedule: {
    start_date: "Q2 2026",
    phases: [
      { phase: "Site Preparation", duration: "3 months" },
      { phase: "Foundation Works", duration: "6 months" },
      { phase: "Structural Construction", duration: "10 months" },
      { phase: "Finishing & Handover", duration: "5 months" },
    ],
  },
  boq_items: [
    {
      item_no: "1.1",
      description: "Site clearing and preparation",
      quantity: 1,
      unit: "lot",
      rate: 450000,
      amount: 450000,
    },
    {
      item_no: "1.2",
      description: "Bulk earthworks including cut and fill",
      quantity: 15000,
      unit: "m³",
      rate: 85,
      amount: 1275000,
    },
    {
      item_no: "2.1",
      description: "Concrete foundation grade 30MPa",
      quantity: 850,
      unit: "m³",
      rate: 2450,
      amount: 2082500,
    },
    {
      item_no: "2.2",
      description: "Reinforcement steel (Y16/Y20)",
      quantity: 65,
      unit: "tons",
      rate: 18500,
      amount: 1202500,
    },
    {
      item_no: "3.1",
      description: "Road base layer (G5 material)",
      quantity: 12000,
      unit: "m³",
      rate: 180,
      amount: 2160000,
    },
    {
      item_no: "3.2",
      description: "Asphalt wearing course (40mm)",
      quantity: 45000,
      unit: "m²",
      rate: 320,
      amount: 14400000,
    },
    {
      item_no: "4.1",
      description: "Stormwater drainage system",
      quantity: 1,
      unit: "lot",
      rate: 2850000,
      amount: 2850000,
    },
    {
      item_no: "4.2",
      description: "Water supply piping (HDPE DN200)",
      quantity: 3200,
      unit: "m",
      rate: 650,
      amount: 2080000,
    },
    {
      item_no: "5.1",
      description: "Street lighting installation",
      quantity: 120,
      unit: "units",
      rate: 28500,
      amount: 3420000,
    },
    {
      item_no: "6.1",
      description: "Traffic signage and road markings",
      quantity: 1,
      unit: "lot",
      rate: 890000,
      amount: 890000,
    },
  ],
  boq_confidence: "high",
  pricing_result: {
    total_boq_amount: 30825500,
    contingency_10_percent: 3082550,
    escalation_8_percent: 2466040,
    professional_fees: 1541275,
    total_estimated_amount: 37915365,
    currency: "ZAR",
    pricing_mode: "detailed_estimate",
    markups_applied: true,
    item_count: 10,
  },
  pricing_status: "completed",
  pricing_unavailable_reason: null,
  extraction_method: "hybrid",
  pipeline_version: "v2.1.0",
  warnings: [
    "General labour count inferred from project scope rather than explicitly stated in document",
    "Schedule phases estimated based on industry benchmarks — confirm with client",
  ],
  confidence_scores: {
    overall: 0.89,
    boq_extraction: 0.94,
    workforce: 0.78,
    sector: 0.96,
    pricing: 0.85,
  },
  executive_summary: `This tender is for the Johannesburg Road & Civil Infrastructure Upgrade (Phase 2), covering road reconstruction, stormwater drainage, and associated civil works in the Sandton and surrounding areas of Gauteng.

Key findings:
• Sector: Infrastructure — Road & Civil Works
• Project Duration: 24 months
• Total BOQ Value: ZAR 30,825,500
• Estimated Total (incl. contingency & fees): ZAR 37,915,365
• Total Workforce Required: 133 personnel across 6 categories
• BOQ Confidence: High (94%)
• Overall Processing Confidence: 89%

The project is a standard municipal infrastructure upgrade with well-defined BOQ items. Pricing estimates include the standard 10% contingency, 8% escalation allowance, and professional fees at 5%.`,
};