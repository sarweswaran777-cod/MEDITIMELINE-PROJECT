"""
MediTimeline - Medical Document OCR Scanner & Clinical Text Extraction Module
Supports digital PDF parsing via pypdf and scanned images/documents via pytesseract + Pillow.
Provides heuristic clinical entity parsing and editable verification models.
"""

from datetime import datetime
import os
import re
import shutil
from typing import Tuple, Any

PIL_AVAILABLE = False
PYTESSERACT_AVAILABLE = False
PYPDF_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore[assignment]
    PIL_AVAILABLE = False

try:
    import pytesseract  # type: ignore[import-untyped]
    possible_tesseract_paths = [
        os.getenv("TESSERACT_CMD"),
        os.getenv("TESSERACT_PATH"),
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for p in possible_tesseract_paths:
        if p and os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            PYTESSERACT_AVAILABLE = True
            break
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    PYTESSERACT_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    pypdf = None  # type: ignore[assignment]
    PYPDF_AVAILABLE = False


# Supported file types & size constraints
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_uploaded_document(uploaded_file: Any) -> Tuple[bool, str]:
    """
    Validates uploaded file against allowed extensions and size threshold.
    Accepts Streamlit UploadedFile, file-like objects, or string file paths.
    Returns: (is_valid: bool, error_msg: str)
    """
    if uploaded_file is None:
        return False, "No file uploaded."

    file_size: int = 0
    header: bytes = b""
    ext_low: str = ""

    if isinstance(uploaded_file, str):
        filename = uploaded_file
        if not os.path.isfile(uploaded_file):
            return False, f"File does not exist: {uploaded_file}"
        file_size = int(os.path.getsize(uploaded_file))
        _, ext = os.path.splitext(filename)
        ext_low = ext.lower()
        if ext_low not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type '{ext}'. Allowed formats: PDF, PNG, JPG, JPEG."
        if file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            return False, f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed {max_mb:.0f} MB."
        try:
            with open(uploaded_file, "rb") as f:
                header = f.read(8)
        except Exception as e:
            return False, f"Unable to read file: {str(e)}"
    else:
        filename = getattr(uploaded_file, "name", "")
        if not filename:
            return False, "Invalid file: missing file name."
        _, ext = os.path.splitext(filename)
        ext_low = ext.lower()
        if ext_low not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type '{ext}'. Allowed formats: PDF, PNG, JPG, JPEG."

        raw_size = getattr(uploaded_file, "size", None)
        if raw_size is not None:
            try:
                file_size = int(raw_size)
            except Exception:
                file_size = 0
        else:
            try:
                file_size = len(uploaded_file.getvalue())
            except Exception:
                file_size = 0

        if file_size > MAX_FILE_SIZE_BYTES:
            max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
            return False, f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed {max_mb:.0f} MB."

        seek_fn = getattr(uploaded_file, "seek", None)
        read_fn = getattr(uploaded_file, "read", None)
        if callable(seek_fn) and callable(read_fn):
            try:
                seek_fn(0)
                chunk = read_fn(8)
                if isinstance(chunk, (bytes, bytearray)):
                    header = bytes(chunk)
            except Exception:
                pass
            finally:
                try:
                    seek_fn(0)
                except Exception:
                    pass

    # Verify file signature (magic bytes) to prevent file extension spoofing
    if isinstance(header, (bytes, bytearray)):
        if ext_low == ".pdf" and not header.startswith(b"%PDF-"):
            return False, "Invalid PDF file: Missing standard PDF file header signature."
        elif ext_low == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "Invalid PNG file: Missing standard PNG file header signature."
        elif ext_low in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
            return False, "Invalid JPEG file: Missing standard JPEG file header signature."

    return True, ""


def is_tesseract_installed() -> bool:
    """Returns True if the Tesseract binary engine is detected."""
    return PYTESSERACT_AVAILABLE


def is_pdf_supported() -> bool:
    """Returns True if pypdf is installed and ready."""
    return PYPDF_AVAILABLE


def get_ocr_engine_status() -> dict:
    """Returns status details regarding available extraction engines."""
    return {
        "pdf_reader": PYPDF_AVAILABLE,
        "image_ocr": PYTESSERACT_AVAILABLE,
        "engine_message": (
            "PDF text extraction: Active (pypdf). "
            + ("Image OCR: Active (Tesseract-OCR)." if PYTESSERACT_AVAILABLE
               else "Image OCR: Optional Tesseract-OCR binary not detected on PATH. Digital PDFs are fully extracted.")
        )
    }


def extract_text_from_file(uploaded_file: Any) -> Tuple[str, str]:
    """
    Extracts text from an uploaded document (PDF or image).
    Accepts Streamlit UploadedFile, file-like objects, or file paths.
    Returns: (extracted_text: str, extraction_method: str)
    """
    if uploaded_file is None:
        return "", "None"

    if isinstance(uploaded_file, str):
        filename = uploaded_file
    else:
        filename = getattr(uploaded_file, "name", "")
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    # ── 1. PDF Document Extraction ────────────────────────────────────
    if ext == ".pdf":
        if not PYPDF_AVAILABLE or pypdf is None:
            return "[Error: pypdf library is not installed]", "Error"

        try:
            if not isinstance(uploaded_file, str):
                seek_fn = getattr(uploaded_file, "seek", None)
                if callable(seek_fn):
                    seek_fn(0)
            reader = pypdf.PdfReader(uploaded_file)
            page_texts = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    page_texts.append(f"--- Page {i + 1} ---\n{text.strip()}")

            full_text = "\n\n".join(page_texts).strip()
            if full_text:
                return full_text, "Digital PDF Text Extraction"
            else:
                return (
                    "[Scanned PDF Notice: No digital text found in this PDF. "
                    "This appears to be a scanned image-based PDF. Please manually enter details or upload high-resolution image.]",
                    "Scanned PDF (No Embedded Text)"
                )
        except Exception as e:
            return f"[PDF Parsing Error: {str(e)}]", "Error"

    # ── 2. Image Document Extraction (PNG, JPG, JPEG) ─────────────────
    elif ext in {".png", ".jpg", ".jpeg"}:
        if not PIL_AVAILABLE or Image is None:
            return "[Image Error: Pillow (PIL) library is not installed]", "Error"

        if not PYTESSERACT_AVAILABLE or pytesseract is None:
            return (
                "[Image OCR Notice: Optical character recognition for image files requires Tesseract-OCR engine. "
                "Tesseract is currently not installed or not on system PATH. "
                "Please enter details in the verification form below. "
                "To enable image OCR, install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki]",
                "Image Fallback (Manual Review)"
            )

        try:
            if not isinstance(uploaded_file, str):
                seek_fn = getattr(uploaded_file, "seek", None)
                if callable(seek_fn):
                    seek_fn(0)
            image = Image.open(uploaded_file)
            assert pytesseract is not None
            text = pytesseract.image_to_string(image)
            clean_text = text.strip()
            if clean_text:
                return clean_text, "Tesseract OCR Engine"
            else:
                return "[OCR Result: No text could be recognized from this image. Please review manually.]", "Tesseract (Empty Output)"
        except Exception as e:
            return f"[OCR Error: {str(e)}]", "Error"

    return "", "Unsupported"


def parse_medical_fields(text: str) -> dict:
    """
    Applies heuristic regular expressions and clinical keyword patterns to
    extract potential medical fields from raw document text.
    Returns a dictionary of pre-filled candidate values for user review.
    """
    fields = {
        "event_date": datetime.today().strftime("%Y-%m-%d"),
        "hospital_name": "",
        "doctor_name": "",
        "diagnosis": "",
        "medicine": "",
        "test_result": "",
        "surgery": "",
        "follow_up": "",
        "notes": "",
        "event_type": "Medical Report"
    }

    if not isinstance(text, str) or not text.strip():
        return fields

    # Check for system notice/error prefix
    is_notice = text.startswith((
        "[Error", "[Scanned PDF Notice", "[Image OCR Notice",
        "[OCR Result", "[OCR Error", "[PDF Parsing Error"
    )) or (text.startswith("[") and ("Notice:" in text or "Error:" in text or "No text" in text))
    if is_notice:
        fields["notes"] = text or ""
        return fields

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # 1. Date Detection
    date_patterns = [
        r'\b((?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2})\b',            # 2026-08-10 or 2026/08/10
        r'\b(\d{1,2}[-/]\d{1,2}[-/](?:19|20)\d{2})\b',            # 10-08-2026 or 10/08/2026
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2})\b',
        r'\b(?:Date|DOA|DOS|Visit Date|Collection Date)[:\s]+([0-9A-Za-z\s,\.\-/]+)'
    ]
    found_date = None
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # If candidate contains extra characters, try to isolate date portion
            sub_m = re.search(
                r'\b(?:\d{1,2}[-/]\d{1,2}[-/](?:19|20)\d{2}|(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s+[A-Za-z]+\s+(?:19|20)\d{2})\b',
                candidate
            )
            cand_str = sub_m.group(0) if sub_m else candidate
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"):
                try:
                    parsed_dt = datetime.strptime(cand_str, fmt)
                    if parsed_dt.date() <= datetime.today().date():
                        found_date = parsed_dt.strftime("%Y-%m-%d")
                        break
                except Exception:
                    continue
        if found_date:
            break
    if found_date:
        fields["event_date"] = found_date

    # 2. Doctor Name Detection
    doc_patterns = [
        r'(?:Dr\.?|Doctor|Consultant|Physician|Attending)[:\s]+([A-Za-z\.\t ]+?)(?:[\n,\r]|MD|MBBS|MS|DNB|DM|MCh|FRCS|MRCP|$)',
        r'\b(Dr\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
    ]
    for pattern in doc_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doc_candidate = match.group(1).strip()
            # Clean leading title and qualification degrees
            doc_candidate = re.sub(r'^(?:Dr\.?|Doctor|Physician|Consultant)\s*', '', doc_candidate, flags=re.IGNORECASE).strip()
            doc_candidate = re.sub(r'[\s,]+(?:MD|MBBS|MS|DNB|DM|MCh|FRCS|MRCP).*$', '', doc_candidate, flags=re.IGNORECASE).strip()
            if 2 < len(doc_candidate) < 60:
                fields["doctor_name"] = doc_candidate
                break

    # 3. Hospital / Clinic Name Detection (line-by-line to prevent multi-line bleed)
    for line in lines:
        match = re.search(
            r'\b([A-Za-z0-9&\'\.\- ]{2,60}\s+(?:Hospital|Clinic|Health\s*Care|Medical\s*Center|Diagnostics|Laboratory|Pathology))\b',
            line, re.IGNORECASE
        )
        if match:
            hosp_candidate = match.group(1).strip()
            if 3 < len(hosp_candidate) < 70:
                fields["hospital_name"] = hosp_candidate
                break
        match_prefix = re.search(r'^(?:Facility|Hospital|Clinic|Center|Provider)[:\s]+([^\n\r]+)', line, re.IGNORECASE)
        if match_prefix:
            hosp_candidate = match_prefix.group(1).strip()
            if 3 < len(hosp_candidate) < 70:
                fields["hospital_name"] = hosp_candidate
                break

    # 4. Diagnosis / Condition Detection
    diag_patterns = [
        r'(?:Diagnosis|Provisional Diagnosis|Final Diagnosis|Impression|Condition|Assessment)[:\s]+([^\n\r]+)',
        r'(?:Diagnosed with|Suffering from)[:\s]+([^\n\r]+)'
    ]
    for pattern in diag_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            diag_cand = match.group(1).strip()
            if 2 < len(diag_cand) < 150:
                fields["diagnosis"] = diag_cand
                break

    # 5. Medications / Rx Detection
    med_lines = []
    med_capture = False
    lab_keywords = [
        "glucose", "blood sugar", "hba1c", "hemoglobin", "wbc", "platelet",
        "creatinine", "urea", "cholesterol", "urine", "tsh", "bilirubin",
        "sgot", "sgpt", "bp:", "blood pressure", "mmhg", "mg/dl"
    ]
    for line in lines:
        lower_line = line.lower()
        if re.search(r'^(?:Rx|Prescription|Medications|Medicines|Drugs|Advised Treatment)', line, re.IGNORECASE):
            med_capture = True
            continue
        if med_capture:
            if re.search(
                r'^(?:Tests?|Investigations?|Advice|Follow|Diagnosis|Notes?|Labs?|Findings?|Vitals?|Plan|Impression|Assessment)',
                line, re.IGNORECASE
            ):
                med_capture = False
            elif not any(lk in lower_line for lk in lab_keywords):
                med_lines.append(line)
        elif re.search(r'\b(?:Tab\.?|Cap\.?|Syrup|Inj\.?|Ointment)\b', line, re.IGNORECASE):
            if not any(lk in lower_line for lk in lab_keywords):
                med_lines.append(line)

    if med_lines:
        fields["medicine"] = ", ".join(med_lines[:4])

    # 6. Lab Tests & Results
    test_lines = []
    for line in lines:
        lower_line = line.lower()
        if any(lower_line.startswith(p) for p in [
            "chief complaint", "complaint:", "follow-up", "follow up",
            "diagnosis:", "notes:", "rx:", "prescription:", "tab", "cap", "inj"
        ]):
            continue
        if any(kw in lower_line for kw in lab_keywords):
            clean_test = re.sub(r'^(?:Tests?|Investigations?|Lab Results?|Findings?)[:\s]*', '', line, flags=re.IGNORECASE).strip()
            if clean_test:
                test_lines.append(clean_test)
    if test_lines:
        fields["test_result"] = "; ".join(test_lines[:4])

    # 7. Surgeries / Procedures
    surg_match = re.search(r'(?:Surgery|Procedure|Operation|Surgical Notes)[:\s]+([^\n\r]+)', text, re.IGNORECASE)
    if surg_match:
        fields["surgery"] = surg_match.group(1).split("\n")[0].strip()

    # 8. Follow-up
    fu_match = re.search(r'(?:Follow[\s-]*up|Next Visit|Review after)[:\s]+([^\n\r]+)', text, re.IGNORECASE)
    if fu_match:
        fields["follow_up"] = fu_match.group(1).split("\n")[0].strip()

    # Event Type heuristic
    lower_text = text.lower()
    if "prescription" in lower_text or "rx" in lower_text:
        fields["event_type"] = "Prescription"
    elif "blood test" in lower_text or "lab report" in lower_text or "pathology" in lower_text:
        fields["event_type"] = "Lab Report"
    elif "scan" in lower_text or "x-ray" in lower_text or "mri" in lower_text or "ultrasound" in lower_text or "ct scan" in lower_text:
        fields["event_type"] = "Scan / Imaging"
    elif "discharge" in lower_text or "summary" in lower_text:
        fields["event_type"] = "Discharge Summary"
    elif "surgery" in lower_text or "operative" in lower_text:
        fields["event_type"] = "Surgery / Procedure"

    # Default notes contains first 400 characters of raw text
    fields["notes"] = (text[:400] + ("..." if len(text) > 400 else "")).strip()

    return fields
