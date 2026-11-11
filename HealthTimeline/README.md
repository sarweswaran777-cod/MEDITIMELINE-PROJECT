# MEDI TIMELINE – Personal Medical History System

**MEDI TIMELINE** is a secure, private personal medical history management and AI-powered clinical intelligence summary system designed for individual users.

---

## Key System Features

### 1. Single-User Personal Health Architecture
- Individual personal user registration and authentication.
- Strict data isolation: each user can only access, view, edit, and delete their own medical records.
- Completely removed obsolete Administrator and Hospital portals, workflows, and access dependencies.
- Zero mixed data between accounts.

### 2. Age-Based Security & Guardian Verification
- **Dynamic Age Calculation:** Automatically computed from Date of Birth (future dates strictly rejected).
- **Minor Accounts (Under 18):** Enforces parent/legal guardian consent details (Guardian Full Name, Relationship, Contact) and verification.
- **Adult Accounts (18 and above):** Independent access and personal health data governance.
- **Milestone Transition:** Users registered as minors who turn 18 are prompted to review and transition to independent adult accounts.
- **Cryptographic OTP Tokens:** Single-use, hashed 6-digit verification tokens with 5-minute expiry and attempt limit protection.
- **Transparent Development Mode:** Clear disclosure if external SMS/Email gateways are not configured, displaying test verification codes rather than fabricating delivery.

### 3. Personal Medical History Storage
- Add clinical encounters manually: Date, Clinic/Hospital, Doctor, Diagnosis, Medicines, Tests/Results, Surgeries, Follow-ups, and Notes.
- Editable records with safe deletion confirmation.
- Clearly marked record provenance: `Manual Entry` vs `Document OCR Extracted`.
- Never misrepresented as hospital-verified.

### 4. OCR Medical Document Scanner
- Upload prescriptions, lab reports, blood tests, scan reports, and discharge summaries in PDF, PNG, JPG, or JPEG format (up to 10MB).
- Direct digital PDF text extraction via `pypdf` and scanned image text recognition via `pytesseract` + Pillow.
- Automatic heuristic extraction of dates, physician names, facilities, diagnoses, medications, lab values, and follow-up advice.
- Interactive editable review form with prominent clinical accuracy review warnings.
- Uploaded original files archived in private user storage directories (`uploads/user_<id>/`).

### 5. Longitudinal Medical Timeline
- Chronological timeline sorted by date (newest or oldest first).
- Multi-parameter search & filtering: Keyword search, Time window, Record source.
- Direct download and inspection of attached clinical reports.

### 6. Period-Based Health Intelligence Summary
- Filter history across customizable intervals:
  - Last 7 Days
  - Last 30 Days
  - Last 2 Months
  - Last 3 Months
  - Last 6 Months
  - Last 1 Year
  - All Records
  - Custom Date Range
- Synthesizes conditions, medications, tests, surgeries, timeline progression, follow-ups, and proactive health attention points (e.g. endocrine surveillance, antibiotic stewardship, multi-drug reconciliation).
- Zero hallucination guarantee: Strictly reflects recorded data.
- Clinical safety notices and medical disclaimers.

### 7. Personal Emergency Medical Card
- Quick reference banner with blood group, allergies, primary emergency contacts, diagnosed conditions, and active prescriptions.
- Privately stored within authenticated accounts (no public links).

---

## Technology Stack
- **Framework**: Streamlit 1.28+
- **Data & Storage**: SQLite3 with parameterized queries, indexes, and schema migrations
- **Data Processing**: pandas, numpy
- **Security & Cryptography**: bcrypt, SHA-256 OTP tokens, secrets module
- **Document OCR & PDF**: pypdf, pytesseract, Pillow (PIL)

---

## Directory Structure
```
HealthTimeline/
├── app.py              # Main Streamlit personal medical history application
├── database.py         # SQLite schema, personal CRUD, safe migrations, OTP tokens
├── auth.py             # Bcrypt password hashing & session authentication
├── ai_summary.py       # Period-based clinical intelligence synthesis & filtering
├── ocr.py              # PDF extraction, OCR scanner, heuristic field parsing
├── requirements.txt    # Python dependencies
├── README.md           # System documentation
├── uploads/            # Private user document storage
├── meditimeline.db     # SQLite database
└── meditimeline.db.bak # Database backup
```

---

## Installation & Setup

1. **Verify Python Installation** (Python 3.8 to 3.12 recommended):
   ```bash
   python --version
   ```

2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Optional Image OCR Setup (Tesseract-OCR)**:
   - For extracting text from scanned images and photos (JPG/PNG), Tesseract-OCR is used.
   - On Windows, install Tesseract from: [UB-Mannheim Tesseract Releases](https://github.com/UB-Mannheim/tesseract/wiki)
   - Ensure `tesseract.exe` is added to the system PATH (or installed in `C:\Program Files\Tesseract-OCR\`).
   - Digital PDF extraction runs natively with `pypdf` without requiring any external binaries.

---

## Running the Application

Launch the Streamlit app:
```bash
streamlit run app.py
```

---

## Evaluation Test Accounts

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `rahul` | `Patient@123` | Personal User (Adult) | Contains comprehensive personal medical records & timeline |
| `Niki` | `Patient@123` | Personal User (Adult) | Independent personal account |
