# -*- coding: utf-8 -*-
"""Heuristic OCR + parsing for UAE Emirates ID card images (camera scans).

English-only: Tesseract runs with ``eng``; Arabic script is stripped from OCR output.
Requires system package ``tesseract-ocr`` and Python ``pytesseract`` (see module manifest).
Images are processed in memory only; callers should not persist raw scans by default.
"""

import base64
import io
import logging
import re
from datetime import date, datetime

from odoo.tools import ustr

_logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    Image = None  # type: ignore

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore

# Lines that are card chrome, not holder data (common OCR false positives for "name")
_NAME_BLACKLIST_RE = re.compile(
    r"united arab emirates|emirates identity|identity card|federal authority|"
    r"id number|idn\b|occupation|nationality|issuing|expir|date of birth|passport|visa\b|"
    r"\bger\b|eeee|eesti|fessri|sb issuing|programmer|employer|issuing place|services|"
    r"festentidentity|resident\s*identity|customs\s*&\s*port",
    re.I,
)

_NAT_GARBAGE_RE = re.compile(
    r"issuing|expir|united arab|identity|federal|id number|jJ0|'\)!",
    re.I,
)

# Single-line OCR noise mistaken for a person name (not holder data)
_EN_NAME_NOISE_WORDS = frozenset(
    {
        "name",
        "english",
        "arabic",
        "sex",
        "gender",
        "male",
        "female",
        "m",
        "f",
        "nat",
        "nationality",
        "occupation",
        "holder",
        "full",
    }
)

_FINAL_VALUE_NOISE_RE = re.compile(
    r"if\s*you\s*find|please\s*return|organization|police\s*station|"
    r"card\s*number|machine\s*readable|resident\s*identity|federal\s*authority|"
    r"customs\s*&\s*port|issuing\s*place|issuing\s*date|occupation|employer|"
    r"date\s*of\s*birth|expiry\s*date|nationality|name\s*:|"
    r"\b(?:I|T)LARE\d{4,}|\b[A-Z0-9]{10,}<{2,}[A-Z0-9<]*",
    re.I,
)

_UAE_CITY_PATTERNS = (
    ("Dubai", r"\bdubai\b"),
    ("Abu Dhabi", r"\babu\s*dhabi\b"),
    ("Sharjah", r"\bsharjah\b"),
    ("Ajman", r"\bajman\b"),
    ("Al Ain", r"\bal\s*ain\b"),
    ("Ras Al Khaimah", r"\bras\s*al\s*khaimah\b|\br\.?a\.?k\.?\b"),
    ("Fujairah", r"\bfujairah\b"),
    ("Umm Al Quwain", r"\bumm\s*al\s*quwain\b"),
)


def _b64_to_image(b64_data):
    if not b64_data or not Image:
        return None
    raw = base64.b64decode(b64_data)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _preprocess_for_ocr(img):
    """Two fast variants; binarize is added only when OCR quality is still low."""
    if not img:
        return []
    w, h = img.size
    scale = max(1.0, 1600.0 / max(w, h))
    if scale > 1.01:
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    gray = img.convert("L")
    base = ImageEnhance.Contrast(gray).enhance(2.0).filter(ImageFilter.SHARPEN)
    strong = ImageEnhance.Contrast(gray).enhance(2.6)
    return [base, strong]


def _preprocess_binarize(gray_l):
    """Heavy last-resort pass (only if fast OCR misses ID/MRZ/dates)."""
    return gray_l.point(lambda p: 255 if p > 140 else 0)


def _ocr_good_enough(text):
    """Stop early when text clearly contains ID / MRZ / multiple dates."""
    t = (text or "").strip()
    if len(t) < 28:
        return False
    if re.search(r"784[-\s]?\d{4}", t):
        return True
    if len(re.findall(r"\d{2}[/.-]\d{2}[/.-]\d{4}", t)) >= 2:
        return True
    compact = re.sub(r"\s+", "", t)
    if re.search(r"[A-Z]{2,}<+[A-Z0-9<]{6,}", compact):
        return True
    return False


def _ocr_quality_score(text):
    """Simple quality score: rewards IDs/dates/MRZ-like blocks and alphabetic content."""
    if not text:
        return 0
    score = len(text)
    score += len(re.findall(r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d\b", text)) * 300
    score += len(re.findall(r"\b\d{2}[/.-]\d{2}[/.-]\d{4}\b", text)) * 60
    score += len(re.findall(r"\b[A-Z]{2,}<+[A-Z0-9<]{8,}\b", text)) * 80
    score += len(re.findall(r"[A-Za-z]{3,}", text)) * 2
    return score


def _ocr_emirates_id_mrz_strip(img):
    """Extra passes on the bottom of the card (MRZ band). Only used for back scans."""
    if not img or not pytesseract:
        return []
    w, h = img.size
    if h < 120 or w < 120:
        return []
    # MRZ occupies the lower third to half of the back; include margin above for hologram bleed.
    y0 = int(h * 0.52)
    crop = img.crop((0, y0, w, h))
    cw, ch = crop.size
    sc = max(1.0, 2400.0 / max(cw, ch))
    if sc > 1.02:
        crop = crop.resize((int(cw * sc), int(ch * sc)), Image.Resampling.LANCZOS)
    gray = crop.convert("L")
    procs = [
        ImageEnhance.Contrast(gray).enhance(2.4).filter(ImageFilter.SHARPEN),
        _preprocess_binarize(ImageEnhance.Contrast(gray).enhance(2.0)),
    ]
    chunks = []
    for proc in procs:
        for psm in (7, 6, 11):
            try:
                t = (
                    pytesseract.image_to_string(proc, lang="eng", config=f"--oem 3 --psm {psm}") or ""
                ).strip()
                if len(t) >= 8:
                    chunks.append(t)
            except Exception as e:
                _logger.debug("MRZ strip OCR psm=%s failed: %s", psm, e)
    return chunks


_ARABIC_SCRIPT_BLOCKS_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+"
)
_RTL_MARKS_RE = re.compile(r"[\u200e\u200f\u202a-\u202e]")


def _strip_arabic_script_from_ocr_output(s):
    """Remove Arabic script from Tesseract output while keeping line structure (English-only)."""
    if not s:
        return ""
    out = []
    for line in s.splitlines():
        line = _RTL_MARKS_RE.sub("", line)
        line = _ARABIC_SCRIPT_BLOCKS_RE.sub(" ", line)
        line = re.sub(r"  +", " ", line).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def image_bytes_to_text(image_b64, eid_side=None):
    """Return UTF-8 text from a single base64-encoded image (no data: prefix).

    ``eid_side`` — ``\"front\"`` | ``\"back\"`` | ``None``. Back scans append MRZ-focused
    crops (same card type only) for stable TD1 reads.

    Short pipeline (about 2–8 Tesseract runs per image) so mobile extraction stays responsive.
    """
    if not pytesseract:
        raise RuntimeError(
            "pytesseract is not installed. Install Python package 'pytesseract' "
            "and system package 'tesseract-ocr' on the Odoo server."
        )
    if not Image:
        raise RuntimeError("Pillow (PIL) is required for Emirates ID OCR.")
    img = _b64_to_image(image_b64)
    if not img:
        return ""
    proc_variants = _preprocess_for_ocr(img)
    if not proc_variants:
        return ""

    def _run_ocr(proc, lang, psm):
        cfg = f"--oem 3 --psm {psm}"
        try:
            return (pytesseract.image_to_string(proc, lang=lang, config=cfg) or "").strip()
        except Exception as e:
            _logger.debug("Tesseract lang=%s psm=%s failed: %s", lang, psm, e)
            return ""

    merged = []
    seen = set()
    runs = 0

    def _add(chunk):
        if not chunk or chunk in seen:
            return
        seen.add(chunk)
        merged.append(chunk)

    blob = ""
    for proc in proc_variants:
        runs += 1
        _add(_run_ocr(proc, "eng", 6))
        blob = "\n".join(merged)
        if _ocr_good_enough(blob):
            break
        runs += 1
        _add(_run_ocr(proc, "eng", 6))
        blob = "\n".join(merged)
        if _ocr_good_enough(blob):
            break

    if not _ocr_good_enough(blob) and proc_variants:
        runs += 1
        _add(_run_ocr(proc_variants[0], "eng", 11))
        blob = "\n".join(merged)

    if not _ocr_good_enough(blob):
        try:
            gray = img.convert("L")
            w, h = gray.size
            sc = max(1.0, 1600.0 / max(w, h))
            if sc > 1.01:
                gray = gray.resize((int(w * sc), int(h * sc)), Image.Resampling.LANCZOS)
            bin_proc = _preprocess_binarize(gray)
            runs += 1
            _add(_run_ocr(bin_proc, "eng", 6))
            blob = "\n".join(merged)
        except Exception as e:
            _logger.debug("Binarize OCR skipped: %s", e)

    if not merged:
        try:
            runs += 1
            chunk = (
                pytesseract.image_to_string(proc_variants[0], lang="eng", config="--oem 3 --psm 6") or ""
            ).strip()
            if chunk:
                merged.append(chunk)
        except Exception as e:
            _logger.exception("Tesseract OCR failed: %s", e)
            raise RuntimeError(
                "OCR engine failed. Ensure 'tesseract-ocr' is installed on the server "
                "and tesseract is on PATH."
            ) from e

    if eid_side == "back" and img:
        for piece in _ocr_emirates_id_mrz_strip(img):
            _add(piece)

    blob = "\n".join(merged)
    blob = _strip_arabic_script_from_ocr_output(blob)
    _logger.debug(
        "Emirates OCR finished in %s pass(es), side=%s, merged_len=%s",
        runs,
        eid_side,
        len(blob),
    )
    return ustr(blob)


def _parse_date_groups(y, mo, d):
    try:
        return datetime(y, mo, d).date()
    except ValueError:
        return None


def _collect_all_dates(text):
    """Every DD/MM/YYYY (and ISO) date in text."""
    found = []
    for m in re.finditer(r"\b(\d{2})[/.-](\d{2})[/.-](\d{4})\b", text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = _parse_date_groups(y, mo, d)
        if dt:
            found.append(dt)
    for m in re.finditer(r"\b(\d{4})[/.-](\d{2})[/.-](\d{2})\b", text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = _parse_date_groups(y, mo, d)
        if dt:
            found.append(dt)
    return found


def _dates_from_labels(text):
    """Prefer explicit Expiry / Issue / Birth lines (reduces swap when card is expired)."""
    res = {"issue": None, "expiry": None, "dob": None}
    compact = re.sub(r"\s+", " ", text)
    patterns = [
        (
            "dob",
            re.compile(
                r"(?:date\s*of\s*birth|birth\s*date|d\.?\s*o\.?\s*b\.?|dob)\s*[:\s/]*"
                r"(\d{2})[/.-](\d{2})[/.-](\d{4})",
                re.I,
            ),
        ),
        (
            "expiry",
            re.compile(
                r"(?:expir(?:y|es)?|valid(?:ity)?\s*(?:until|to)?|valid\s*until)\s*[:\s/]*"
                r"(\d{2})[/.-](\d{2})[/.-](\d{4})",
                re.I,
            ),
        ),
        (
            "issue",
            re.compile(
                r"(?:issuing\s*date|issue\s*date|date\s*of\s*issue)\s*[:\s/]*"
                r"(\d{2})[/.-](\d{2})[/.-](\d{4})",
                re.I,
            ),
        ),
    ]
    for key, rx in patterns:
        m = rx.search(compact) or rx.search(text)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dt = _parse_date_groups(y, mo, d)
            if dt:
                res[key] = dt
    return res


def _assign_card_dates_from_list(found_dates, labeled):
    """Merge label hints with chronological heuristic for UAE EID.

    Expiry is often *before* 'today' on expired cards; never treat 'future only' as expiry.
    Typical ordering after sort: DOB < Issue < Expiry.
    """
    labeled = {k: v for k, v in labeled.items() if v}
    if labeled.get("dob") and labeled.get("expiry"):
        return {
            "dob": labeled["dob"],
            "issue": labeled.get("issue"),
            "expiry": labeled["expiry"],
        }
    found_dates = sorted(set(found_dates))
    if not found_dates:
        return {"dob": labeled.get("dob"), "issue": labeled.get("issue"), "expiry": labeled.get("expiry")}

    dob = labeled.get("dob")
    issue = labeled.get("issue")
    expiry = labeled.get("expiry")

    if len(found_dates) >= 2:
        if dob is None:
            dob = found_dates[0]
        if expiry is None:
            expiry = found_dates[-1]
        if issue is None and len(found_dates) >= 3:
            issue = found_dates[-2]
    elif len(found_dates) == 1:
        only = found_dates[0]
        if dob is None and expiry is None:
            if only.year < 1995:
                dob = only
            else:
                expiry = only
        elif dob is None and expiry is not None and only < expiry:
            dob = only
        elif expiry is None and dob is not None and only > dob:
            expiry = only

    if issue is None and dob and expiry:
        between = [d for d in found_dates if dob < d < expiry]
        if len(between) == 1:
            issue = between[0]
        elif len(between) > 1:
            issue = between[0]

    return {"dob": dob, "issue": issue, "expiry": expiry}


def _parse_dates(combined_text):
    labeled = _dates_from_labels(combined_text)
    found = _collect_all_dates(combined_text)
    return _assign_card_dates_from_list(found, labeled)


def _parse_dates_for_eid(front_text, back_text, combined_text):
    """Merge label hints from front and back, then all numeric dates from the full OCR."""
    labeled = {}
    for src in (front_text, back_text, combined_text):
        if not src:
            continue
        part = _dates_from_labels(src)
        for key in ("dob", "issue", "expiry"):
            if part.get(key) and not labeled.get(key):
                labeled[key] = part[key]
    found = sorted(set(_collect_all_dates(combined_text or "")))
    return _assign_card_dates_from_list(found, labeled)


def _parse_id_number(text):
    patterns = [
        r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d\b",
        r"\b784\d{12}\b",
        r"\b784[-\s]?\d{4}[-\s]?\d{7}[-\s]?\d{1}\b",
    ]
    compact = re.sub(r"\s+", " ", text)
    for pat in patterns:
        m = re.search(pat, compact)
        if m:
            raw = m.group(0)
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 15:
                d = digits[:15]
                return f"{d[:3]}-{d[3:7]}-{d[7:14]}-{d[14]}"
    return ""


def _parse_gender(text):
    u = text.upper()
    if re.search(r"\b(MALE|M\b)\b", u):
        return "male"
    if re.search(r"\b(FEMALE|F\b)\b", u):
        return "female"
    return ""


def _line_after_label(text, label_variants):
    """Return first non-empty line after a label-only row (case-insensitive).

    If the label and value are on the same line, do not skip to the next line
    (avoids e.g. nationality = \"Male\" when the real nationality line is noisy).
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, raw in enumerate(lines):
        ln_low = raw.lower()
        for lab in label_variants:
            lab_low = lab.lower()
            if lab_low not in ln_low:
                continue
            pos = ln_low.find(lab_low)
            if pos != 0:
                continue
            after = raw[pos + len(lab) :].strip(" :\t-/")
            if after:
                continue
            if i + 1 < len(lines):
                return lines[i + 1]
    return ""


def _latin_only(s):
    """Strip Arabic / RTL marks; keep English (and digits/punctuation) for ID fields."""
    if not s:
        return ""
    s = re.sub(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+", " ", s)
    s = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _inline_value_after_label(text, label_variants):
    """Extract value when label and value are on same line (e.g. Name: John Doe)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for raw in lines:
        low = raw.lower()
        for lab in label_variants:
            lab_low = lab.lower()
            if low.startswith(lab_low):
                rest = raw[len(lab) :].strip(" :\t-/.")
                if rest:
                    return rest
    return ""


def _looks_like_holder_name_english(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) < 3 or len(s) > 120:
        return False
    if "<<" in s or s.lstrip().startswith("<"):
        return False
    first_word = s.split()[0].lower() if s.split() else ""
    if first_word in _EN_NAME_NOISE_WORDS or s.lower() in _EN_NAME_NOISE_WORDS:
        return False
    if _NAME_BLACKLIST_RE.search(s):
        return False
    if re.search(r"\d{3,}", s):
        return False
    letters = sum(1 for c in s if c.isalpha())
    if letters < len(s) * 0.5:
        return False
    words = s.split()
    if len(words) > 12:
        return False
    return True


def _parse_name_after_name_colon(text):
    """Emirates ID front: English name is after 'Name:' mid-line (OCR adds junk before the label)."""
    for raw in text.splitlines():
        m = re.search(r"(?i)\bname\s*:\s*([A-Za-z].*)", raw)
        if not m:
            continue
        rest = m.group(1).strip()
        rest = re.split(
            r"\s+\d+\s*<<<|\s*<<<|\s*nationality\b|\s*date\s*of\s*birth\b|\s*\bsex\b",
            rest,
            1,
            flags=re.I,
        )[0].strip(" -/|•7")
        rest = re.sub(r"\s+", " ", rest)
        if _looks_like_holder_name_english(rest):
            return rest
    return ""


def _parse_name_english_regex(text):
    """Fallback: Name: anywhere in blob (multiline)."""
    m = re.search(
        r"(?is)\bname\s*:\s*([A-Za-z][A-Za-z\-\s\']{5,118}?)"
        r"(?=\s*(?:nationality|date\s*of|\bsex\b|784|\d\s*<<<|<<<)|\n|$)",
        text,
    )
    if m:
        val = re.sub(r"\s+", " ", m.group(1).strip(" -/|•"))
        if _looks_like_holder_name_english(val):
            return val
    return ""


def _prefer_mrz_name(english_name, mrz_name):
    """Prefer front-of-card English when it looks complete; MRZ is fallback (often surname-first)."""
    mrz_name = (mrz_name or "").strip()
    if mrz_name and ("<<" in mrz_name or mrz_name.startswith("<")):
        mrz_name = ""
    if not mrz_name:
        return english_name or ""
    if not english_name:
        return mrz_name
    ew = english_name.split()
    if len(ew) >= 3 and not _NAME_BLACKLIST_RE.search(english_name) and len(english_name) <= 100:
        return english_name
    if _NAME_BLACKLIST_RE.search(english_name):
        return mrz_name
    if len(english_name) > 100:
        return mrz_name
    mw = mrz_name.split()
    if len(ew) == 1 and len(mw) >= 2:
        return mrz_name
    caps_words = sum(1 for w in ew if len(w) > 2 and w.isupper())
    if caps_words >= 2:
        return mrz_name
    return english_name


def _parse_name_english(text):
    col = _parse_name_after_name_colon(text)
    if col:
        return col
    rx = _parse_name_english_regex(text)
    if rx:
        return rx
    inline = _inline_value_after_label(
        text,
        (
            "full name",
            "name (english)",
            "name english",
            "english name",
            "holder name",
            "name:",
            "name",
        ),
    )
    if inline and _looks_like_holder_name_english(inline):
        return re.sub(r"\s+", " ", inline).strip()
    cand = _line_after_label(
        text,
        (
            "full name",
            "name (english)",
            "name english",
            "english name",
            "holder name",
            "name:",
            "name",
        ),
    )
    if cand and _looks_like_holder_name_english(cand):
        return re.sub(r"\s+", " ", cand).strip()
    best = ""
    best_score = 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not _looks_like_holder_name_english(ln):
            continue
        words = ln.split()
        score = len(ln)
        if 2 <= len(words) <= 6:
            score += 30
        if re.search(r"[a-z]", ln) and re.search(r"[A-Z]", ln):
            score += 10
        if score > best_score:
            best_score = score
            best = ln
    return best.strip()


def _clean_nationality(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r"^[\d\s/'.-]+", "", s).strip()
    return s


def _nationality_acceptable(rest):
    """Reject OCR fragments (e.g. 'Sb') that are not plausible country text."""
    if not rest or rest.lower() in _EN_NAME_NOISE_WORDS:
        return False
    if _NAT_GARBAGE_RE.search(rest):
        return False
    if len(re.sub(r"[^A-Za-z]", "", rest)) < 3:
        return False
    if not re.match(r"^[A-Za-z\s\-']{2,}$", rest):
        return False
    if len(rest) > 60:
        return False
    return True


def _nationality_from_nationality_line(line):
    """Parse value from a line that starts with Nationality (possibly noisy OCR)."""
    rest = re.sub(r"^\s*nationality\s*[:\s/]*", "", line, flags=re.I).strip()
    if not rest:
        return ""
    rest = re.split(
        r"\b(?:issuing|issue|expir|expiry|date|united|federal|identity|emirates)\b",
        rest,
        1,
        flags=re.I,
    )[0].strip(" /'")
    rest = _clean_nationality(rest)
    if not _nationality_acceptable(rest):
        return ""
    return rest.strip()


def _parse_nationality(text):
    inline = _inline_value_after_label(text, ("nationality", "nat:", "nationality:"))
    inline = _clean_nationality(inline)
    if inline and _nationality_acceptable(inline):
        return inline.strip()
    cand = _line_after_label(text, ("nationality", "nat:", "nationality:"))
    cand = _clean_nationality(cand)
    if cand and _nationality_acceptable(cand):
        return cand.strip()
    for ln in text.splitlines():
        raw = ln.strip()
        if re.match(r"^\s*nationality\b", raw, re.I):
            same = _nationality_from_nationality_line(raw)
            if same:
                return same
    m = re.search(
        r"nationality\s*[:\s/]+\s*([A-Za-z][A-Za-z\s\-']{1,45}?)(?=\s*(?:issuing|expir|date|\n|$))",
        text,
        re.I,
    )
    if m:
        val = _clean_nationality(m.group(1))
        if val and _nationality_acceptable(val):
            return val
    return ""


def _parse_labeled_field(text, labels):
    for lab in labels:
        m = re.search(rf"{re.escape(lab)}\s*[:\s/]+\s*(.+?)(?:\n|$)", text, re.I | re.DOTALL)
        if m:
            val = m.group(1).strip().split("\n")[0].strip()
            if val and len(val) < 200 and not _NAT_GARBAGE_RE.search(val):
                return val
    return ""


def _strip_eid_field_value(raw, stop_at=None):
    """Cut OCR field value at next label / noise."""
    if not raw:
        return ""
    s = re.sub(r"\s+", " ", raw).strip()
    if stop_at:
        low = s.lower()
        for phrase in stop_at:
            idx = low.find(phrase.lower())
            if idx > 0:
                s = s[:idx].strip(" ,.-|")
                low = s.lower()
    s = re.sub(r"\s+[aA]\s*$", "", s).strip()
    return s


def _acceptable_eid_long_field(val, min_len=2, max_len=200):
    """Allow UAE company names (may contain 'United Arab Emirates'); reject obvious OCR junk."""
    if not val or len(val) < min_len or len(val) > max_len:
        return False
    if re.search(r"jJ0|'\)\!|<<<<+", val):
        return False
    letters = sum(1 for c in val if c.isalpha())
    return letters >= max(2, min_len)


def _cleanup_mixed_employer(val):
    """Latin company name with Arabic/OCR noise between words."""
    if not val:
        return ""
    s = re.sub(r"[\u200e\u200f]", "", val)
    s = re.sub(r"[\u0600-\u06FF]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+\d+\s*$", "", s)
    s = re.sub(r"\s+[A-Z]{1,3}\s*$", "", s)
    return s.strip(" -–|([.,;")


def _trim_occupation_noise(val):
    parts = val.split()
    while parts and parts[-1] in ("=", "|", ":", "-", "/", ".", "_"):
        parts.pop()
    while len(parts) >= 2 and len(parts[-1]) <= 2 and parts[-1].isalpha():
        parts.pop()
    while parts and parts[-1].lower() in ("ee", "pe", "a", "e", "te", "be"):
        parts.pop()
    s = " ".join(parts).strip()
    s = re.sub(r'(?i)\s*[=|]+\s*$', "", s)
    return s.strip(" -|:=._")


def _trim_trailing_eid_value_noise(s):
    """Strip trailing OCR junk: ``| : eae`` (Arabic bleed), lone ``=``, pipes, colons."""
    if not s:
        return s
    s = s.strip()
    s = re.sub(r"(?i)\s*\|\s*:?\s*[a-z]{1,12}\s*$", "", s)
    s = re.sub(r"(?i)\s+:\s+[a-z]{1,12}\s*$", "", s)
    for _ in range(4):
        t = re.sub(r"(?i)\s*[=|]+(?=\s*$)", "", s)
        t = re.sub(r"(?i)[=|:._\-]+\s*$", "", t).strip()
        if t == s:
            break
        s = t
    if re.search(r"(?i)\)\s*$", s):
        m = re.search(r"(?i)(\(\s*l\s+l\s+c\s*\)|\(l\.?\s*l\.?\s*c\.?\))\s*(.+)$", s)
        if m and m.group(2):
            tail = m.group(2).strip()
            if len(tail) <= 20 and re.search(r"[|:]", tail) and not re.search(
                r"(?i)\bu\.?\s*a\.?\s*e\b", tail
            ):
                s = s[: m.start(2)].strip()
    return s.strip(" -|:=._")


def _cleanup_final_field_text(val):
    if not val:
        return ""
    val = _latin_only(val)
    val = re.sub(r"\s+", " ", val).strip()
    val = _trim_trailing_eid_value_noise(val)
    return val.strip(" -|:=._,;/")


def _looks_like_noisy_final_value(val):
    if not val:
        return True
    if _FINAL_VALUE_NOISE_RE.search(val):
        return True
    if "<<" in val or val.lstrip().startswith("<"):
        return True
    if re.search(r"\d{6,}", val):
        return True
    return False


def _sanitize_final_name(val):
    val = _cleanup_final_field_text(val)
    if not val:
        return ""
    val = re.sub(r"(?i)^\s*name\s*:?\s*", "", val).strip()
    val = re.split(
        r"(?i)\s+(?:nationality|date\s*of\s*birth|dob|sex|gender|id\s*number|expiry)\b",
        val,
        1,
    )[0].strip()
    if _looks_like_noisy_final_value(val):
        return ""
    if not _looks_like_holder_name_english(val):
        return ""
    return val


def _sanitize_final_nationality(val):
    val = _cleanup_final_field_text(val)
    if not val:
        return ""
    val = re.sub(r"(?i)^\s*nationality\s*:?\s*", "", val).strip()
    if not _nationality_acceptable(val):
        return ""
    return " ".join(w.capitalize() for w in val.split())


def _sanitize_final_occupation(val):
    val = _cleanup_final_field_text(val)
    if not val:
        return ""
    val = re.sub(rf"(?i)^\s*{_OCC_LABEL_RE}\s*:?\s*", "", val).strip()
    val = _trim_occupation_value_fragment(val)
    val = _trim_occupation_noise(val)
    if _looks_like_noisy_final_value(val):
        return ""
    if not _acceptable_eid_long_field(val, min_len=3, max_len=120):
        return ""
    return val


def _sanitize_final_employer(val):
    val = _cleanup_final_field_text(val)
    if not val:
        return ""
    val = re.sub(r"(?i)^\s*(?:employer|em\s*ployer|ernployer)\s*:?\s*", "", val).strip()
    val = _short_employer_company(_cleanup_mixed_employer(val))
    if _looks_like_noisy_final_value(val):
        return ""
    if not _acceptable_eid_long_field(val, min_len=4, max_len=220):
        return ""
    return _normalize_known_employer_typo(val)


def _sanitize_final_issuing_place(val):
    val = _cleanup_final_field_text(val)
    if not val:
        return ""
    for label, pat in _UAE_CITY_PATTERNS:
        if re.search(pat, val, re.I):
            return label
    return ""


# OCR typos on Emirates ID back (English-only pipeline)
_OCC_LABEL_RE = r"(?:[o0]ccupation|occupati[o0]n|occupation|professi[o0]n|profession|job\s*title)"


def _parse_occupation_fuzzy(text):
    """English-only heuristics when 'Occupation:' is garbled (common on phone OCR)."""
    lat = _latin_only(text)
    m = re.search(r"(?i)\b(computer\s+programmer|software\s+engineer|sales\s+manager|project\s+manager)\b", lat)
    if m:
        return " ".join(w.capitalize() for w in m.group(1).split())
    m = re.search(
        rf"(?i){_OCC_LABEL_RE}\s*[:\s]*([A-Za-z][A-Za-z\s\-]{{3,70}}?)"
        r"(?=\s*(?:employer|em\s*ployer|issuing|berkeley|berte|if\s*you|$|\n))",
        lat,
    )
    if m:
        val = _trim_occupation_noise(m.group(1).strip())
        if _acceptable_eid_long_field(val, min_len=3, max_len=110):
            return val
    return ""


def _trim_employer_value_fragment(s):
    """On collapsed OCR lines, cut employer value before the next obvious field or MRZ."""
    if not s:
        return ""
    s = s.strip()
    m = re.search(
        r"(?i)\s+(?=issuing\s*place|occupation\s*:|employer\s*:|card\s*number|"
        r"SSSUING|if\s*you|please\s*return|ILARE\d|machine\s*readable|"
        r"[A-Z]{2,}<+<[A-Z])",
        s,
    )
    if m:
        s = s[: m.start()].strip()
    if len(s) > 200:
        s = s[:200].rsplit(None, 1)[0]
    return s.strip()


def _trim_occupation_value_fragment(s):
    """Cut occupation value on one-line OCR before employer / issuing / MRZ."""
    if not s:
        return ""
    s = s.strip()
    m = re.search(
        r"(?i)\s+(?=employer\s*:|em\s*ployer\s*:|issuing\s*place|SSSUING|card\s*number|"
        r"berkeley|berteley|if\s*you|please\s*return|ILARE\d|[A-Z]{2,}<{2,})",
        s,
    )
    if m:
        s = s[: m.start()].strip()
    if len(s) > 130:
        s = s[:130].rsplit(None, 1)[0]
    return s.strip()


def _parse_occupation_glue_friendly(text):
    """Occupation when OCR glues labels (no newlines); tolerates ``0ccupation``, missing colon."""
    if not text:
        return ""
    stop_re = (
        r"(?=\s+(?:employer|em\s*ployer)\s*:|issuing\s*place|SSSUING|berkeley|berteley|"
        r"if\s*you|card\s*number|ILARE\d|[A-Z]{2,}<{2,}|\n|$)"
    )
    m = re.search(
        rf"(?is)\b{_OCC_LABEL_RE}\b\s*[:\s/]*\s*([A-Za-z][A-Za-z0-9\s\-,&'/]{{2,95}}?){stop_re}",
        text,
    )
    if not m:
        return ""
    val = _trim_occupation_noise(_cleanup_mixed_employer(m.group(1).strip(" :.-|/")))
    if _acceptable_eid_long_field(val, min_len=3, max_len=120):
        return val
    return ""


def _parse_employer_glue_friendly(text):
    """Employer when labels are on one line or heavily merged."""
    if not text:
        return ""
    stop_re = (
        r"(?=\s+issuing\s*place|SSSUING|\boccupation\b|if\s*you|card\s*number|"
        r"ILARE\d|please\s*return|[A-Z]{2,}<{2,}|\n|$)"
    )
    m = re.search(
        rf"(?is)\b(?:employer|em\s*ployer|ernployer)\b\s*[:\s/]*\s*(.+?){stop_re}",
        text,
    )
    if not m:
        return ""
    val = _short_employer_company(_cleanup_mixed_employer(m.group(1).strip()))
    if _acceptable_eid_long_field(val, min_len=4, max_len=220):
        return val
    return ""


def _parse_occupation_after_colon_lat(lat):
    """``Occupation:`` on Latin-collapsed back OCR (single long line)."""
    if not lat:
        return ""
    m = re.search(rf"(?i){_OCC_LABEL_RE}\s*:\s*", lat)
    if not m:
        return ""
    frag = _trim_occupation_value_fragment(lat[m.end() :])
    val = _trim_occupation_noise(_cleanup_mixed_employer(frag))
    if _acceptable_eid_long_field(val, min_len=3, max_len=120):
        return val
    return ""


def _mrz_digit_pair(a, b, c):
    """Parse YY MM DD from MRZ allowing ``O`` misread as ``0``."""

    def d(x):
        return int(x.replace("O", "0").replace("o", "0"))

    return d(a), d(b), d(c)


def _normalize_known_employer_typo(s):
    """Resident cards often OCR ``Berkeley`` as ``Berteley``; normalize for display."""
    if not s:
        return s
    return re.sub(r"(?i)\bberteley\b", "Berkeley", s)


def _short_employer_company(s):
    """Phone OCR often concatenates the rest of the card onto one line after the company name."""
    if not s:
        return s
    s = s.strip()
    m = re.search(
        r"\s{2,}\d|\sRS\s|\sINT\s|SSSUING|Diehl|\.\.\.\s*Pe|pe PS|please return",
        s,
        re.I,
    )
    if m and m.start() > 12:
        s = s[: m.start()].strip(" :.,-|")
    if len(s) > 88:
        s = s[:88].rsplit(None, 1)[0]
    return s.strip(" :.,-|")


def _parse_employer_after_employer_colon(lat):
    """Take everything after ``Employer:`` until the next label / MRZ; Latin-only text."""
    if not lat:
        return ""
    m = re.search(r"(?i)(?:employer|em\s*ployer)\s*:\s*", lat)
    if not m:
        return ""
    frag = _trim_employer_value_fragment(lat[m.end() :])
    val = _short_employer_company(_cleanup_mixed_employer(frag))
    if _acceptable_eid_long_field(val, min_len=4, max_len=220):
        return val
    return ""


def _extract_uae_llc_suffix(tail):
    """Only accept a clear ``U.a.e`` + optional ``(L L C)`` after ``Services:``; drop hologram noise."""
    if not tail:
        return ""
    t = _cleanup_mixed_employer(tail)
    m = re.search(
        r"(?i)(u\.\s*a\.\s*e)\s*(\(\s*l\s+l\s+c\s*\)|\(l\.?\s*l\.?\s*c\.?\))?",
        t,
    )
    if not m:
        return ""
    return (m.group(1).strip() + (" " + m.group(2).strip() if m.group(2) else "")).strip()


def _parse_employer_after_services_colon(lat):
    """``Berkeley Services: …`` — only merge a real ``U.a.e (L L C)`` tail, not random OCR after the colon."""
    if not lat:
        return ""
    m = re.search(r"(?i)\b((?:berkeley|berte?ley)\s+services)\s*:\s*", lat)
    if not m:
        return ""
    prefix = m.group(1).strip()
    frag = _trim_employer_value_fragment(lat[m.end() :])
    tail = _short_employer_company(_cleanup_mixed_employer(frag))
    uae_llc = _extract_uae_llc_suffix(tail)
    val = f"{prefix} {uae_llc}".strip() if uae_llc else prefix
    val = _short_employer_company(val)
    if _acceptable_eid_long_field(val, min_len=8, max_len=220):
        return val
    return ""


def _append_employer_uae_tail(full_lat, stub):
    """Same OCR line often has 'Services' then ':'/noise then 'U.a.e (L L C)' — rejoin from the Latin line."""
    if not stub or not full_lat:
        return stub
    if re.search(r"(?i)\bu\.\s*a\.\s*e", stub):
        return stub
    if not re.search(r"(?i)\b(?:berkeley|berte?ley)\s+services\b", stub):
        return stub
    pos = full_lat.lower().find(stub.lower())
    if pos < 0:
        return stub
    # _latin_only() collapses newlines to spaces; scan a short window after the company stub.
    span_end = min(len(full_lat), pos + len(stub) + 140)
    tail = full_lat[pos + len(stub) : span_end].strip()
    if not tail:
        return stub
    m = re.search(
        r"(?i)\b(u\.\s*a\.\s*e)\s*(\(\s*l\s+l\s+c\s*\)|\(l\.?\s*l\.?\s*c\.?\))?",
        tail[:110],
    )
    if not m:
        return stub
    extra = m.group(1).strip()
    llc = (m.group(2) or "").strip()
    out = f"{stub} {extra}"
    if llc:
        out = f"{out} {llc}"
    return out.strip()


def _parse_employer_fuzzy(text):
    """English employer line; tolerates 'Berteley' / 'U.a.e' / '(L L C)'."""
    lat = _latin_only(text)
    m = re.search(
        r"(?i)\b((?:berkeley|berte?ley)\s+services(?:\s+u\.\s*a\.\s*e)?"
        r"(?:\s*\(\s*l\s+l\s+c\s*\)|\s*\(l\.?\s*l\.?\s*c\.?\)|\s*llc)?)\b",
        lat,
    )
    if m:
        val = _short_employer_company(
            _append_employer_uae_tail(lat, _cleanup_mixed_employer(m.group(1).strip()))
        )
        if _acceptable_eid_long_field(val, min_len=10, max_len=220):
            return val
    m2 = re.search(r"(?i)(?:employer|em\s*ployer)\s*:\s*", lat)
    if m2:
        frag = _trim_employer_value_fragment(lat[m2.end() :])
        val = _short_employer_company(_cleanup_mixed_employer(frag))
        if _acceptable_eid_long_field(val, min_len=4, max_len=220):
            return val
    return ""


def _parse_issuing_place_fuzzy(text):
    """English city near garbled 'Issuing place' (e.g. 'SSSUING ace + Dubai')."""
    lat = _latin_only(text)
    m = re.search(r"(?i)issuing\s*place\s*[:\s]+\s*([A-Za-z][A-Za-z\s\-]{2,40})", lat)
    if m:
        city = m.group(1).strip().split()[0]
        if len(city) >= 3:
            return city[0].upper() + city[1:].lower()
    m2 = re.search(
        r"(?i)(?:ssu|issu)\w*\s+ace\s*\+\s*(Dubai|Abu\s*Dhabi|Sharjah|Ajman|Al\s*Ain)",
        lat,
    )
    if m2:
        return m2.group(1).strip().title().replace(" Al ", " al ")
    return ""


def _parse_occupation_eid(text):
    """Occupation is on Emirates ID back; OCR often merges lines."""
    if not text:
        return ""
    patterns = [
        r"(?:^|\n)\s*occupation\s*[:\s/]+\s*([^\n]+)",
        r"(?:^|\n)\s*profession\s*[:\s/]+\s*([^\n]+)",
        r"(?:^|\n)\s*job\s*title\s*[:\s/]+\s*([^\n]+)",
        rf"(?i)\b{_OCC_LABEL_RE}\b\s*[:\s/]+\s*([^\n]+)",
    ]
    stop = ("employer", "issuing place", "if you find")
    for pat in patterns:
        m = re.search(pat, text, re.I | re.MULTILINE)
        if not m:
            continue
        val = _trim_occupation_noise(_strip_eid_field_value(m.group(1), stop))
        if _acceptable_eid_long_field(val, min_len=3, max_len=120):
            return val
    return _parse_occupation_glue_friendly(text)


def _parse_employer_eid(text):
    if not text:
        return ""
    m = re.search(
        r"(?:^|\n)\s*employer\s*[:\s/]*\s*((?:[^\n]+\n?){1,3}?)"
        r"(?=\n\s*(?:issuing|if you|card number|please)|$)",
        text,
        re.I | re.MULTILINE,
    )
    if m:
        block = m.group(1).strip()
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        latin = [
            ln
            for ln in lines
            if sum(1 for c in ln if "A" <= c <= "Z" or "a" <= c <= "z") >= 6
        ]
        pick = latin[0] if latin else (lines[0] if lines else "")
        val = _strip_eid_field_value(
            pick,
            ("issuing place", "if you find", "please return"),
        )
        if _acceptable_eid_long_field(val, min_len=2, max_len=220):
            return val
    _emp_stop = (
        r"(?=\s*(?:\bissuing\s*place\b|SSSUING|occupation\b|if\s*you|card\s*number|"
        r"ILARE\d|please\s*return|[A-Z]{2,}<{2,})|\n|$)"
    )
    m2 = re.search(
        rf"(?is)\b(?:employer|em\s*ployer)\b\s*[:\s/]+\s*(.+?){_emp_stop}",
        text,
    )
    if m2:
        one = m2.group(1).strip()
        if "\n" not in one:
            val = _short_employer_company(_cleanup_mixed_employer(one))
            if _acceptable_eid_long_field(val, min_len=4, max_len=220):
                return val
    return _parse_employer_glue_friendly(text)


def _parse_employer_heuristic_lines(text):
    """When labels are garbled, a line with LLC/LTD often is the employer (back of card)."""
    if not text or not text.strip():
        return ""
    for ln in text.splitlines():
        s = ln.strip()
        if len(s) < 10 or len(s) > 220:
            continue
        if not re.search(r"\b(LLC|L\.L\.C\.?|L\s*L\s*C|LTD\.?|LIMITED)\b", s, re.I):
            continue
        letters = sum(1 for c in s if c.isalpha() and ord(c) < 128)
        if letters < 10:
            continue
        cleaned = _cleanup_mixed_employer(s)
        if _acceptable_eid_long_field(cleaned, min_len=6, max_len=220):
            return cleaned
    return ""


def _parse_issuing_place_city_fallback(text):
    """Last resort: UAE city name on back OCR (issuing place)."""
    if not text or len(text.strip()) < 25:
        return ""
    compact = re.sub(r"\s+", " ", text)
    if re.search(r"\bDubay\b", compact, re.I):
        return "Dubai"
    cities = (
        ("Abu Dhabi", r"Abu\s*Dhabi"),
        ("Sharjah", r"Sharjah|Al\s*Sharjah"),
        ("Ajman", r"\bAjman\b"),
        ("Al Ain", r"Al\s*Ain"),
        ("Ras Al Khaimah", r"Ras\s*Al\s*Khaimah|R\.?A\.?K\.?"),
        ("Fujairah", r"Fujairah"),
        ("Umm Al Quwain", r"Umm\s*Al\s*Quwain"),
    )
    for label, pat in cities:
        if re.search(rf"\b(?:{pat})\b", compact, re.I):
            return label
    return ""


def _parse_issuing_place_eid(text):
    if not text:
        return ""
    patterns = [
        r"(?:^|\n)\s*issuing\s*place\s*[:\s/]+\s*([^\n]+)",
        r"(?:^|\n)\s*(?:issuing|issuin)\s+\w{0,12}\s*(?:place|pace)\s*[:\s/+.\-]*\s*([A-Za-z][^\n]*)",
    ]
    stop = ("if you find", "please return", "card number")
    for pat in patterns:
        m = re.search(pat, text, re.I | re.MULTILINE)
        if not m:
            continue
        val = _strip_eid_field_value(m.group(1), stop)
        if _acceptable_eid_long_field(val, min_len=2, max_len=80):
            return val
    m = re.search(
        r"(?i)(?:issuing|issuin)[^\n]{0,55}"
        r"(Dubai|Abu\s*Dhabi|Sharjah|Ajman|Al\s*Ain|Ras\s*Al\s*Khaimah|Fujairah|Umm\s*Al\s*Quwain)",
        text,
    )
    if m:
        return m.group(1).strip()
    return ""


def _parse_mrz_dates_sex(text):
    """MRZ TD1-style recovery: glued lines, ``O``/``0`` confusion, compact blobs."""
    res = {"dob": None, "expiry": None, "sex": "", "name": "", "nationality": ""}

    def yy_mm_dd_to_date(yy, mm, dd):
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            return datetime(year, mm, dd).date()
        except ValueError:
            return None

    nat_map = {
        "IND": "India",
        "PAK": "Pakistan",
        "BGD": "Bangladesh",
        "NPL": "Nepal",
        "LKA": "Sri Lanka",
        "PHL": "Philippines",
        "EGY": "Egypt",
        "ARE": "United Arab Emirates",
        "GBR": "United Kingdom",
        "USA": "United States",
        "NGA": "Nigeria",
        "JOR": "Jordan",
        "LBN": "Lebanon",
        "SYR": "Syria",
    }

    td1_mid = re.compile(
        r"([0-9O]{2})([0-9O]{2})([0-9O]{2})([0-9O])([MF<])([0-9O]{2})([0-9O]{2})([0-9O]{2})([0-9O])([A-Z]{3})"
    )

    def apply_td1_match(m):
        try:
            y1, mo1, d1 = _mrz_digit_pair(m.group(1), m.group(2), m.group(3))
            y2, mo2, d2 = _mrz_digit_pair(m.group(6), m.group(7), m.group(8))
        except ValueError:
            return
        if not (1 <= mo1 <= 12 and 1 <= d1 <= 31 and 1 <= mo2 <= 12 and 1 <= d2 <= 31):
            return
        dob = yy_mm_dd_to_date(y1, mo1, d1)
        expiry = yy_mm_dd_to_date(y2, mo2, d2)
        if not dob or not expiry:
            return
        if dob > date.today() or expiry.year < 1990:
            return
        sex = m.group(5)
        nat = m.group(10)
        if not res["dob"]:
            res["dob"] = dob
        if not res["expiry"]:
            res["expiry"] = expiry
        if sex in ("M", "F") and not res["sex"]:
            res["sex"] = "male" if sex == "M" else "female"
        if nat.isalpha() and len(nat) == 3 and not res["nationality"]:
            res["nationality"] = nat

    blobs = []
    if text:
        blobs.append(text)
        cu = re.sub(r"\s+", "", text.upper())
        if cu:
            blobs.append(cu)

    def _apply_td1_on_blob(blob, mf_only):
        for m in td1_mid.finditer(blob):
            if mf_only and m.group(5) not in "MF":
                continue
            apply_td1_match(m)

    for blob in blobs:
        _apply_td1_on_blob(blob, mf_only=True)
    if not res["dob"]:
        for blob in blobs:
            _apply_td1_on_blob(blob, mf_only=False)

    lines = [ln.strip().upper() for ln in (text or "").splitlines() if ln.strip()]
    mrz_lines = []
    for ln in lines:
        comp = re.sub(r"\s+", "", ln)
        if "<" in comp or re.search(r"[A-Z0-9]{18,}", comp):
            mrz_lines.append(comp)

    for ln in mrz_lines:
        _apply_td1_on_blob(ln, mf_only=True)
    if not res["dob"]:
        for ln in mrz_lines:
            _apply_td1_on_blob(ln, mf_only=False)
    for ln in mrz_lines:
        m = re.search(
            r"(\d{2})(\d{2})(\d{2})\d([MF<])(\d{2})(\d{2})(\d{2})\d([A-Z]{3})",
            ln.replace("O", "0"),
        )
        if m:
            apply_td1_match(m)

    def _name_from_mrz_string(s):
        nm = re.search(r"([A-Z]{2,})<<([A-Z0-9<]{3,})", s)
        if not nm:
            return ""
        raw = nm.group(1) + "<<" + nm.group(2)
        parts = raw.split("<<", 1)
        surname = parts[0].replace("<", " ").strip()
        given = parts[1].replace("<", " ").strip()
        full = (given + " " + surname).strip()
        full = re.sub(r"\s+", " ", full)
        if len(full) >= 4 and not re.search(r"\d{3,}", full):
            return full
        return ""

    for blob in blobs:
        probe = blob.upper() if blob is text else blob
        fn = _name_from_mrz_string(probe)
        if fn:
            res["name"] = fn
            break

    if not res["name"]:
        for ln in mrz_lines:
            nm = re.search(r"([A-Z]{2,}(?:<[A-Z]{1,})+<*)", ln)
            if not nm:
                continue
            raw = nm.group(1).strip("<")
            if "<<" not in raw:
                continue
            parts = raw.split("<<", 1)
            surname = parts[0].replace("<", " ").strip()
            given = parts[1].replace("<", " ").strip()
            full = re.sub(r"\s+", " ", (given + " " + surname).strip())
            if len(full) >= 4:
                res["name"] = full
                break

    if res["nationality"] in nat_map:
        res["nationality"] = nat_map[res["nationality"]]
    return res


def _merge_mrz_parsed(primary, secondary):
    """Prefer back-only MRZ, then fill gaps from full OCR blob."""
    out = dict(primary)
    for k in ("dob", "expiry", "sex", "name", "nationality"):
        if (out.get(k) in (None, "")) and secondary.get(k) not in (None, ""):
            out[k] = secondary[k]
    return out


def extract_fields_from_ocr(front_text, back_text):
    """Merge OCR from front and back; return dict of visitor.management field values."""
    front = front_text or ""
    back = back_text or ""
    combined = f"{front}\n{back}"
    combined_u = combined.upper()

    id_number = _parse_id_number(front) or _parse_id_number(combined) or _parse_id_number(combined_u)
    dates = _parse_dates_for_eid(front, back, combined)
    gender = _parse_gender(front) or _parse_gender(combined)
    mrz_hint = _merge_mrz_parsed(_parse_mrz_dates_sex(back), _parse_mrz_dates_sex(combined))
    name = _parse_name_english(front) or _parse_name_english(combined)
    if mrz_hint.get("name"):
        name = _prefer_mrz_name(name, mrz_hint["name"])
    name = _latin_only(name) if name else ""
    nationality = (
        _parse_nationality(front)
        or _parse_nationality(back)
        or _parse_nationality(combined)
    )
    back_lat = _latin_only(back)
    lat_all = _latin_only(combined)
    occupation = (
        _parse_occupation_eid(back)
        or _parse_occupation_eid(back_lat)
        or _parse_occupation_after_colon_lat(back_lat)
        or _parse_occupation_after_colon_lat(lat_all)
        or _parse_occupation_glue_friendly(lat_all)
        or _parse_occupation_fuzzy(back)
        or _parse_occupation_fuzzy(back_lat)
        or _parse_occupation_fuzzy(lat_all)
    )
    if not occupation:
        occupation = _parse_labeled_field(lat_all, ("occupation", "profession", "job title"))
    occupation = _trim_trailing_eid_value_noise(
        _trim_occupation_noise(_latin_only(occupation))
    ) if occupation else ""
    employer_name = (
        _parse_employer_eid(back)
        or _parse_employer_eid(back_lat)
        or _parse_employer_eid(combined)
        or _parse_employer_glue_friendly(lat_all)
        or _parse_employer_after_employer_colon(lat_all)
        or _parse_employer_after_services_colon(lat_all)
    )
    if not employer_name or sum(1 for c in employer_name if "\u0600" <= c <= "\u06FF") > len(employer_name) * 0.35:
        m_en_co = re.search(
            r"(?i)\b((?:berkeley|berte?ley)\s+services(?:\s+u\.\s*a\.\s*e)?"
            r"(?:\s*\(\s*l\s+l\s+c\s*\)|\s*\(l\.?\s*l\.?\s*c\.?\)|\s*llc)?)\b",
            lat_all,
        )
        if m_en_co:
            employer_name = _cleanup_mixed_employer(m_en_co.group(1).strip())
    if employer_name:
        employer_name = _cleanup_mixed_employer(employer_name)
    if not employer_name:
        employer_name = (
            _parse_employer_fuzzy(back_lat)
            or _parse_employer_fuzzy(back)
            or _parse_employer_heuristic_lines(back_lat)
            or _parse_employer_heuristic_lines(back)
            or _parse_employer_heuristic_lines(combined)
        )
    if employer_name:
        employer_name = _short_employer_company(
            _append_employer_uae_tail(
                lat_all, _latin_only(_cleanup_mixed_employer(employer_name))
            )
        )
    issuing_place = (
        _parse_issuing_place_eid(back_lat)
        or _parse_issuing_place_eid(back)
        or _parse_issuing_place_fuzzy(back_lat)
        or _parse_issuing_place_fuzzy(back)
        or _parse_issuing_place_eid(combined)
    )
    if not issuing_place:
        compact_back = re.sub(r"\s+", " ", back or "")
        if re.search(r"(?i)issu(?:ing|in).{0,45}dubai", compact_back) or (
            re.search(r"(?i)dubai", compact_back)
            and re.search(r"(?i)issu|ssu|suing|place", compact_back)
        ):
            issuing_place = "Dubai"
        elif re.search(r"(?i)issu(?:ing|in).{0,45}abu\s*dhabi", compact_back):
            issuing_place = "Abu Dhabi"
    if not issuing_place and len(back.strip()) > 40:
        issuing_place = _parse_issuing_place_city_fallback(back)

    if employer_name:
        employer_name = _normalize_known_employer_typo(employer_name)
        employer_name = _trim_trailing_eid_value_noise(employer_name)

    dob = dates["dob"] or mrz_hint.get("dob")
    id_expiry = dates["expiry"] or mrz_hint.get("expiry")
    id_issue = dates["issue"]
    if not gender:
        gender = mrz_hint.get("sex", "") or ""
    if not nationality and mrz_hint.get("nationality"):
        nationality = mrz_hint["nationality"]

    name = _sanitize_final_name(name)
    nationality = _sanitize_final_nationality(nationality)
    occupation = _sanitize_final_occupation(occupation)
    employer_name = _sanitize_final_employer(employer_name)
    issuing_place = _sanitize_final_issuing_place(issuing_place)

    warnings = []
    if not id_number:
        warnings.append("Could not confidently read Emirates ID number; please type it.")
    if not name:
        warnings.append("Could not confidently read English name; please verify.")
    if not id_expiry:
        warnings.append("Could not confidently read expiry date; please verify.")
    if nationality and _NAT_GARBAGE_RE.search(nationality):
        warnings.append("Nationality may be incorrect; please verify.")
        nationality = ""
    if not occupation and back.strip():
        warnings.append("Could not confidently read occupation; left blank.")
    if not employer_name and back.strip():
        warnings.append("Could not confidently read employer; left blank.")

    def fmt_date(d):
        return d.isoformat() if d else ""

    return {
        "name": name,
        "name_arabic": "",
        "id_number": id_number,
        "nationality": nationality,
        "date_of_birth": fmt_date(dob) if dob else "",
        "gender": gender,
        "id_expiry_date": fmt_date(id_expiry) if id_expiry else "",
        "id_issue_date": fmt_date(id_issue) if id_issue else "",
        "occupation": occupation,
        "employer_name": employer_name,
        "issuing_place": issuing_place,
        "passport_number": "",
        "visa_number": "",
        "warnings": warnings,
        "raw_ocr_preview": (combined[:4000] + "…") if len(combined) > 4000 else combined,
    }
