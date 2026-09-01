import re
import difflib


def calculate_similarity(s1: str, s2: str) -> float:
    """Calculates normalized Levenshtein-like similarity ratio between two strings."""
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, str(s1).lower().strip(), str(s2).lower().strip()).ratio()


def fuzzy_search_keywords(text: str, keywords: list[str], min_threshold: float = 0.75) -> tuple[bool, float, str]:
    """
    Searches for keywords in text using word-by-word token-level fuzzy matching.
    Requires every word in multi-word keywords to meet a minimum threshold (0.60),
    preventing false phrase matches like 'fat free' matching 'toll free'.
    Returns (found, confidence_score, matched_keyword).
    """
    if not text:
        return False, 0.0, ""

    text_lower = str(text).lower()

    # Exact substring match first (confidence 1.0)
    for kw in keywords:
        if kw.lower() in text_lower:
            return True, 1.0, kw

    tokens = re.findall(r'\b[a-z0-9@\.\+\#\-]+\b', text_lower)
    if not tokens:
        return False, 0.0, ""

    max_score = 0.0
    best_match = ""

    for kw in keywords:
        kw_lower = kw.lower()
        kw_words = kw_lower.split()
        kw_len = len(kw_words)

        if kw_len > len(tokens):
            continue

        for i in range(len(tokens) - kw_len + 1):
            phrase_tokens = tokens[i:i + kw_len]
            # Calculate word-by-word similarity
            word_scores = [calculate_similarity(phrase_tokens[j], kw_words[j]) for j in range(kw_len)]

            # Every word in phrase must have at least 0.60 similarity to the keyword word
            if any(ws < 0.60 for ws in word_scores):
                continue

            score = sum(word_scores) / float(kw_len)
            if score > max_score:
                max_score = score
                best_match = kw

    if max_score >= min_threshold:
        return True, round(max_score, 2), best_match
    return False, round(max_score, 2), ""




def normalize_ocr_digits(text: str) -> str:
    """
    Fixes common OCR digit/letter confusions in numeric/alphanumeric strings:
    'O'/'o' -> '0', 'I'/'l' -> '1', 'S'/'s' -> '5' (when adjacent to digits or percentage).
    """
    if not text:
        return ""
    s = str(text)
    # Handle percentage cases like 1OO%, 1O%, 9O%, etc.
    s = re.sub(r'\b1[Oo][Oo]%', '100%', s)
    s = re.sub(r'\b1[Oo]%', '10%', s)
    s = re.sub(r'(?<=\d)[Oo]+(?=%)', lambda m: '0' * len(m.group(0)), s)
    s = re.sub(r'(?<=\d)[Oo]+', lambda m: '0' * len(m.group(0)), s)
    s = re.sub(r'[Oo]+(?=\d)', lambda m: '0' * len(m.group(0)), s)
    s = re.sub(r'(?<=\d)[Il|](?=\d)|(?<=\d)[Il|]\b|\b[Il|](?=\d)', '1', s)
    s = re.sub(r'(?<=\d)[Ss](?=\d)', '5', s)
    return s



def validate_mrp(mrp_text):
    """Rule 6(1)(e): MRP must be declared with a currency symbol and include all taxes."""
    if not mrp_text or not str(mrp_text).strip():
        return {
            "field": "MRP",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(1)(e)",
            "reason": "MRP not found on label"
        }

    norm_text = normalize_ocr_digits(str(mrp_text).lower())

    # Currency match (accepts standard Rs/INR/₹ as well as OCR noisy R5/Re)
    exact_currency = bool(re.search(r"(?:rs\.?|r5|re\.?|₹|inr|rupees|rp)", norm_text))
    has_digits = bool(re.search(r'\d+(?:\.\d+)?', norm_text))

    fuzzy_curr_found, score, matched = fuzzy_search_keywords(norm_text, ["mrp", "price", "retail"], min_threshold=0.60)

    if exact_currency and has_digits:
        return {
            "field": "MRP",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0,
            "rule": "Rule 6(1)(e)",
            "reason": "OK"
        }
    elif (fuzzy_curr_found or has_digits) and ("mrp" in norm_text or score >= 0.60):
        return {
            "field": "MRP",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": round(max(score, 0.70), 2),
            "rule": "Rule 6(1)(e)",
            "reason": f"MRP detected via fuzzy read ('{mrp_text[:30]}'); currency symbol or price formatting requires review"
        }

    return {
        "field": "MRP",
        "pass": False,
        "status": "FAIL",
        "confidence": 0.30,
        "rule": "Rule 6(1)(e)",
        "reason": "MRP present but missing currency symbol (Rs. / ₹ / INR)"
    }


def validate_manufacturer(manufacturer_text):
    """Rule 6(1)(a): Name and complete address of the manufacturer/packer/importer."""
    if not manufacturer_text or not str(manufacturer_text).strip():
        return {
            "field": "Manufacturer Details",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(1)(a)",
            "reason": "Manufacturer/Packer/Importer details not found on label"
        }

    text = str(manufacturer_text)
    text_lower = text.lower()

    keywords = ["mfd by", "manufactured by", "packed by", "marketed by", "imported by", "pkd by", "mfg by", "packer", "importer"]
    exact_match = any(kw in text_lower for kw in keywords)
    fuzzy_found, score, _ = fuzzy_search_keywords(text_lower, keywords, min_threshold=0.60)

    if (exact_match or score >= 0.80) and len(text.strip()) >= 10:
        return {
            "field": "Manufacturer Details",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0 if exact_match else score,
            "rule": "Rule 6(1)(a)",
            "reason": "OK"
        }
    elif fuzzy_found or len(text.strip()) >= 5:
        return {
            "field": "Manufacturer Details",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": round(max(score, 0.65), 2),
            "rule": "Rule 6(1)(a)",
            "reason": f"Manufacturer declaration low-confidence read ('{text[:35]}...'); verify name and complete address"
        }

    return {
        "field": "Manufacturer Details",
        "pass": False,
        "status": "FAIL",
        "confidence": 0.20,
        "rule": "Rule 6(1)(a)",
        "reason": "Manufacturer/Packer/Importer text too short or unreadable"
    }


def validate_net_quantity(quantity_text):
    """Rule 6(1)(c): Net quantity declared in standard units of metric measurement."""
    if not quantity_text or not str(quantity_text).strip():
        return {
            "field": "Net Quantity",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(1)(c)",
            "reason": "Net quantity not found on label"
        }

    norm_text = normalize_ocr_digits(str(quantity_text).lower())

    # Standard pattern match (e.g. '500g', '1 kg', '200 ml', '10 pcs')
    std_pattern = r"\b\d+(?:\.\d+)?\s*(g|gm|gms|kg|ml|l|ltr|liter|litre|m|cm|mm|u|n|pcs|piece|pieces|count)\b"
    if re.search(std_pattern, norm_text):
        return {
            "field": "Net Quantity",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0,
            "rule": "Rule 6(1)(c)",
            "reason": "OK"
        }

    # Noisy OCR pattern match (e.g. '500q' where q is OCR for g, '1kq' for kg, '500rni' for ml)
    fuzzy_pattern = r"\b\d+(?:\.\d+)?\s*(q|qms|kq|rni|1tr|krg)\b"
    match = re.search(fuzzy_pattern, norm_text)
    if match:
        noisy_unit = match.group(1)
        return {
            "field": "Net Quantity",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": 0.75,
            "rule": "Rule 6(1)(c)",
            "reason": f"Net quantity contains OCR noise in unit ('{noisy_unit}' for metric unit); needs review"
        }

    if any(char.isdigit() for char in norm_text):
        return {
            "field": "Net Quantity",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": 0.60,
            "rule": "Rule 6(1)(c)",
            "reason": f"Net quantity numeric value found ('{quantity_text[:20]}') but metric unit is unclear"
        }

    return {
        "field": "Net Quantity",
        "pass": False,
        "status": "FAIL",
        "confidence": 0.20,
        "rule": "Rule 6(1)(c)",
        "reason": "Net quantity missing standard unit of measurement (g, kg, ml, l, pcs, etc.)"
    }


def validate_manufacturing_date(date_text):
    """Rule 6(1)(d): Month and year of manufacture / packing / import."""
    if not date_text or not str(date_text).strip():
        return {
            "field": "Date of Manufacture/Packing",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(1)(d)",
            "reason": "Month/Year of manufacture or packing not found on label"
        }

    norm_text = normalize_ocr_digits(str(date_text).lower())

    # Exact date pattern (e.g., 03/2026, 03-2026, MAR 2026, 03/26)
    date_pattern = r"\b(0[1-9]|1[0-2]|[a-z]{3})[\/\-\.\s]+(20\d{2}|\d{2})\b"
    if re.search(date_pattern, norm_text):
        return {
            "field": "Date of Manufacture/Packing",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0,
            "rule": "Rule 6(1)(d)",
            "reason": "OK"
        }

    # Fuzzy date match with OCR noise (e.g. original text was 'O3/2O26' or 'mfd 03.2026')
    fuzzy_found, score, _ = fuzzy_search_keywords(norm_text, ["mfd", "mfg", "pkd", "packed", "date", "batch"], min_threshold=0.60)
    has_digits = bool(re.search(r'\d+', norm_text))

    if fuzzy_found and has_digits:
        return {
            "field": "Date of Manufacture/Packing",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": round(max(score, 0.70), 2),
            "rule": "Rule 6(1)(d)",
            "reason": f"Date of manufacture detected with OCR noise ('{date_text[:25]}'); month/year format needs review"
        }

    return {
        "field": "Date of Manufacture/Packing",
        "pass": False,
        "status": "FAIL",
        "confidence": 0.20,
        "rule": "Rule 6(1)(d)",
        "reason": "Date of manufacture format unreadable or missing month/year"
    }


def validate_consumer_care(care_text):
    """Rule 6(2): Consumer care details (contact number, email, or address)."""
    if not care_text or not str(care_text).strip():
        return {
            "field": "Consumer Care",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(2)",
            "reason": "Consumer care contact details not found on label"
        }

    norm_text = normalize_ocr_digits(str(care_text).lower())
    orig_text = str(care_text).lower()

    has_email = bool(re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", orig_text))
    has_phone = bool(re.search(r"\b(?:\+91|0)?[6-9]\d{9}\b|\b1800[- ]?\d{3}[- ]?\d{3,4}\b", norm_text))

    keywords = ["customer care", "consumer care", "helpline", "toll free", "feedback", "care@", "contact", "helpdesk"]
    fuzzy_found, score, matched_kw = fuzzy_search_keywords(orig_text, keywords, min_threshold=0.60)

    if has_email or has_phone:
        return {
            "field": "Consumer Care",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0,
            "rule": "Rule 6(2)",
            "reason": "OK"
        }
    elif fuzzy_found or any(char.isdigit() for char in norm_text):
        return {
            "field": "Consumer Care",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": round(max(score, 0.70), 2),
            "rule": "Rule 6(2)",
            "reason": f"Consumer care heading detected ('{matched_kw or care_text[:25]}'); contact number or email format needs manual review"
        }

    return {
        "field": "Consumer Care",
        "pass": False,
        "status": "FAIL",
        "confidence": 0.20,
        "rule": "Rule 6(2)",
        "reason": "Consumer care details missing contact number or email address"
    }


def validate_country_of_origin(country_text):
    """Rule 6(1)(aa): Country of origin or manufacture."""
    if not country_text or not str(country_text).strip():
        return {
            "field": "Country of Origin",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(1)(aa)",
            "reason": "Country of origin not declared"
        }

    text_lower = str(country_text).lower()
    keywords = ["country of origin", "made in", "produced in", "manufactured in", "product of", "origin", "india"]

    exact_match = any(kw in text_lower for kw in keywords)
    fuzzy_found, score, _ = fuzzy_search_keywords(text_lower, keywords, min_threshold=0.60)

    if exact_match:
        return {
            "field": "Country of Origin",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0,
            "rule": "Rule 6(1)(aa)",
            "reason": "OK"
        }
    elif fuzzy_found:
        return {
            "field": "Country of Origin",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": round(score, 2),
            "rule": "Rule 6(1)(aa)",
            "reason": f"Country of origin detected via fuzzy matching ('{country_text[:25]}'); verify declaration"
        }

    return {
        "field": "Country of Origin",
        "pass": True,
        "status": "PASS",
        "confidence": 0.85,
        "rule": "Rule 6(1)(aa)",
        "reason": "OK"
    }


def validate_unit_sale_price(usp_text, mrp_text=None, qty_text=None):
    """Rule 6(11): Unit Sale Price (USP) per g, kg, ml, litre, or unit."""
    if not usp_text or not str(usp_text).strip():
        return {
            "field": "Unit Sale Price (USP)",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 6(11)",
            "reason": "Unit Sale Price (USP) declaration missing on label"
        }

    norm_text = normalize_ocr_digits(str(usp_text).lower())

    # Standard format match (e.g., '0.09/g', 'rs. 2 per ml', '10 / piece')
    std_pattern = r"(\d+(?:\.\d+)?)\s*(?:\/|per)\s*(g|gm|kg|ml|l|ltr|pcs|piece|unit|u|n)"
    if re.search(std_pattern, norm_text):
        return {
            "field": "Unit Sale Price (USP)",
            "pass": True,
            "status": "PASS",
            "confidence": 1.0,
            "rule": "Rule 6(11)",
            "reason": "OK"
        }

    # Fuzzy format match (e.g. OCR noise in unit '0.09/q' or missing slash but rate present)
    fuzzy_pattern = r"(\d+(?:\.\d+)?)\s*(?:\/|per)?\s*(g|gm|kg|ml|l|pcs|q|kq|rni)\b"
    if re.search(fuzzy_pattern, norm_text) or "usp" in norm_text:
        return {
            "field": "Unit Sale Price (USP)",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": 0.70,
            "rule": "Rule 6(11)",
            "reason": f"USP declaration contains OCR noise or non-standard formatting ('{usp_text[:30]}'); needs review"
        }

    return {
        "field": "Unit Sale Price (USP)",
        "pass": False,
        "status": "FAIL",
        "confidence": 0.20,
        "rule": "Rule 6(11)",
        "reason": "USP format invalid. Must specify rate per standard unit (e.g., 'Rs. 0.10 / g')"
    }





def calculate_pdp_area(shape="rectangular", height_cm=0, width_cm=0, circumference_cm=0, total_surface_area_cm2=0):
    """Calculates Principal Display Panel (PDP) area in cm² according to Rule 7(5)."""
    shape = str(shape).lower()
    if shape == "rectangular":
        return float(height_cm) * float(width_cm)
    elif shape == "cylindrical":
        return 0.40 * float(height_cm) * float(circumference_cm)
    elif shape == "other":
        return 0.40 * float(total_surface_area_cm2)
    return 0.0


def validate_pdp_font_height(font_height_mm, pdp_area_cm2, is_blown=False):
    """Rule 7(2): Minimum height of letters and numerals based on PDP Area."""
    if font_height_mm is None or float(font_height_mm) <= 0:
        return {
            "field": "PDP Font Height",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.0,
            "rule": "Rule 7(2)",
            "reason": "Font height could not be measured or is missing"
        }

    fh = float(font_height_mm)
    pdp = float(pdp_area_cm2)

    # Statutory minimum threshold lookup
    if pdp < 50:
        required_min = 1.5 if is_blown else 1.0
    elif 50 <= pdp <= 100:
        required_min = 3.0 if is_blown else 1.5
    elif 100 < pdp <= 500:
        required_min = 4.0 if is_blown else 2.5
    elif 500 < pdp <= 2500:
        required_min = 6.0 if is_blown else 4.0
    else:
        required_min = 6.0

    if fh < required_min:
        # Borderline check (within 15% measurement tolerance)
        if fh >= required_min * 0.85:
            return {
                "field": "PDP Font Height",
                "pass": False,
                "status": "NEEDS REVIEW",
                "confidence": 0.75,
                "rule": "Rule 7(2)",
                "reason": f"Font height ({fh:.1f} mm) is borderline below minimum ({required_min} mm) for PDP area {pdp:.1f} cm²; needs measurement review"
            }
        return {
            "field": "PDP Font Height",
            "pass": False,
            "status": "FAIL",
            "confidence": 0.95,
            "rule": "Rule 7(2)",
            "reason": f"Font height ({fh:.1f} mm) is below statutory minimum ({required_min} mm) for PDP area {pdp:.1f} cm²"
        }

    return {
        "field": "PDP Font Height",
        "pass": True,
        "status": "PASS",
        "confidence": 1.0,
        "rule": "Rule 7(2)",
        "reason": f"OK (Font height {fh:.1f} mm meets required minimum {required_min} mm)"
    }


def detect_misleading_declarations(full_text_or_dict, country_of_origin=None) -> dict:
    """
    Separately analyzes label text for non-standard, misleading, or deceptive declarations
    (e.g., percentage claims, origin contradictions, miracle health claims, promotions).
    NOT evaluated as a statutory mandatory field rule; reported separately as NEEDS REVIEW advisory.
    """
    if isinstance(full_text_or_dict, dict):
        text = " ".join(str(v) for v in full_text_or_dict.values() if v and isinstance(v, str))
    else:
        text = str(full_text_or_dict or "")

    text_lower = text.lower()
    norm_text = normalize_ocr_digits(text_lower)

    findings = []

    # 1. Percentage Claims ("97% fat free", "99% sugar free", "100% cholesterol free", "95% oil free")
    fat_claims = re.finditer(r"\b(?:\d{1,2}|100)%\s*(?:fat\s*free|sugar\s*free|cholesterol\s*free|oil\s*free)\b", norm_text)
    for m in fat_claims:
        claim_str = m.group(0)
        findings.append({
            "claim": claim_str,
            "category": "Percentage Health Claim",
            "status": "NEEDS REVIEW",
            "confidence": 0.85,
            "reason": f"Non-standard percentage claim detected: '{claim_str}' requires human/legal verification"
        })

    # 2. Deceptive Foreign Origin Claims ("Swiss Formula" / "Made in USA" while origin is India)
    origin_str = str(country_of_origin or "").lower()
    is_declared_india = "india" in origin_str or "made in india" in text_lower
    if is_declared_india:
        foreign_claims = re.finditer(r"\b(?:made\s*in\s*(usa|uk|japan|germany|france|italy|china)|swiss\s*(?:formula|quality|chocolate)|imported\s*quality)\b", text_lower)
        for m in foreign_claims:
            claim_str = m.group(0)
            findings.append({
                "claim": claim_str,
                "category": "Origin Inconsistency",
                "status": "NEEDS REVIEW",
                "confidence": 0.90,
                "reason": f"Potential origin contradiction: label highlights '{claim_str}' while declared Country of Origin is India"
            })

    # 3. Miracle, Purity & Absolute Safety Claims ("100% natural", "100% pure", "guaranteed weight loss", "miracle cure for cold", "miracle treatment", "completely safe")
    miracle_claims = re.finditer(
        r"\b(?:"
        r"100%\s*(?:natural|pure|safe|organic)|"
        r"guaranteed\s*weight\s*loss|"
        r"miracle\s*(?:cure(?:\s*for\s*\w+)?|treatment|remedy)|"
        r"cures?\s*(?:cold|cancer|diabetes|disease|\w+)|"
        r"completely\s*safe|"
        r"zero\s*calories|0%\s*calories"
        r")\b",
        text_lower
    )
    for m in miracle_claims:
        claim_str = m.group(0)
        findings.append({
            "claim": claim_str,
            "category": "Unverified Health & Safety Claim",
            "status": "NEEDS REVIEW",
            "confidence": 0.80,
            "reason": f"Unverified health/safety claim detected: '{claim_str}' requires statutory substantiation"
        })

    # Track already matched claims to avoid duplicate findings
    matched_claims_set = set(f["claim"].lower() for f in findings)

    # 5. Fuzzy Match Fallback for OCR Noisy Claims (e.g., 'fat tree', 'garanteed weight loss', 'miracle treatmnt')
    fuzzy_candidates = [
        ("fat free", "Percentage Health Claim", 0.75, "Non-standard percentage claim detected (fuzzy match: 'fat free') requires human/legal verification"),
        ("sugar free", "Percentage Health Claim", 0.75, "Non-standard percentage claim detected (fuzzy match: 'sugar free') requires human/legal verification"),
        ("cholesterol free", "Percentage Health Claim", 0.75, "Non-standard percentage claim detected (fuzzy match: 'cholesterol free') requires human/legal verification"),
        ("oil free", "Percentage Health Claim", 0.75, "Non-standard percentage claim detected (fuzzy match: 'oil free') requires human/legal verification"),
        ("guaranteed weight loss", "Unverified Health & Safety Claim", 0.75, "Unverified health claim detected (fuzzy match: 'guaranteed weight loss') requires statutory substantiation"),
        ("miracle treatment", "Unverified Health & Safety Claim", 0.75, "Unverified treatment claim detected (fuzzy match: 'miracle treatment') requires statutory substantiation"),
        ("miracle cure", "Unverified Health & Safety Claim", 0.75, "Unverified miracle cure claim detected (fuzzy match: 'miracle cure') requires statutory substantiation"),
        ("completely safe", "Unverified Health & Safety Claim", 0.75, "Absolute safety claim detected (fuzzy match: 'completely safe') requires statutory substantiation"),
        ("100% natural", "Unverified Health & Safety Claim", 0.75, "Unverified purity/natural claim detected (fuzzy match: '100% natural') requires statutory substantiation"),
        ("100% pure", "Unverified Health & Safety Claim", 0.75, "Unverified purity claim detected (fuzzy match: '100% pure') requires statutory substantiation"),
    ]

    for target_kw, category, min_score, reason in fuzzy_candidates:
        if not any(target_kw in c for c in matched_claims_set):
            found, score, matched_word = fuzzy_search_keywords(norm_text, [target_kw], min_threshold=min_score)
            if found:
                findings.append({
                    "claim": matched_word or target_kw,
                    "category": category,
                    "status": "NEEDS REVIEW",
                    "confidence": round(score, 2),
                    "reason": reason
                })
                matched_claims_set.add(target_kw)

    if is_declared_india and not any("swiss formula" in c or "made in usa" in c for c in matched_claims_set):
        found_origin, score_origin, kw_origin = fuzzy_search_keywords(text_lower, ["swiss formula", "made in usa", "imported quality"], min_threshold=0.75)
        if found_origin:
            findings.append({
                "claim": kw_origin,
                "category": "Origin Inconsistency",
                "status": "NEEDS REVIEW",
                "confidence": round(score_origin, 2),
                "reason": f"Potential origin contradiction (fuzzy match: '{kw_origin}') while declared Country of Origin is India"
            })



    if findings:
        return {
            "detected": True,
            "status": "NEEDS REVIEW",
            "count": len(findings),
            "findings": findings,
            "summary": f"{len(findings)} non-standard / misleading declaration(s) detected requiring review"
        }

    return {
        "detected": False,
        "status": "PASS",
        "count": 0,
        "findings": [],
        "summary": "No misleading or non-standard declarations detected"
    }


def validate_label(extracted_data):
    """
    Validates all extracted packaging label fields against Legal Metrology Rules.
    Returns structured results including status ('PASS', 'FAIL', 'NEEDS REVIEW')
    and overall compliance status. Misleading claims are reported separately.
    """
    full_text = extracted_data.get("full_text") or " ".join(str(v) for v in extracted_data.values() if v and isinstance(v, str))

    results = [
        validate_mrp(extracted_data.get("mrp")),
        validate_manufacturer(extracted_data.get("manufacturer") or extracted_data.get("manufacturer_details")),
        validate_net_quantity(extracted_data.get("net_quantity") or extracted_data.get("quantity")),
        validate_manufacturing_date(extracted_data.get("mfg_date") or extracted_data.get("manufacturing_date")),
        validate_consumer_care(extracted_data.get("consumer_care") or extracted_data.get("customer_care")),
        validate_country_of_origin(extracted_data.get("country_of_origin") or extracted_data.get("origin_country")),
        validate_unit_sale_price(extracted_data.get("unit_sale_price") or extracted_data.get("usp")),
    ]

    meta = extracted_data.get("metadata", {})
    if meta or extracted_data.get("font_height_mm") is not None:
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

    # Separate Misleading Claims Analysis
    misleading_info = detect_misleading_declarations(
        full_text,
        country_of_origin=extracted_data.get("country_of_origin") or extracted_data.get("origin_country")
    )

    # If misleading claims detected, append an advisory checkpoint to results list for visibility
    if misleading_info["detected"]:
        claims_summary = ", ".join(f"'{f['claim']}'" for f in misleading_info["findings"])
        reasons_summary = "; ".join(f['reason'] for f in misleading_info["findings"])
        results.append({
            "field": "Misleading / Non-Standard Claims (Advisory)",
            "pass": False,
            "status": "NEEDS REVIEW",
            "confidence": 0.85,
            "rule": "Section 39 / Advisory",
            "reason": f"Advisory review: {reasons_summary}"
        })

    has_fails = any(r.get("status") == "FAIL" for r in results)
    has_reviews = any(r.get("status") == "NEEDS REVIEW" for r in results)

    # Statutory score considers only non-advisory checkpoints
    statutory_results = [r for r in results if not str(r.get("rule", "")).startswith("Section 39")]
    passed_count = sum(1 for r in statutory_results if r.get("status") == "PASS")
    total_count = len(statutory_results)

    review_count = sum(1 for r in results if r.get("status") == "NEEDS REVIEW")
    fail_count = sum(1 for r in results if r.get("status") == "FAIL")

    if not has_fails and not has_reviews:
        overall_status = "PASS"
    elif has_fails:
        overall_status = "FAIL"
    else:
        overall_status = "NEEDS REVIEW"


    return {
        "compliant": overall_status == "PASS",
        "status": overall_status,
        "score": f"{passed_count}/{total_count}",
        "pass_count": passed_count,
        "review_count": review_count,
        "fail_count": fail_count,
        "total_count": total_count,
        "percentage": round((passed_count / total_count) * 100, 2),
        "results": results,
        "misleading_declarations": misleading_info
    }



def evaluate_all_rules(raw_lines: list[str], package_height_cm: float = 15.0, package_width_cm: float = 10.0, detected_font_height_mm: float = 2.5) -> dict:
    """
    Adapter function that converts OCR raw lines into structured fields using
    fuzzy matching and digit normalization, then executes validate_label().
    """
    full_text = " \n ".join(raw_lines)
    norm_full_text = normalize_ocr_digits(full_text)
    lower_text = norm_full_text.lower()

    extracted_data = {
        "mrp": None,
        "manufacturer": None,
        "net_quantity": None,
        "mfg_date": None,
        "consumer_care": None,
        "country_of_origin": None,
        "unit_sale_price": None,
        "full_text": full_text,
        "font_height_mm": float(detected_font_height_mm),
        "metadata": {
            "shape": "rectangular",
            "height_cm": float(package_height_cm),
            "width_cm": float(package_width_cm),
            "is_blown": False
        }
    }

    # 1. MRP Match — Strict check to avoid false positives (ignore USP lines)
    _mrp_kw_pattern = re.compile(r'\b(?:mrp|mr1p|max\s*retail\s*price|maximum\s*retail\s*price)\b')
    _currency_pattern = re.compile(r'(?:rs\.\s*\d|rs\s+\d|₹\s*\d|inr\s*\d|r5\s*\d|\brupees\b)')

    for line in raw_lines:
        line_norm = normalize_ocr_digits(line).lower()
        # Skip if this line is explicitly Unit Sale Price (USP)
        if "usp" in line_norm or "unit sale price" in line_norm or "unit price" in line_norm:
            continue
        if _mrp_kw_pattern.search(line_norm) or _currency_pattern.search(line_norm):
            extracted_data["mrp"] = line
            break
    if not extracted_data["mrp"]:
        # Search lower_text excluding explicit USP phrases
        clean_text_for_mrp = re.sub(r'usp[^\n]*', '', lower_text)
        mrp_match = re.search(r"(?:mrp|max(?:imum)?\s*retail\s*price|mr1p)[^\d\n]*?(\d+(?:\.\d+)?)", clean_text_for_mrp)
        if mrp_match:
            extracted_data["mrp"] = mrp_match.group(0)

    # 2. Manufacturer Match
    for line in raw_lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in ["mfd by", "manufactured by", "packed by", "marketed by", "imported by", "pkd by", "mfg by", "rnfd by", "rnfg by"]):
            extracted_data["manufacturer"] = line
            break
    if not extracted_data["manufacturer"]:
        mfg_match = re.search(r"(?:mfd|manufactured|packed|marketed|imported|rnfd|rnfg)\s*by[:\s]*([^,\n]+(?:,[^,\n]+)*)", lower_text)
        if mfg_match:
            extracted_data["manufacturer"] = mfg_match.group(0)

    # 3. Net Quantity Match
    qty_match = re.search(r"(?:net\s*(?:qty|quantity|wt|weight)?[:\s]*)?(\d+(?:\.\d+)?)\s*(kg|g|gm|gms|q|ml|l|ltr|pcs|units|n|kq|rni)\b", lower_text)
    if qty_match:
        extracted_data["net_quantity"] = qty_match.group(0)

    # 4. Date of Manufacture Match
    for line in raw_lines:
        line_norm = normalize_ocr_digits(line).lower()
        if any(kw in line_norm for kw in ["mfd", "mfg", "pkd", "packed", "date", "rnfd"]):
            date_m = re.search(r"\b(0[1-9]|1[0-2]|[a-z]{3})[\/\-\.\s]+(20\d{2}|\d{2})\b", line_norm)
            if date_m:
                extracted_data["mfg_date"] = line
                break
    if not extracted_data["mfg_date"]:
        date_match = re.search(r"(?:mfd|mfg|packed|pkd|date|rnfd)[:\s]*([0-1]?[0-9][/\-\.](?:20)?[2-3][0-9]|[a-z]{3}[/\-\.]?(?:20)?[2-3][0-9])", lower_text)
        if date_match:
            extracted_data["mfg_date"] = date_match.group(0)

    # 5. Consumer Care Match
    phone_match = re.search(r"\b(?:\+91|0)?[6-9]\d{9}\b|\b1800[- ]?\d{3}[- ]?\d{3,4}\b", norm_full_text)
    email_match = re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", lower_text)
    if phone_match or email_match:
        extracted_data["consumer_care"] = (email_match.group(0) if email_match else None) or (phone_match.group(0) if phone_match else "Helpline declared")
    else:
        found, score, kw = fuzzy_search_keywords(lower_text, ["customer care", "helpline", "toll free", "feedback", "care@"], min_threshold=0.60)
        if found:
            extracted_data["consumer_care"] = f"Consumer Care declared ({kw})"

    # 6. Country of Origin Match (Requires explicit origin keywords, not just 'India' in company name)
    origin_explicit = re.search(r"(?:country of origin|origin|product of)[:\s]*([a-z\s]+)", lower_text)
    if origin_explicit:
        extracted_data["country_of_origin"] = origin_explicit.group(0).strip()
    else:
        origin_match = re.search(r"(?:made in|produced in|manufactured in)[:\s]*([a-z\s]+)", lower_text)
        if origin_match:
            extracted_data["country_of_origin"] = origin_match.group(0).strip()
        elif "made in india" in lower_text or "product of india" in lower_text:
            extracted_data["country_of_origin"] = "India"


    # 7. Unit Sale Price Match
    usp_match = re.search(r"(?:usp|unit\s*sale\s*price|rate)[:\s]*(?:rs\.?|inr|₹|r5)?\s*(\d+(?:\.\d+)?)\s*(?:\/|per)\s*(?:g|kg|ml|l|pcs|piece|unit|q)", lower_text)
    if usp_match:
        extracted_data["unit_sale_price"] = usp_match.group(0)
    else:
        found, score, kw = fuzzy_search_keywords(lower_text, ["usp", "unit sale price", "rate"], min_threshold=0.60)
        if found:
            extracted_data["unit_sale_price"] = f"USP detected ({kw})"

    return validate_label(extracted_data)