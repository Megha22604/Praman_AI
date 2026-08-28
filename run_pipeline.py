import json
from parser import parse_raw_ocr_lines
from rules_engine import validate_label

# Simulated raw text lines as returned by an OCR engine from a product package
raw_ocr_lines_sample = [
    "CRUNCHY POTATO CHIPS",
    "Net Qty: 200 g",
    "MRP Rs. 35.00 (Incl. of all taxes)",
    "USP: Rs. 0.175 / g",
    "Mfg Date: 02/2026",
    "Manufactured by: Sunshine Snacks Pvt Ltd, Plot 12, GIDC, Ahmedabad 382445",
    "Consumer Care: feedback@sunshinesnacks.com, Toll Free 1800-200-9999",
    "Country of Origin: India"
]

print("=== 1. RAW OCR DETECTED LINES ===")
for line in raw_ocr_lines_sample:
    print(f"  • {line}")

# Step 1: Parse the raw strings into structured legal fields[cite: 1]
parsed_fields = parse_raw_ocr_lines(raw_ocr_lines_sample)
print("\n=== 2. PARSED STRUCTURED FIELDS ===")
print(json.dumps(parsed_fields, indent=2))

# Step 2: Add metadata and run deterministic rules validation[cite: 1, 2]
parsed_fields["metadata"] = {
    "shape": "rectangular",
    "height_cm": 18.0,
    "width_cm": 12.0,  # PDP Area = 216 cm² -> Min Font Height = 2.5 mm[cite: 2]
    "is_blown": False
}
parsed_fields["font_height_mm"] = 2.8  # Compliant font measurement[cite: 2]

compliance_report = validate_label(parsed_fields)

print("\n=== 3. FINAL COMPLIANCE REPORT ===")
print(f"Overall Compliant: {compliance_report['compliant']}")
print(f"Score: {compliance_report['score']} ({compliance_report['percentage']}%)")
print(json.dumps(compliance_report["results"], indent=2))