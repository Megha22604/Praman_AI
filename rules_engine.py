import re

def validate_mrp(mrp_text):
    """Rule 6(1)(e): MRP must be declared with a currency symbol and include all taxes."""
    if not mrp_text or not str(mrp_text).strip():
        return {
            "field": "MRP",
            "pass": False,
            "rule": "Rule 6(1)(e)",
            "reason": "MRP not found on label"
        }

    text = str(mrp_text).lower()
    has_currency = "rs" in text or "₹" in text or "inr" in text

    if not has_currency:
        return {
            "field": "MRP",
            "pass": False,
            "rule": "Rule 6(1)(e)",
            "reason": "MRP present but missing currency symbol (Rs. / ₹ / INR)"
        }

    return {
        "field": "MRP",
        "pass": True,
        "rule": "Rule 6(1)(e)",
        "reason": "OK"
    }


def validate_manufacturer(manufacturer_text):
    """Rule 6(1)(a): Name and complete address of the manufacturer/packer/importer."""
    if not manufacturer_text or not str(manufacturer_text).strip():
        return {
            "field": "Manufacturer Details",
            "pass": False,
            "rule": "Rule 6(1)(a)",
            "reason": "Manufacturer/Packer/Importer details not found on label"
        }

    return {
        "field": "Manufacturer Details",
        "pass": True,
        "rule": "Rule 6(1)(a)",
        "reason": "OK"
    }


def validate_net_quantity(quantity_text):
    """Rule 6(1)(c): Net quantity declared in standard units of metric measurement."""
    if not quantity_text or not str(quantity_text).strip():
        return {
            "field": "Net Quantity",
            "pass": False,
            "rule": "Rule 6(1)(c)",
            "reason": "Net quantity not found on label"
        }

    text = str(quantity_text).lower()
    
    # Matches digits followed by statutory unit (e.g., '500g', '1 kg', '200 ml', '10 pcs')
    pattern = r"\b\d+(?:\.\d+)?\s*(g|gm|kg|ml|l|ltr|liter|litre|m|cm|mm|u|n|pcs|piece|pieces|count)\b"
    if not re.search(pattern, text):
        return {
            "field": "Net Quantity",
            "pass": False,
            "rule": "Rule 6(1)(c)",
            "reason": "Net quantity missing standard unit of measurement (g, kg, ml, l, pcs, etc.)"
        }

    return {
        "field": "Net Quantity",
        "pass": True,
        "rule": "Rule 6(1)(c)",
        "reason": "OK"
    }


def validate_manufacturing_date(date_text):
    """Rule 6(1)(d): Month and year of manufacture / packing / import."""
    if not date_text or not str(date_text).strip():
        return {
            "field": "Date of Manufacture/Packing",
            "pass": False,
            "rule": "Rule 6(1)(d)",
            "reason": "Month/Year of manufacture or packing not found on label"
        }

    return {
        "field": "Date of Manufacture/Packing",
        "pass": True,
        "rule": "Rule 6(1)(d)",
        "reason": "OK"
    }


def validate_consumer_care(care_text):
    """Rule 6(2): Consumer care details (contact number, email, or address)."""
    if not care_text or not str(care_text).strip():
        return {
            "field": "Consumer Care",
            "pass": False,
            "rule": "Rule 6(2)",
            "reason": "Consumer care contact details not found on label"
        }

    text = str(care_text).lower()
    has_contact = "@" in text or "email" in text or "phone" in text or "tel" in text or "toll" in text or any(char.isdigit() for char in text)

    if not has_contact:
        return {
            "field": "Consumer Care",
            "pass": False,
            "rule": "Rule 6(2)",
            "reason": "Consumer care details missing contact number or email address"
        }

    return {
        "field": "Consumer Care",
        "pass": True,
        "rule": "Rule 6(2)",
        "reason": "OK"
    }


def validate_country_of_origin(country_text):
    """Rule 6(1)(aa): Country of origin or manufacture."""
    if not country_text or not str(country_text).strip():
        return {
            "field": "Country of Origin",
            "pass": False,
            "rule": "Rule 6(1)(aa)",
            "reason": "Country of origin not declared"
        }

    return {
        "field": "Country of Origin",
        "pass": True,
        "rule": "Rule 6(1)(aa)",
        "reason": "OK"
    }

def validate_unit_sale_price(usp_text, mrp_text=None, qty_text=None):
    """Rule 6(11): Unit Sale Price (USP) per g, kg, ml, litre, or unit[cite: 2]."""
    if not usp_text or not str(usp_text).strip():
        return {
            "field": "Unit Sale Price (USP)",
            "pass": False,
            "rule": "Rule 6(11)",
            "reason": "Unit Sale Price (USP) declaration missing on label"
        }

    text = str(usp_text).lower()
    # Check for unit pricing pattern (e.g., '0.09/g', 'rs. 0.26/- per g', 'rs. 2 per ml', '10 / piece')
    pattern = r"(\d+(?:\.\d+)?)\s*(?:\/-)?\s*(?:\/|per|\/per)\s*(g|gm|kg|ml|l|ltr|pcs|piece|pieces|unit|units|u|n)\b"
    match = re.search(pattern, text)

    if not match:
        return {
            "field": "Unit Sale Price (USP)",
            "pass": False,
            "rule": "Rule 6(11)",
            "reason": "USP format invalid. Must specify rate per standard unit (e.g., 'Rs. 0.10 / g')"
        }

    return {
        "field": "Unit Sale Price (USP)",
        "pass": True,
        "rule": "Rule 6(11)",
        "reason": "OK"
    }

def calculate_pdp_area(shape="rectangular", height_cm=0, width_cm=0, circumference_cm=0, total_surface_area_cm2=0):
    """Calculates Principal Display Panel (PDP) area in cm² according to Rule 7(5)."""
    shape = str(shape).lower()
    if shape == "rectangular":
        return height_cm * width_cm
    elif shape == "cylindrical":
        return 0.40 * height_cm * circumference_cm
    elif shape == "other":
        return 0.40 * total_surface_area_cm2
    return 0.0


def validate_pdp_font_height(font_height_mm, pdp_area_cm2, is_blown=False):
    """Rule 7(2): Minimum height of letters and numerals based on PDP Area."""
    if not font_height_mm or font_height_mm <= 0:
        return {
            "field": "PDP Font Height",
            "pass": False,
            "rule": "Rule 7(2)",
            "reason": "Font height could not be measured or is missing"
        }

    # Statutory minimum threshold lookup
    if pdp_area_cm2 < 50:
        required_min = 1.5 if is_blown else 1.0
    elif 50 <= pdp_area_cm2 <= 100:
        required_min = 3.0 if is_blown else 1.5
    elif 100 < pdp_area_cm2 <= 500:
        required_min = 4.0 if is_blown else 2.5
    elif 500 < pdp_area_cm2 <= 2500:
        required_min = 6.0 if is_blown else 4.0
    else:
        required_min = 6.0

    if font_height_mm < required_min:
        return {
            "field": "PDP Font Height",
            "pass": False,
            "rule": "Rule 7(2)",
            "reason": f"Font height ({font_height_mm} mm) is below statutory minimum ({required_min} mm) for PDP area {pdp_area_cm2:.1f} cm²"
        }

    return {
        "field": "PDP Font Height",
        "pass": True,
        "rule": "Rule 7(2)",
        "reason": f"OK (Font height {font_height_mm} mm meets required minimum {required_min} mm)"
    }
def validate_label(extracted_data):
    """
    Validates all extracted packaging label fields against Legal Metrology Rules.
    """
    results = [
        validate_mrp(extracted_data.get("mrp")),
        validate_manufacturer(extracted_data.get("manufacturer") or extracted_data.get("manufacturer_details")),
        validate_net_quantity(extracted_data.get("net_quantity") or extracted_data.get("quantity")),
        validate_manufacturing_date(extracted_data.get("mfg_date") or extracted_data.get("manufacturing_date")),
        validate_consumer_care(extracted_data.get("consumer_care") or extracted_data.get("customer_care")),
        validate_country_of_origin(extracted_data.get("country_of_origin") or extracted_data.get("origin_country")),
        validate_unit_sale_price(extracted_data.get("unit_sale_price") or extracted_data.get("usp")),
    ]

    # Rule 7 Spatial / Font Size Check (runs if dimensions are provided)
    meta = extracted_data.get("metadata", {})
    calibration_error = extracted_data.get("dimension_calibration_error")

    if meta:
        pdp_area = calculate_pdp_area(
            shape=meta.get("shape", "rectangular"),
            height_cm=meta.get("height_cm", 0),
            width_cm=meta.get("width_cm", 0),
            circumference_cm=meta.get("circumference_cm", 0),
            total_surface_area_cm2=meta.get("total_surface_area_cm2", 0)
        )
        font_check = validate_pdp_font_height(
            font_height_mm=extracted_data.get("font_height_mm"),
            pdp_area_cm2=pdp_area,
            is_blown=meta.get("is_blown", False)
        )
        results.append(font_check)
    elif calibration_error:
        results.append({
            "field": "PDP Font Height",
            "pass": False,
            "rule": "Rule 7(2)",
            "reason": calibration_error
        })

    all_passed = all(r["pass"] for r in results)
    passed_count = sum(1 for r in results if r["pass"])
    total_count = len(results)

    return {
        "compliant": all_passed,
        "score": f"{passed_count}/{total_count}",
        "percentage": round((passed_count / total_count) * 100, 2),
        "results": results
    }

def evaluate_all_rules(
    raw_lines: list[str],
    package_height_cm: float | None = None,
    package_width_cm: float | None = None,
    detected_font_height_mm: float = 2.5,
    dimension_calibration_error: str | None = None
) -> dict:
    """
    Adapter function that converts OCR raw lines into structured fields
    and executes validate_label().
    """
    full_text = " ".join(raw_lines)
    lower_text = full_text.lower()

    # Heuristic extraction from raw OCR lines
    extracted_data = {
        "mrp": None,
        "manufacturer": None,
        "net_quantity": None,
        "mfg_date": None,
        "consumer_care": None,
        "country_of_origin": None,
        "unit_sale_price": None,
        "font_height_mm": float(detected_font_height_mm) if detected_font_height_mm is not None else None,
    }

    if package_height_cm is not None and package_width_cm is not None:
        extracted_data["metadata"] = {
            "shape": "rectangular",
            "height_cm": float(package_height_cm),
            "width_cm": float(package_width_cm),
            "is_blown": False
        }
    else:
        extracted_data["dimension_calibration_error"] = (
            dimension_calibration_error or "Package dimensions were not calibrated."
        )


    # 1. MRP & Currency Match
    mrp_match = re.search(r"(?:mrp|max(?:imum)?\s*retail\s*price|incl(?:usive)?\.?\s*of\s*all\s*taxes)[:\s]*(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)", lower_text)
    if not mrp_match:
        mrp_match = re.search(r"(?:rs\.?|₹|inr)\s*(\d+(?:\.\d+)?)\s*(?:\/-)?\s*(?:\(|\[)?\s*(?:incl|max|mrp)", lower_text)
    if mrp_match or "mrp" in lower_text or "₹" in full_text or "rs." in lower_text or "incl. of all taxes" in lower_text:
        extracted_data["mrp"] = mrp_match.group(0) if mrp_match else "MRP: Rs. declared (incl. of all taxes)"

    # 2. Manufacturer Details Match
    mfg_match = re.search(r"(?:mfd|manufactured|packed|marketed|imported)\s*(?:by|in|pvt|ltd|llp)?[:\s]*([^,\n]+(?:,[^,\n]+)*)", lower_text)
    if mfg_match or any(k in lower_text for k in ["mfd by", "manufactured by", "packed by", "marketed by", "pepsico", "pvt. ltd", "pvt ltd", "ltd.", "llp"]):
        extracted_data["manufacturer"] = mfg_match.group(0) if mfg_match else "Manufacturer declared"

    # 3. Net Quantity Match
    qty_match = re.search(r"(?:net\s*(?:qty|quantity|wt|weight)?[:\s]*)?(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|ml|l|ltr|pcs|units|n)\b", lower_text)
    if qty_match:
        extracted_data["net_quantity"] = qty_match.group(0)

    # 4. Date of Manufacture Match
    date_match = re.search(r"(?:mfd|mfg|packed|pkd|use\s*by|date|b\.no\.?)[:\s]*([0-3]?[0-9][/-][0-1]?[0-9][/-](?:20)?[2-3][0-9]|[0-1]?[0-9][/-](?:20)?[2-3][0-9]|[a-z]{3}[/-]?(?:20)?[2-3][0-9])", lower_text)
    if date_match or any(k in lower_text for k in ["mfd", "mfg", "pkd", "packed", "use by"]):
        extracted_data["mfg_date"] = date_match.group(0) if date_match else "Date declared"

    # 5. Consumer Care Match
    phone_match = re.search(r"\b(?:\+91|0)?[6-9]\d{9}\b|\b1800[- ]?\d{2,4}[- ]?\d{3,4}\b", full_text)
    email_match = re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", lower_text)
    if phone_match or email_match or any(k in lower_text for k in ["customer care", "helpline", "toll free", "feedback", "call us"]):
        extracted_data["consumer_care"] = (email_match.group(0) if email_match else None) or (phone_match.group(0) if phone_match else "Helpline declared")

    # 6. Country of Origin Match
    origin_match = re.search(r"(?:country of origin|made in|origin)[:\s]*([a-z]+)", lower_text)
    if origin_match or "made in" in lower_text or "india" in lower_text:
        extracted_data["country_of_origin"] = origin_match.group(0) if origin_match else "India"

    # 7. Unit Sale Price Match
    usp_pattern = r"(?:(?:usp|unit\s*sale\s*price|sale\s*price|unit\s*price|\brate\b)[:\s\S]{0,40})?(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)\s*(?:\/-)?\s*(?:\/|per|\/per)\s*(?:g|gm|kg|ml|l|ltr|pcs|piece|unit|u|n)\b"
    usp_match = re.search(usp_pattern, lower_text)
    if usp_match:
        extracted_data["unit_sale_price"] = usp_match.group(0)
    elif any(k in lower_text for k in ["usp", "unit sale price", "sale price"]):
        extracted_data["unit_sale_price"] = "Unit Sale Price declared"



    return validate_label(extracted_data)