import json
from rules_engine import evaluate_all_rules, validate_label

# 10 Real Product Labels representing various categories, OCR noise levels, and misleading claims
TEST_PRODUCTS = [
    {
        "name": "1. Lays Spanish Tomato Chips (Snacks)",
        "type": "raw_lines",
        "lines": [
            "LAYS SPANISH TOMATO CHIPS",
            "Net Qty: 52 g",
            "MR1P R5. 20.00 (Incl. of all taxes)",
            "USP: Rs. 0.38 / g",
            "Mfg Date: 01/2026",
            "Manufactured by: PepsiCo India Holdings Pvt Ltd, Sector 18, Gurugram 122015",
            "Consumer Care: feedback@pepsico.com, Toll Free 1800-222-678",
            "Country of Origin: India"
        ],
        "height_cm": 18.0,
        "width_cm": 12.0,
        "font_height_mm": 2.8,
        "expected_status": "PASS"
    },
    {
        "name": "2. Amul Taaza Toned Milk Pouch (Dairy - Noisy OCR & Missing Origin)",
        "type": "raw_lines",
        "lines": [
            "AMUL TAAZA TONED MILK",
            "Net Weight: 500rni",
            "MR1P R5 27.00",
            "USP: Rs. 0.054 / ml",
            "rnfd 02/2026",
            "Marketed by: Kaira District Co-op Milk Producers Union, Anand 388001",
            "Consumer Care: care@amul.coop, 1800-258-3333"
        ],
        "height_cm": 15.0,
        "width_cm": 10.0,
        "font_height_mm": 2.2,
        "expected_status": "FAIL"  # Missing country of origin
    },
    {
        "name": "3. Nestlé Maggi 2-Minute Noodles (Deceptive Fat Claim)",
        "type": "raw_lines",
        "lines": [
            "MAGGI 2-MINUTE NOODLES",
            "100% Natural & 97% fat free",
            "Net Qty: 70 g",
            "MRP Rs. 14.00 (incl. of all taxes)",
            "USP: Rs. 0.20 / g",
            "Mfg Date: 03/2026",
            "Manufactured by: Nestle India Ltd, Moga, Punjab 142001",
            "Consumer Care: wecare@in.nestle.com, Toll-Free 1800-103-1947",
            "Country of Origin: India"
        ],
        "height_cm": 12.0,
        "width_cm": 10.0,
        "font_height_mm": 2.5,
        "expected_status": "NEEDS REVIEW"  # Separate advisory for '97% fat free' triggers review
    },
    {
        "name": "4. Cadbury Dairy Milk Silk (Confectionery - Low Confidence OCR)",
        "type": "raw_lines",
        "lines": [
            "CADBURY DAIRY MILK SILK",
            "Net Weight: 150 g",
            "MRP Rs. 175.00",
            "USP: Rs. 1.17 / g",
            "rnfd O3/2O26",  # Letter 'O' instead of digit '0'
            "rnfg by: Mondelez India Foods Pvt Ltd, Mumbai 400018",
            "Consumer Care: care@mondelez.com, Toll Free 1800-22-7080",
            "Country of Origin: India"
        ],
        "height_cm": 16.0,
        "width_cm": 8.0,
        "font_height_mm": 2.6,
        "expected_status": "NEEDS REVIEW"  # Low-confidence date OCR
    },
    {
        "name": "5. Britannia Good Day Biscuits (Bakery - Missing USP)",
        "type": "dict",
        "data": {
            "mrp": "Rs. 30.00 (incl. of all taxes)",
            "manufacturer": "Britannia Industries Ltd, Kolkata 700017",
            "net_quantity": "120 g",
            "mfg_date": "02/2026",
            "consumer_care": "feedback@britindia.com, 1800-425-4444",
            "country_of_origin": "India",
            "unit_sale_price": None,  # Missing USP declaration
            "full_text": "Britannia Good Day Biscuits Net Qty 120g MRP Rs 30.00 Made in India",
            "font_height_mm": 2.5,
            "metadata": {"shape": "rectangular", "height_cm": 14.0, "width_cm": 8.0}
        },
        "expected_status": "FAIL"  # Missing USP
    },
    {
        "name": "6. Tata Salt Iodized (Staples - OCR Unit Noise)",
        "type": "raw_lines",
        "lines": [
            "TATA SALT VACUUM EVAPORATED",
            "Net Weight: 1kq",  # OCR read 'kq' instead of 'kg'
            "MRP Rs. 28.00 (Incl. of all taxes)",
            "USP: Rs. 0.028 / g",
            "Mfg Date: 01/2026",
            "Manufactured by: Tata Consumer Products Ltd, Mumbai 400099",
            "Consumer Care: care@tataconsumer.com, 1800-108-4488",
            "Country of Origin: India"
        ],
        "height_cm": 22.0,
        "width_cm": 15.0,
        "font_height_mm": 3.5,
        "expected_status": "NEEDS REVIEW"  # '1kq' OCR unit noise
    },
    {
        "name": "7. Dettol Liquid Handwash (Personal Care - Deceptive Origin Claim)",
        "type": "raw_lines",
        "lines": [
            "DETTOL LIQUID HANDWASH REFILL",
            "Swiss Formula - Made in USA",  # Deceptive origin claim
            "Net Qty: 750 ml",
            "MRP Rs. 135.00",
            "USP: Rs. 0.18 / ml",
            "Mfg Date: 12/2025",
            "Manufactured by: Reckitt Benckiser India Pvt Ltd, Solan HP 173205",
            "Consumer Care: india.rcare@reckitt.com, 1800-102-2221",
            "Country of Origin: India"  # Declared origin conflicts with header
        ],
        "height_cm": 20.0,
        "width_cm": 12.0,
        "font_height_mm": 3.0,
        "expected_status": "NEEDS REVIEW"  # Origin inconsistency separate advisory
    },
    {
        "name": "8. Tropicana 100% Orange Juice (Beverages - Sub-minimum Font Height)",
        "type": "dict",
        "data": {
            "mrp": "Rs. 145.00 (incl. of all taxes)",
            "manufacturer": "Varun Beverages Ltd, Greater Noida 201306",
            "net_quantity": "1000 ml",
            "mfg_date": "02/2026",
            "consumer_care": "consumer.feedback@varunbev.com, 1800-180-1234",
            "country_of_origin": "India",
            "unit_sale_price": "Rs. 0.145 / ml",
            "full_text": "Tropicana 100% Orange Juice Net Qty 1000ml Made in India",
            "font_height_mm": 1.2,  # Sub-minimum font for 300 cm² PDP (requires min 2.5 mm)
            "metadata": {"shape": "rectangular", "height_cm": 20.0, "width_cm": 15.0}
        },
        "expected_status": "FAIL"  # Undersized font
    },
    {
        "name": "9. Dabur Organic Honey (Ayurveda - Miracle Cure & Weight Loss Claim)",
        "type": "raw_lines",
        "lines": [
            "DABUR PURE ORGANIC HONEY",
            "Guaranteed Weight Loss & 100% Natural Miracle Cures Cold",
            "Net Qty: 250 g",
            "MRP Rs. 195.00 (Incl. of all taxes)",
            "USP: Rs. 0.78 / g",
            "Mfg Date: 01/2026",
            "Manufactured by: Dabur India Ltd, Sahibabad Ghaziabad 201010",
            "Consumer Care: daburcares@dabur.com, 1800-103-1644",
            "Country of Origin: India"
        ],
        "height_cm": 14.0,
        "width_cm": 8.0,
        "font_height_mm": 2.5,
        "expected_status": "NEEDS REVIEW"  # Unverified health claim separate advisory
    },
    {
        "name": "10. Ferrero Rocher Chocolates (Imported Confectionery - 100% Compliant)",
        "type": "dict",
        "data": {
            "mrp": "Rs. 499.00 (incl. of all taxes)",
            "manufacturer": "Imported by: Ferrero India Pvt Ltd, Baramati Pune 413133",
            "net_quantity": "200 g",
            "mfg_date": "11/2025",
            "consumer_care": "customercare.india@ferrero.com, 1800-209-2090",
            "country_of_origin": "Italy",
            "unit_sale_price": "Rs. 2.495 / g",
            "full_text": "Ferrero Rocher Chocolates Country of Origin Italy Imported by Ferrero India",
            "font_height_mm": 3.2,
            "metadata": {"shape": "rectangular", "height_cm": 18.0, "width_cm": 12.0}
        },
        "expected_status": "PASS"
    }
]


def run_evaluation_suite():
    print("================================================================================")
    print("           PRAMAN_AI LMPC RULES ENGINE COMPREHENSIVE EVALUATION SUITE            ")
    print("================================================================================")

    passed_tests = 0
    total_tests = len(TEST_PRODUCTS)

    for idx, test in enumerate(TEST_PRODUCTS, start=1):
        print(f"\n--- Product {idx}: {test['name']} ---")

        if test["type"] == "raw_lines":
            report = evaluate_all_rules(
                raw_lines=test["lines"],
                package_height_cm=test.get("height_cm", 15.0),
                package_width_cm=test.get("width_cm", 10.0),
                detected_font_height_mm=test.get("font_height_mm", 2.5)
            )
        else:
            report = validate_label(test["data"])

        actual_status = report["status"]
        expected_status = test["expected_status"]

        status_match = (actual_status == expected_status)
        if status_match:
            passed_tests += 1

        status_flag = "[OK MATCH]" if status_match else "[MISMATCH]"
        print(f"Status: {actual_status} (Expected: {expected_status}) {status_flag}")
        print(f"Score: {report['score']} ({report['percentage']}%) | Pass: {report['pass_count']} | Review: {report['review_count']} | Fail: {report['fail_count']}")
        print("Checkpoints Breakdown (8 Statutory Rules):")

        for res in report["results"]:
            icon = "[PASS]" if res["status"] == "PASS" else ("[NEEDS REVIEW]" if res["status"] == "NEEDS REVIEW" else "[FAIL]")
            conf = f" (Conf: {res.get('confidence', 1.0)})" if 'confidence' in res else ""
            clean_reason = str(res['reason']).replace('₹', 'Rs.').encode('ascii', 'replace').decode('ascii')
            print(f"  {icon}{conf} {res['field']} ({res['rule']}): {clean_reason}")

        misleading = report.get("misleading_declarations", {})
        if misleading.get("detected"):
            print(f"  >> [SEPARATE ADVISORY] Misleading/Non-Standard Claims ({misleading['count']} found):")
            for f in misleading.get("findings", []):
                print(f"     * [{f['status']}] '{f['claim']}' ({f['category']}): {f['reason']}")

    print("\n================================================================================")
    print(f"SUMMARY: {passed_tests}/{total_tests} test cases produced expected evaluation outcome.")
    print("================================================================================")


if __name__ == "__main__":
    run_evaluation_suite()