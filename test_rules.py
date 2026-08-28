import json
from rules_engine import validate_label

# 1. Base Product Data (Passes all Rule 6 declarations)
base_product = {
    "mrp": "Rs. 45.00 (incl. of all taxes)",
    "manufacturer": "ABC Foods Pvt Ltd, Industrial Area, Pune 411001",
    "net_quantity": "500 g",
    "mfg_date": "03/2026",
    "consumer_care": "care@abcfoods.com, Toll-Free: 1800-123-4567",
    "country_of_origin": "India",
    "unit_sale_price": "Rs. 0.09 / g"
}

# 2. Test Case: Rectangular Box (15cm x 10cm = 150 cm² PDP -> Requires Min 2.5mm Font)
# Case A: Compliant Font Height (3.0 mm) -> Should Pass 8/8 (100%)
compliant_box = {
    **base_product,
    "font_height_mm": 3.0,
    "metadata": {
        "shape": "rectangular",
        "height_cm": 15.0,
        "width_cm": 10.0,
        "is_blown": False
    }
}

# Case B: Sub-minimum Font Height (1.8 mm) -> Should Fail Rule 7(2)
undersized_font_box = {
    **base_product,
    "font_height_mm": 1.8,
    "metadata": {
        "shape": "rectangular",
        "height_cm": 15.0,
        "width_cm": 10.0,
        "is_blown": False
    }
}

print("=== 1. TESTING COMPLIANT FONT & PDP (8/8 CHECKS) ===")
report1 = validate_label(compliant_box)
print(f"Compliant: {report1['compliant']} | Score: {report1['score']} ({report1['percentage']}%)")
print(json.dumps(report1['results'][-1], indent=2))  # Display the Rule 7 result

print("\n=== 2. TESTING UNDERSIZED FONT (FAILS RULE 7(2)) ===")
report2 = validate_label(undersized_font_box)
print(f"Compliant: {report2['compliant']} | Score: {report2['score']} ({report2['percentage']}%)")
print(json.dumps(report2['results'][-1], indent=2))  # Display the Rule 7 failure