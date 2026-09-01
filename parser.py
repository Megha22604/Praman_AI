import re
from rules_engine import normalize_ocr_digits, fuzzy_search_keywords


def clean_text(raw_text):
    """Cleans up raw OCR text strings."""
    if not raw_text:
        return ""
    return " ".join(str(raw_text).split()).strip()


def parse_raw_ocr_lines(lines):
    """
    Parses a raw list of detected text lines from an OCR engine
    and extracts standard LMPC fields with fault-tolerant fuzzy matching.
    """
    parsed = {
        "mrp": None,
        "manufacturer": None,
        "net_quantity": None,
        "mfg_date": None,
        "consumer_care": None,
        "country_of_origin": None,
        "unit_sale_price": None,
        "full_text": " \n ".join([clean_text(l) for l in lines if l])
    }

    for line in lines:
        cleaned_line = clean_text(line)
        if not cleaned_line:
            continue
        line_lower = cleaned_line.lower()
        norm_line_lower = normalize_ocr_digits(cleaned_line).lower()

        # 1. MRP Extraction
        if not parsed["mrp"]:
            mrp_kws = ["mrp", "max retail price", "rs.", "rs ", "₹", "inr", "r5", "mr1p"]
            found, score, _ = fuzzy_search_keywords(norm_line_lower, mrp_kws, min_threshold=0.60)
            if (found or "mrp" in line_lower) and any(c.isdigit() for c in norm_line_lower):
                parsed["mrp"] = cleaned_line

        # 2. Net Quantity Extraction
        if not parsed["net_quantity"]:
            qty_kws = ["net wt", "net weight", "net qty", "net quantity", "weight:", "net content"]
            found_qty_kw, _, _ = fuzzy_search_keywords(line_lower, qty_kws, min_threshold=0.60)
            if found_qty_kw:
                parsed["net_quantity"] = cleaned_line
            else:
                # Standalone pattern check: '500 g', '1 kg', or noisy '500q', '1kq'
                match = re.search(r"\b\d+(?:\.\d+)?\s*(g|gm|gms|kg|ml|l|ltr|pcs|count|q|kq|rni)\b", norm_line_lower)
                if match and "per" not in norm_line_lower and "/" not in norm_line_lower:
                    parsed["net_quantity"] = cleaned_line

        # 3. Unit Sale Price (USP)
        if not parsed["unit_sale_price"]:
            usp_kws = ["usp", "unit sale price", "/ g", "/g", "/ ml", "/ml", "/ kg", "/kg", "per g", "per ml", "rate:"]
            found_usp, score, matched = fuzzy_search_keywords(norm_line_lower, usp_kws, min_threshold=0.60)
            if (found_usp or "/" in line_lower or "per" in line_lower) and any(c.isdigit() for c in norm_line_lower) and ("net" not in line_lower or "usp" in line_lower):
                parsed["unit_sale_price"] = cleaned_line

        # 4. Manufacturing / Packaging Date
        if not parsed["mfg_date"]:
            mfg_kws = ["mfg", "pkd", "packed", "date", "batch", "rnfd", "mfd"]
            found_mfg, _, _ = fuzzy_search_keywords(norm_line_lower, mfg_kws, min_threshold=0.60)
            date_match = re.search(r"\b(0[1-9]|1[0-2]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\/\-\.\s,]+(20\d{2}|\d{2})\b", norm_line_lower)
            if date_match or (found_mfg and any(c.isdigit() for c in norm_line_lower)):
                parsed["mfg_date"] = cleaned_line

        # 5. Manufacturer / Packer Details
        if not parsed["manufacturer"]:
            mfg_by_kws = ["mfd by", "mfg by", "manufactured by", "packed by", "pkd by", "marketed by", "rnfd by", "rnfg by"]
            found_mfg_by, _, _ = fuzzy_search_keywords(line_lower, mfg_by_kws, min_threshold=0.60)
            if found_mfg_by:
                parsed["manufacturer"] = cleaned_line

        # 6. Consumer Care Contact Details
        if not parsed["consumer_care"]:
            care_kws = ["consumer care", "customer care", "toll free", "helpdesk", "feedback", "@", "care@", "helpline"]
            found_care, _, _ = fuzzy_search_keywords(line_lower, care_kws, min_threshold=0.60)
            if found_care or re.search(r"\b1800[- ]?\d{3}[- ]?\d{3,4}\b", norm_line_lower):
                parsed["consumer_care"] = cleaned_line

        # 7. Country of Origin
        if not parsed["country_of_origin"]:
            if any(kw in line_lower for kw in ["country of origin", "origin:", "made in"]):
                parsed["country_of_origin"] = cleaned_line
            elif "india" in line_lower and "manufactured by" not in line_lower and "packed by" not in line_lower:
                parsed["country_of_origin"] = "India"

    return parsed