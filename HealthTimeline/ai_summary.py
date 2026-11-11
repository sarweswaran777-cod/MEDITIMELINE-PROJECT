"""
MediTimeline - Personal Health History & Period-Based Intelligence Summary Module
Provides deterministic clinical synthesis, chronological event filtering, zero-hallucination health reports,
and strict HTML sanitization against injection attacks.
"""

import pandas as pd
from datetime import datetime, timedelta, date
import html
import textwrap


def get_date_range(period: str, custom_start=None, custom_end=None):
    """
    Calculates normalized start_date and end_date timestamps based on the period string.

    Supported periods:
    - "Last 7 Days"
    - "Last 30 Days"
    - "Last 2 Months"
    - "Last 3 Months"
    - "Last 6 Months"
    - "Last 1 Year"
    - "All Records" (or "All Time")
    - "Custom Date Range"

    Returns:
        tuple: (start_date, end_date) as pd.Timestamp or (None, None)
    """
    today_end = pd.Timestamp.now().floor('s')

    if period in ("All Records", "All Time"):
        return None, None
    elif period == "Last 7 Days":
        start_date = today_end - pd.Timedelta(days=7)
        return start_date, today_end
    elif period == "Last 30 Days":
        start_date = today_end - pd.Timedelta(days=30)
        return start_date, today_end
    elif period == "Last 2 Months":
        start_date = today_end - pd.DateOffset(months=2)
        return start_date, today_end
    elif period == "Last 3 Months":
        start_date = today_end - pd.DateOffset(months=3)
        return start_date, today_end
    elif period == "Last 6 Months":
        start_date = today_end - pd.DateOffset(months=6)
        return start_date, today_end
    elif period == "Last 1 Year":
        start_date = today_end - pd.DateOffset(years=1)
        return start_date, today_end
    elif period == "Custom Date Range":
        if custom_start and custom_end:
            start_ts = pd.to_datetime(custom_start).normalize()
            end_ts = pd.to_datetime(custom_end).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            # Ensure start <= end
            if start_ts > end_ts:
                start_ts, end_ts = end_ts, start_ts
            return start_ts, end_ts
        return None, None
    else:
        start_date = today_end - pd.Timedelta(days=30)
        return start_date, today_end


def filter_records_by_period(hist_df: pd.DataFrame, start_date=None, end_date=None) -> pd.DataFrame:
    """
    Filters a medical history DataFrame strictly within [start_date, end_date].
    Handles missing or unparseable dates safely without crashing.
    """
    if hist_df is None or hist_df.empty:
        return pd.DataFrame()

    df = hist_df.copy()

    if 'event_date' not in df.columns:
        return df

    # Parse dates safely
    df['parsed_date'] = pd.to_datetime(df['event_date'], errors='coerce')

    if start_date is not None and pd.notna(start_date):
        start_ts = pd.to_datetime(start_date).normalize()
        mask_start = pd.notna(df['parsed_date']) & (df['parsed_date'] >= start_ts)
        df = df.loc[mask_start]

    if end_date is not None and pd.notna(end_date):
        end_ts = pd.to_datetime(end_date).normalize() + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        mask_end = pd.notna(df['parsed_date']) & (df['parsed_date'] <= end_ts)
        df = df.loc[mask_end]

    # Sort chronologically (oldest to newest for clinical progression analysis)
    df = df.sort_values(by='parsed_date', ascending=True)
    return df


def _extract_unique_sanitized(series) -> list[str]:
    """Extracts unique non-empty string values from a pandas series and sanitizes for display."""
    if series is None or series.empty:
        return []
    items = []
    for val in series.dropna().unique():
        cleaned = str(val).strip()
        if cleaned and cleaned.lower() not in ('none', 'nan', '', 'n/a', 'null', 'nil', 'normal'):
            if cleaned not in items:
                items.append(cleaned)
    return items


def extract_period_summary_data(hist_df: pd.DataFrame, start_date=None, end_date=None,
                                period_label: str = "Selected Period") -> dict:
    """
    Extracts structured, verified clinical entities and algorithmic insights for a given period.
    Strictly deterministic and grounded. Returns a dictionary of validated Python objects.
    """
    if hist_df is None or hist_df.empty:
        return {
            "has_records": False,
            "period_label": period_label,
            "total_records": 0,
            "message": "No medical records logged yet."
        }

    df = filter_records_by_period(hist_df, start_date, end_date)

    if df.empty:
        range_text = f" ({str(start_date)[:10]} to {str(end_date)[:10]})" if start_date and end_date else ""
        return {
            "has_records": False,
            "period_label": period_label,
            "total_records": 0,
            "message": f"No medical events recorded in {period_label}{range_text}."
        }

    diagnoses = _extract_unique_sanitized(df.get('diagnosis', pd.Series(dtype=object)))
    medicines = _extract_unique_sanitized(df.get('medicine', pd.Series(dtype=object)))
    test_results = _extract_unique_sanitized(df.get('test_result', pd.Series(dtype=object)))
    surgeries = _extract_unique_sanitized(df.get('surgery', pd.Series(dtype=object)))
    follow_ups = _extract_unique_sanitized(df.get('follow_up', pd.Series(dtype=object)))
    facilities = _extract_unique_sanitized(df.get('hospital_name', pd.Series(dtype=object)))
    doctors = _extract_unique_sanitized(df.get('doctor_name', pd.Series(dtype=object)))

    min_date = str(df['event_date'].min())[:10] if 'event_date' in df.columns else "N/A"
    max_date = str(df['event_date'].max())[:10] if 'event_date' in df.columns else "N/A"
    date_display = f"{min_date} to {max_date}" if min_date != max_date else min_date

    # Build chronological event items
    events = []
    for _, row in df.iterrows():
        events.append({
            "event_date": str(row.get('event_date', 'N/A')),
            "event_type": str(row.get('event_type', 'Consultation')),
            "hospital_name": str(row.get('hospital_name', '')),
            "doctor_name": str(row.get('doctor_name', '')),
            "diagnosis": str(row.get('diagnosis', '')),
            "medicine": str(row.get('medicine', '')),
            "test_result": str(row.get('test_result', '')),
            "surgery": str(row.get('surgery', '')),
            "follow_up": str(row.get('follow_up', '')),
            "notes": str(row.get('notes', '')),
            "record_source": str(row.get('record_source', 'Manual Entry'))
        })

    # Algorithmic health continuity insights
    attention_items = []
    lower_diagnoses = " ".join(diagnoses).lower()
    lower_meds = " ".join(medicines).lower()

    if any(k in lower_diagnoses or k in lower_meds for k in ("diabet", "metformin", "insulin", "glucose")):
        attention_items.append({
            "title": "Glycemic Control & Endocrine Surveillance",
            "desc": "Active blood sugar or diabetes management recorded. Maintain regular fasting blood glucose and HbA1c testing as advised."
        })
    if any(k in lower_diagnoses or k in lower_meds for k in ("bp", "hypertension", "amlodipine", "losartan", "telmisartan")):
        attention_items.append({
            "title": "Cardiovascular & Blood Pressure Monitoring",
            "desc": "Blood pressure management or cardiovascular therapy recorded. Keep tracking daily blood pressure readings."
        })
    if any(k in lower_diagnoses or k in lower_meds for k in ("fever", "infection", "bronchitis", "antibiotic", "azithromycin", "amoxicillin")):
        attention_items.append({
            "title": "Infection Resolution & Antimicrobial Regimen",
            "desc": "Acute febrile or infectious episode recorded. Verify complete adherence to prescribed antimicrobial regimens."
        })
    if surgeries:
        attention_items.append({
            "title": "Post-Operative Recovery Observation",
            "desc": f"Documented surgical procedure(s): {', '.join(surgeries)}. Monitor healing and schedule routine follow-up reviews."
        })
    if len(medicines) >= 3:
        attention_items.append({
            "title": "Multi-Medication Adherence Awareness",
            "desc": f"Multiple active medications ({len(medicines)} prescribed). Discuss multi-drug reviews with your doctor or pharmacist."
        })

    if not attention_items:
        attention_items.append({
            "title": "Longitudinal Health Stability",
            "desc": "No acute clinical contraindications identified in records for this period. Standard routine health checkups are advised."
        })

    return {
        "has_records": True,
        "period_label": period_label,
        "date_display": date_display,
        "total_records": len(df),
        "diagnoses": diagnoses,
        "medicines": medicines,
        "test_results": test_results,
        "surgeries": surgeries,
        "follow_ups": follow_ups,
        "facilities": facilities,
        "doctors": doctors,
        "events": events,
        "attention_items": attention_items
    }


def generate_period_summary(hist_df: pd.DataFrame, start_date=None, end_date=None,
                            period_label: str = "Selected Period") -> str:
    """
    Generates a 100% unindented, trusted HTML report.
    CRITICAL: All lines have ZERO leading spaces so Markdown never renders them as code blocks.
    All dynamic user text is escaped using html.escape() to guarantee zero HTML injection.
    """
    data = extract_period_summary_data(hist_df, start_date, end_date, period_label)

    if not data["has_records"]:
        msg = html.escape(data["message"])
        return textwrap.dedent(f"""\
<div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:12px; padding:24px; text-align:center; color:#475569;">
<div style="font-size: 2rem; margin-bottom: 8px;">📋</div>
<h4 style="color:#0f2942; margin:0 0 6px 0; font-size:1.1rem;">No Records Available</h4>
<p style="margin:0; font-size:0.9rem;">{msg}</p>
</div>
""")

    p_label = html.escape(data["period_label"])
    d_display = html.escape(data["date_display"])
    total_recs = data["total_records"]
    diag_cnt = len(data["diagnoses"])
    med_cnt = len(data["medicines"])
    fac_cnt = len(data["facilities"])

    # Header Card (ZERO INDENTATION ON ANY LINE)
    header_html = textwrap.dedent(f"""\
<div style="background: linear-gradient(135deg, #0f2942 0%, #163e63 100%); color: white; padding: 22px 26px; border-radius: 12px; margin-bottom: 22px; box-shadow: 0 4px 12px rgba(15, 41, 66, 0.1);">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
<div>
<div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Personal Health Intelligence Synthesis</div>
<h2 style="color: white; margin: 4px 0 0 0; font-size: 1.55rem; font-weight: 700;">Medical History Period Summary</h2>
</div>
<div style="background: rgba(255, 255, 255, 0.12); padding: 8px 16px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.2); text-align: right;">
<div style="font-size: 0.72rem; color: #cbd5e1; text-transform: uppercase;">Active Timeframe</div>
<div style="font-size: 0.95rem; font-weight: 600; color: #ffffff;">{p_label} ({d_display})</div>
</div>
</div>
<div style="display: flex; gap: 24px; margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(255, 255, 255, 0.15); flex-wrap: wrap;">
<div><span style="color: #94a3b8; font-size: 0.8rem;">Events in Period:</span> <strong style="color: #38bdf8; font-size: 0.95rem;">{total_recs}</strong></div>
<div><span style="color: #94a3b8; font-size: 0.8rem;">Diagnoses Logged:</span> <strong style="color: #ffffff; font-size: 0.95rem;">{diag_cnt}</strong></div>
<div><span style="color: #94a3b8; font-size: 0.8rem;">Medications:</span> <strong style="color: #ffffff; font-size: 0.95rem;">{med_cnt}</strong></div>
<div><span style="color: #94a3b8; font-size: 0.8rem;">Facilities Consulted:</span> <strong style="color: #ffffff; font-size: 0.95rem;">{fac_cnt}</strong></div>
</div>
</div>
""")

    # Grid of Entity Cards
    diag_li = "".join([f'<li style="margin-bottom: 5px;"><strong>{html.escape(d)}</strong></li>' for d in data["diagnoses"]]) or '<li style="color: #94a3b8;">None recorded in this period</li>'
    med_li = "".join([f'<li style="margin-bottom: 5px;"><strong>{html.escape(m)}</strong></li>' for m in data["medicines"]]) or '<li style="color: #94a3b8;">None recorded in this period</li>'
    test_li = "".join([f'<li style="margin-bottom: 5px;">{html.escape(t)}</li>' for t in data["test_results"]]) or '<li style="color: #94a3b8;">No diagnostic tests recorded</li>'
    surg_li = "".join([f'<li style="margin-bottom: 5px;"><strong>{html.escape(s)}</strong></li>' for s in data["surgeries"]]) or '<li style="color: #94a3b8;">No surgical procedures recorded</li>'

    grid_html = textwrap.dedent(f"""\
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 22px;">
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #0d9488; border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px;">
<span style="color: #0d9488; font-size: 1.1rem;">🩺</span>
<h4 style="color: #0f2942; margin: 0; font-size: 0.95rem; font-weight: 600;">Diagnoses & Conditions</h4>
</div>
<ul style="margin: 0; padding-left: 18px; font-size: 0.88rem; color: #1e293b;">
{diag_li}
</ul>
</div>
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #0284c7; border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px;">
<span style="color: #0284c7; font-size: 1.1rem;">💊</span>
<h4 style="color: #0f2942; margin: 0; font-size: 0.95rem; font-weight: 600;">Medications Taken</h4>
</div>
<ul style="margin: 0; padding-left: 18px; font-size: 0.88rem; color: #1e293b;">
{med_li}
</ul>
</div>
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #6366f1; border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px;">
<span style="color: #6366f1; font-size: 1.1rem;">🔬</span>
<h4 style="color: #0f2942; margin: 0; font-size: 0.95rem; font-weight: 600;">Lab Tests & Results</h4>
</div>
<ul style="margin: 0; padding-left: 18px; font-size: 0.88rem; color: #1e293b;">
{test_li}
</ul>
</div>
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #f59e0b; border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 10px;">
<span style="color: #f59e0b; font-size: 1.1rem;">🏥</span>
<h4 style="color: #0f2942; margin: 0; font-size: 0.95rem; font-weight: 600;">Surgeries & Procedures</h4>
</div>
<ul style="margin: 0; padding-left: 18px; font-size: 0.88rem; color: #1e293b;">
{surg_li}
</ul>
</div>
</div>
""")

    # Chronological Progression Log
    progression_cards = []
    for ev in data["events"]:
        edate = html.escape(ev["event_date"])
        etype = html.escape(ev["event_type"])
        hname = html.escape(ev["hospital_name"])
        doc = html.escape(ev["doctor_name"])
        diag = html.escape(ev["diagnosis"])
        med = html.escape(ev["medicine"])
        test = html.escape(ev["test_result"])
        surg = html.escape(ev["surgery"])
        fu = html.escape(ev["follow_up"])
        src = ev["record_source"]

        meta_parts = []
        if hname:
            meta_parts.append(f"Facility: <strong>{hname}</strong>")
        if doc:
            meta_parts.append(f"Doctor: <strong>Dr. {doc}</strong>")
        meta_str = " | ".join(meta_parts)

        src_badge = ('<span style="background: #f3e8ff; color: #7e22ce; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">📄 Document Extracted</span>'
                     if 'document' in src.lower() else
                     '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">✍️ Manual Entry</span>')

        details = []
        if diag:
            details.append(f"<div><span style='color:#64748b;'>Diagnosis:</span> <strong style='color:#0f2942;'>{diag}</strong></div>")
        if med:
            details.append(f"<div><span style='color:#64748b;'>Medicines:</span> <strong style='color:#0284c7;'>{med}</strong></div>")
        if test:
            details.append(f"<div><span style='color:#64748b;'>Findings:</span> {test}</div>")
        if surg:
            details.append(f"<div><span style='color:#64748b;'>Surgery:</span> <strong style='color:#6366f1;'>{surg}</strong></div>")
        if fu:
            details.append(f"<div><span style='color:#64748b;'>Follow-up:</span> <strong style='color:#d97706;'>{fu}</strong></div>")

        details_html = "".join([f"<div style='margin-top: 3px; font-size: 0.86rem;'>{d}</div>" for d in details])

        progression_cards.append(textwrap.dedent(f"""\
<div style="border-left: 3px solid #0d9488; padding: 10px 14px; margin-bottom: 12px; background: #f8fafc; border-radius: 0 8px 8px 0;">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
<div>
<strong style="color: #0f2942; font-size: 0.95rem;">{edate}</strong>
<span style="background: #e2e8f0; color: #334155; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin-left: 8px;">{etype}</span>
<span style="margin-left: 8px;">{src_badge}</span>
</div>
<div style="font-size: 0.8rem; color: #475569;">{meta_str}</div>
</div>
<div style="margin-top: 6px;">
{details_html or "<div style='color: #94a3b8; font-size: 0.85rem;'>General consultation recorded.</div>"}
</div>
</div>
"""))

    progression_html = textwrap.dedent(f"""\
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 22px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
<h4 style="color: #0f2942; margin: 0 0 14px 0; font-size: 1rem; font-weight: 600;">📈 Health Changes & Event Progression in this Period</h4>
{"".join(progression_cards)}
</div>
""")

    # Follow-ups Section
    fu_html = ""
    if data["follow_ups"]:
        fu_li = "".join([f'<li style="margin-bottom: 6px;"><strong>{html.escape(f)}</strong></li>' for f in data["follow_ups"]])
        fu_html = textwrap.dedent(f"""\
<div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 18px; margin-bottom: 22px;">
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
<span style="font-size: 1.1rem; color: #d97706;">🔔</span>
<h4 style="color: #92400e; margin: 0; font-size: 0.98rem; font-weight: 600;">Pending Follow-ups & Scheduled Reviews</h4>
</div>
<ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: #78350f;">
{fu_li}
</ul>
</div>
""")

    # Attention & Care Continuity Section
    att_cards = []
    for item in data["attention_items"]:
        t_clean = html.escape(item["title"])
        d_clean = html.escape(item["desc"])
        att_cards.append(f"""<div style="margin-bottom: 10px;"><div style="color: #15803d; font-weight: 600; font-size: 0.92rem;">• {t_clean}</div><div style="color: #1e293b; font-size: 0.86rem; margin-top: 2px; padding-left: 14px;">{d_clean}</div></div>""")

    attention_html = textwrap.dedent(f"""\
<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; padding: 18px; margin-bottom: 22px;">
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
<span style="font-size: 1.1rem; color: #166534;">🛡️</span>
<h4 style="color: #166534; margin: 0; font-size: 0.98rem; font-weight: 600;">Health Attention & Care Continuity Highlights</h4>
</div>
{"".join(att_cards)}
</div>
""")

    # Safety Notice
    safety_html = textwrap.dedent("""\
<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; font-size: 0.8rem; color: #64748b; line-height: 1.45;">
<strong>Clinical & Safety Notice:</strong> This summary is generated from your personal electronic health entries using structured clinical synthesis. It is designed for personal health reference and discussion with your doctor. It is NOT a replacement for professional clinical judgment or medical diagnosis.
</div>
""")

    return "".join([header_html, grid_html, progression_html, fu_html, attention_html, safety_html])
