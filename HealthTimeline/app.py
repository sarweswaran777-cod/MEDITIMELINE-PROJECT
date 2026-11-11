"""
MEDI TIMELINE – Personal Medical History Management & AI-Powered Summary System
A secure, private personal electronic health record application for individuals.
No Admin roles, no Hospital roles, no hospital approval workflows.
"""

import streamlit as st
import os
import html
import textwrap
import secrets
from datetime import datetime, date

# Guard html.escape against NoneType values
_builtin_html_escape = html.escape


def _safe_html_escape(s, quote=True):
    if s is None:
        return ""
    return _builtin_html_escape(str(s), quote=quote)


html.escape = _safe_html_escape

import database as db  # noqa: E402
import auth  # noqa: E402
import ai_summary  # noqa: E402
import ocr as ocr_module  # noqa: E402

# ── Page Configuration ──────────────────────────────────────────────────
st.set_page_config(
    page_title="MediTimeline — Personal Medical History",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global Healthcare UI Design System (CSS) ───────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #0f172a;
}

.stApp {
    background-color: #f8fafc;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b192c 0%, #0f2942 100%) !important;
    border-right: 1px solid #1e3a5f;
}
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #f8fafc !important;
    width: 100%;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 500;
    font-size: 0.9rem;
    margin: 3px 0;
    text-align: left;
    transition: all 0.2s ease-in-out;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(13, 148, 136, 0.4);
    border-color: #0d9488;
    color: #ffffff !important;
    transform: translateX(3px);
}

/* Metric Cards */
[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-top: 3px solid #0d9488;
    border-radius: 10px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}
[data-testid="stMetricValue"] {
    color: #0f2942 !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
}
[data-testid="stMetricLabel"] {
    color: #64748b !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Primary Buttons */
.stButton > button[kind="primary"] {
    background: #0d9488 !important;
    border-color: #0d9488 !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 8px 20px !important;
    box-shadow: 0 2px 6px rgba(13, 148, 136, 0.25) !important;
    transition: all 0.2s ease;
}
.stButton > button[kind="primary"]:hover {
    background: #0f766e !important;
    border-color: #0f766e !important;
    box-shadow: 0 4px 10px rgba(13, 148, 136, 0.35) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 2px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
    height: 44px;
    border-radius: 8px 8px 0 0;
    padding: 8px 18px;
    font-weight: 600;
    color: #64748b;
}
.stTabs [aria-selected="true"] {
    color: #0f2942 !important;
    border-bottom: 3px solid #0d9488 !important;
}

/* Headings */
h1 { color: #0f2942; font-weight: 700; font-size: 1.85rem; }
h2 { color: #0f2942; font-weight: 600; font-size: 1.4rem; }
h3 { color: #1e3a5f; font-weight: 600; font-size: 1.18rem; }
h4 { color: #1e3a5f; font-weight: 600; font-size: 0.98rem; }

/* Custom Healthcare Cards */
.med-header-card {
    background: linear-gradient(135deg, #0f2942 0%, #163e63 100%);
    color: white;
    padding: 22px 26px;
    border-radius: 12px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(15, 41, 66, 0.08);
}
.med-header-card h1, .med-header-card h2, .med-header-card h3 {
    color: #ffffff !important;
    margin: 0;
}
.med-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

/* Badges */
.badge-manual {
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    padding: 3px 10px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}
.badge-ocr {
    background: #f3e8ff;
    color: #7e22ce;
    border: 1px solid #e9d5ff;
    padding: 3px 10px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}
.badge-minor {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #fde68a;
    padding: 3px 10px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}
.badge-adult {
    background: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
    padding: 3px 10px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}

/* Timeline Record Item */
.timeline-record {
    border-left: 4px solid #0d9488;
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    border-radius: 0 10px 10px 0;
    padding: 18px 22px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    transition: all 0.2s ease;
}
.timeline-record:hover {
    border-left-color: #0284c7;
    box-shadow: 0 3px 8px rgba(15, 23, 42, 0.06);
}
.timeline-record.ocr-item {
    border-left-color: #9333ea;
}
.timeline-record.ocr-item:hover {
    border-left-color: #7e22ce;
}

/* Emergency Card Banner */
.emergency-banner {
    background: linear-gradient(135deg, #881337 0%, #b91c1c 100%);
    color: white;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 8px 20px rgba(153, 27, 27, 0.22);
    margin: 16px 0;
}
.emergency-banner h2 { color: white !important; margin-top: 0; }

/* Notice Box */
.clinical-notice {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 0.85rem;
    color: #166534;
    margin: 10px 0;
}
.warning-box {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.86rem;
    color: #92400e;
    margin: 12px 0;
}
.security-notice {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.82rem;
    color: #64748b;
    margin-top: 14px;
}
</style>
""", unsafe_allow_html=True)

# ── Database Initialization ─────────────────────────────────────────────
db.create_database()

# ── Ensure uploads storage directory exists ──────────────────────────────
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ── Session State Management ────────────────────────────────────────────
for key, default in [
    ("logged_in", False),
    ("user_id", None),
    ("username", None),
    ("full_name", None),
    ("current_page", "Dashboard"),
    ("edit_record_id", None),
    ("ocr_preview_data", None),
    ("ocr_uploaded_filename", None),
    ("ocr_temp_filepath", None),
    ("dev_otp_display", None),
    ("summary_selected_period", "All Records"),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Navigation Helper ───────────────────────────────────────────────────
def navigate_to(page_name: str):
    """Safely updates active page and triggers rerun."""
    st.session_state["current_page"] = page_name
    st.rerun()


# ════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION: LOGIN & AGE-BASED REGISTRATION INTERFACE
# ════════════════════════════════════════════════════════════════════════

def login_and_registration_page():
    col_l, col_main, col_r = st.columns([1, 2.4, 1])

    with col_main:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0 16px 0;">
            <div style="display: inline-flex; align-items: center; justify-content: center; width: 56px; height: 56px; background: #0f2942; border-radius: 14px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(15, 41, 66, 0.15);">
                <span style="font-size: 28px; color: #38bdf8;">🩺</span>
            </div>
            <h1 style="color: #0f2942; font-size: 2.2rem; margin: 0; font-weight: 800; letter-spacing: -0.5px;">MEDI TIMELINE</h1>
            <p style="color: #0d9488; font-size: 1rem; font-weight: 600; margin: 4px 0 2px 0;">Personal Medical History & AI-Powered Summary System</p>
            <p style="color: #64748b; font-size: 0.88rem; margin: 0;">Private health history, OCR report scanner, chronological timeline & date-based summaries</p>
        </div>
        """, unsafe_allow_html=True)

        # Show any session expiration notice
        if st.session_state.get("session_notice"):
            st.warning(st.session_state["session_notice"])
            st.session_state["session_notice"] = None

        tab_login, tab_register = st.tabs(["🔐 Sign In to Personal Account", "✍️ Create New Personal Account"])

        # ── 1.1 SIGN IN TAB ───────────────────────────────────────────
        with tab_login:
            st.markdown("""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #0d9488; border-radius: 10px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04); margin-bottom: 16px;">
                <h3 style="color: #0f2942; margin-top: 0; font-size: 1.1rem;">Personal Medical Account Sign In</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin-top: -4px; margin-bottom: 0;">
                    Access and manage your private medical history, uploaded reports, and clinical timeline.
                </p>
            </div>
            """, unsafe_allow_html=True)

            with st.form("personal_login_form"):
                l_username = st.text_input("Username", placeholder="e.g. rahul", key="login_username_input")
                l_password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password_input")
                l_submit = st.form_submit_button("Sign In to My Medical Timeline", type="primary", use_container_width=True)

                if l_submit:
                    if not l_username or not l_password:
                        st.error("Please enter both username and password.")
                    else:
                        user = db.authenticate_user(l_username)
                        if user and user.get("is_locked"):
                            rem_sec = user.get("lockout_remaining_seconds", 60)
                            st.error(f"Account temporarily locked due to repeated failed login attempts. Please try again in {rem_sec} seconds.")
                        elif user and auth.verify_password(l_password, user["password_hash"]):
                            if user.get("active", 1) == 0:
                                st.error("This account is currently deactivated. Please contact support.")
                            else:
                                db.record_successful_login(user["id"])
                                auth.login(user)
                                db.add_audit_log(user["id"], "User", "User logged in successfully", user.get("medical_id", ""))
                                st.success(f"Welcome back, {user.get('full_name') or user['username']}!")
                                st.rerun()
                        else:
                            # Record failed attempt and rate limit
                            db.record_failed_login(l_username)
                            # Generic error to prevent user enumeration
                            st.error("Authentication failed: Invalid username or password.")

            # Sample Credentials Helper Card
            st.markdown("""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 18px; margin-top: 20px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);">
                <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #0f2942; margin-bottom: 6px;">Evaluation Personal Accounts</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; font-size: 0.85rem; color: #334155;">
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px;">
                        <strong style="color: #0d9488;">Rahul Kumar:</strong><br>
                        <code>rahul</code> / <code>Patient@123</code>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px;">
                        <strong style="color: #0284c7;">Athmiga (Niki):</strong><br>
                        <code>Niki</code> / <code>Patient@123</code>
                    </div>
                </div>
                <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 8px; text-align: center;">
                    Strict Account Privacy: Each user can only access their own medical history.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── 1.2 REGISTER TAB (WITH AGE & GUARDIAN SECURITY) ───────────
        with tab_register:
            st.markdown("""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #0284c7; border-radius: 10px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04); margin-bottom: 16px;">
                <h3 style="color: #0f2942; margin-top: 0; font-size: 1.1rem;">Register Individual Health Account</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin-top: -4px; margin-bottom: 0;">
                    Age-verified personal account with minor guardian protection & keyed HMAC security tokens.
                </p>
            </div>
            """, unsafe_allow_html=True)

            col_dob, col_age = st.columns([2, 1])
            with col_dob:
                reg_dob = st.date_input(
                    "Date of Birth * (Age is calculated automatically)",
                    min_value=date(1900, 1, 1),
                    max_value=date.today(),
                    value=date(2000, 1, 1),
                    key="reg_dob_input"
                )
            with col_age:
                calculated_age = db.calculate_age_from_dob(reg_dob)
                is_minor = calculated_age < 18
                st.metric("Calculated Age", f"{calculated_age} yrs")

            if is_minor:
                st.markdown("""
                <div class="warning-box">
                    <strong>🛡️ Minor Account Security (Under 18):</strong><br>
                    Parent or legal guardian details and consent verification are required for minor accounts in compliance with health data privacy rules.
                </div>
                """, unsafe_allow_html=True)

            with st.form("personal_register_form"):
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    reg_name = st.text_input("Full Legal Name *", placeholder="e.g. Rahul Kumar", key="rn_name")
                    reg_contact = st.text_input("Email Address or Phone *", placeholder="e.g. rahul@example.com", key="rn_contact")
                    reg_username = st.text_input("Desired Username *", placeholder="e.g. rahul", key="rn_user")
                with col_r2:
                    reg_pass1 = st.text_input("Password * (Min 8 chars, uppercase, lowercase, number, symbol)", type="password", key="rn_p1")
                    reg_pass2 = st.text_input("Confirm Password *", type="password", key="rn_p2")
                    reg_blood = st.selectbox("Blood Group (Optional)", ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], key="rn_blood")

                guardian_name = ""
                guardian_rel = ""
                guardian_contact = ""
                if is_minor:
                    st.markdown("#### Parent / Legal Guardian Details (Required for Minors)")
                    col_g1, col_g2, col_g3 = st.columns(3)
                    with col_g1:
                        guardian_name = st.text_input("Guardian Full Name *", placeholder="e.g. S. Kumar", key="rn_gname")
                    with col_g2:
                        guardian_rel = st.selectbox("Guardian Relationship *", ["Parent (Mother/Father)", "Legal Guardian", "Authorized Caregiver"], key="rn_grel")
                    with col_g3:
                        guardian_contact = st.text_input("Guardian Phone / Email *", placeholder="e.g. +91 98765 00000", key="rn_gcontact")

                st.markdown("#### Optional Emergency Information")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    reg_allergy = st.text_input("Known Allergies (if any)", placeholder="e.g. Penicillin, Peanuts, None", key="rn_allergy")
                with col_e2:
                    reg_emg_contact = st.text_input("Emergency Contact Person & Phone", placeholder="e.g. Ananya (+91 98765 43210)", key="rn_emg")

                reg_submit = st.form_submit_button("Request Verification Code (OTP)", type="primary", use_container_width=True)

                if reg_submit:
                    errors = []
                    if not reg_name.strip():
                        errors.append("Full Name is required.")
                    if not reg_contact.strip():
                        errors.append("Contact Email or Phone is required.")
                    if not reg_username.strip():
                        errors.append("Username is required.")
                    if is_minor:
                        if not guardian_name.strip():
                            errors.append("Parent/Guardian Full Name is required for minor accounts.")
                        if not guardian_contact.strip():
                            errors.append("Parent/Guardian Contact is required for minor accounts.")

                    valid_pwd, pwd_msg = auth.validate_password_strength(reg_pass1)
                    if not valid_pwd:
                        errors.append(pwd_msg)
                    if reg_pass1 != reg_pass2:
                        errors.append("Passwords do not match.")

                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        otp_code, otp_err = db.generate_and_store_otp(reg_contact.strip(), purpose="registration")
                        if otp_err:
                            st.error(otp_err)
                        else:
                            st.session_state["pending_reg"] = {
                                "username": reg_username.strip(),
                                "password": reg_pass1,
                                "email": reg_contact.strip() if "@" in reg_contact else "",
                                "phone": reg_contact.strip() if "@" not in reg_contact else "",
                                "full_name": reg_name.strip(),
                                "dob": str(reg_dob),
                                "blood_group": reg_blood,
                                "allergies": reg_allergy.strip(),
                                "emergency_contact": reg_emg_contact.strip(),
                                "guardian_name": guardian_name.strip(),
                                "guardian_rel": guardian_rel.strip(),
                                "guardian_contact": guardian_contact.strip(),
                                "contact": reg_contact.strip()
                            }
                            smtp_configured = bool(os.getenv("SMTP_SERVER"))
                            sms_configured = bool(os.getenv("TWILIO_ACCOUNT_SID"))
                            if not smtp_configured and not sms_configured:
                                st.session_state["dev_otp_display"] = otp_code
                            else:
                                st.session_state["dev_otp_display"] = None

                            st.success("Verification code issued! Complete the verification step below.")

            # OTP Verification Form
            if "pending_reg" in st.session_state and st.session_state["pending_reg"]:
                pending = st.session_state["pending_reg"]
                st.markdown("---")
                st.markdown(f"""
                <div style="background: #ffffff; border: 1px solid #0d9488; border-radius: 10px; padding: 20px; margin-top: 10px;">
                    <h4 style="color: #0f2942; margin-top: 0;">Enter Verification Code (OTP)</h4>
                    <p style="color: #475569; font-size: 0.88rem; margin-bottom: 12px;">
                        A single-use 6-digit security token was issued for <strong>{html.escape(pending['contact'])}</strong>. Expires in 5 minutes.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                if st.session_state.get("dev_otp_display"):
                    st.info(f"⚙️ **Development Mode (No Real Email/SMS Gateway Configured):** For testing purposes, your verification code is: **`{st.session_state['dev_otp_display']}`**")

                with st.form("otp_verification_form"):
                    entered_code = st.text_input("Enter 6-digit Verification Code", max_chars=6, key="otp_code_input")
                    verify_submit = st.form_submit_button("Confirm & Complete Account Creation", type="primary", use_container_width=True)

                    if verify_submit:
                        success, vmsg = db.verify_otp_code(pending["contact"], entered_code, purpose="registration")
                        if success:
                            uid, mid = db.register_personal_user(
                                username=pending["username"],
                                password=pending["password"],
                                email=pending["email"],
                                phone=pending["phone"],
                                full_name=pending["full_name"],
                                dob_str=pending["dob"],
                                blood_group=pending["blood_group"],
                                allergies=pending["allergies"],
                                emergency_contact=pending["emergency_contact"],
                                guardian_name=pending["guardian_name"],
                                guardian_rel=pending["guardian_rel"],
                                guardian_contact=pending["guardian_contact"]
                            )
                            if uid:
                                db.add_audit_log(uid, "User", "Account registered with age verification", mid)
                                st.session_state["pending_reg"] = None
                                st.session_state["dev_otp_display"] = None
                                st.success(f"🎉 Account successfully created! Your personal Medical ID is **{mid}**. Sign in using the Sign In tab.")
                            else:
                                st.error("Registration failed: That username or contact is already registered. Please choose another username.")
                        else:
                            st.error(vmsg)


# ════════════════════════════════════════════════════════════════════════
# 2. MAIN APPLICATION (AUTHENTICATED PERSONAL USER DASHBOARD)
# ════════════════════════════════════════════════════════════════════════

def main_app():
    # ── Session Protection & Inactivity Check ───────────────────────────
    is_valid_session, session_err = auth.check_session_validity()
    if not is_valid_session:
        st.session_state["session_notice"] = session_err
        st.rerun()
        return

    user_id = st.session_state["user_id"]
    profile = db.get_user_profile(user_id)

    if not profile:
        st.error("User profile could not be loaded. Please sign in again.")
        auth.logout()
        st.rerun()
        return

    full_name = profile.get("full_name") or profile.get("username")
    medical_id = profile.get("medical_id", f"USER{user_id}")
    current_age = profile.get("current_age", profile.get("age", 0))
    is_minor = profile.get("is_minor", 0) == 1
    transition_due = profile.get("transition_due", False)

    # ── Sidebar ─────────────────────────────────────────────────────────
    st.sidebar.markdown(textwrap.dedent(f"""\
<div style="padding: 12px 4px 16px 4px; border-bottom: 1px solid rgba(255,255,255,0.12); margin-bottom: 12px;">
<div style="font-size: 0.75rem; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; font-weight: 700;">Personal Health Portal</div>
<div style="font-size: 1.15rem; font-weight: 700; color: #ffffff;">{html.escape(full_name)}</div>
<div style="font-size: 0.8rem; color: #94a3b8; font-family: monospace;">ID: {html.escape(medical_id)}</div>
<div style="margin-top: 6px;">
{'<span class="badge-minor">Minor (Guardian Protected)</span>' if is_minor else '<span class="badge-adult">Individual Account</span>'}
</div>
</div>
"""), unsafe_allow_html=True)

    nav_items = [
        ("📊 Dashboard", "Dashboard"),
        ("📝 My Medical History", "MedicalHistory"),
        ("📄 Upload Medical Report (OCR)", "UploadReport"),
        ("⏳ Medical Timeline", "Timeline"),
        ("🧠 Period-Based Summary", "PeriodSummary"),
        ("🚨 Emergency Card", "EmergencyCard"),
        ("⚙️ My Account", "MyAccount"),
    ]

    for label, page_key in nav_items:
        active = st.session_state.get("current_page") == page_key
        prefix = "● " if active else "  "
        if st.sidebar.button(f"{prefix}{label}", key=f"sb_nav_{page_key}"):
            st.session_state["current_page"] = page_key
            st.rerun()

    st.sidebar.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    if st.sidebar.button("🚪 Sign Out", key="sb_logout_btn"):
        db.add_audit_log(user_id, "User", "User logged out", medical_id)
        auth.logout()
        st.rerun()

    # Age transition prompt if user was registered as minor but has reached 18
    if transition_due:
        st.warning("""
        🎉 **Age Transition Milestone:** Our records show that you have reached 18 years of age!
        You are now eligible to transition to independent personal health record management.
        """)
        if st.button("Acknowledge & Transition to Independent Account", key="age_trans_btn", type="primary"):
            db.transition_minor_to_independent(user_id)
            db.add_audit_log(user_id, "User", "Transitioned from minor to independent adult account", medical_id)
            st.success("Account successfully upgraded to independent adult status!")
            st.rerun()

    current_page = st.session_state.get("current_page", "Dashboard")

    # ════════════════════════════════════════════════════════════════════
    # PAGE 1: PERSONAL DASHBOARD
    # ════════════════════════════════════════════════════════════════════
    if current_page == "Dashboard":
        blood_txt = html.escape(profile.get('blood_group') or 'Not Recorded')
        st.markdown(textwrap.dedent(f"""\
<div class="med-header-card">
<div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Personal Health Dashboard</div>
<h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">Welcome back, {html.escape(full_name)}</h1>
<p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
Medical ID: <code>{html.escape(medical_id)}</code> | Age: <strong>{current_age} yrs</strong> | Blood Group: <strong>{blood_txt}</strong>
</p>
</div>
"""), unsafe_allow_html=True)

        stats = db.get_user_stats(user_id)

        # Metric Cards Row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Medical Records", stats["total_records"])
        c2.metric("Uploaded Documents", stats["total_documents"])
        c3.metric("Facilities Consulted", stats["total_facilities"])
        c4.metric("Attending Doctors", stats["total_doctors"])

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Quick Action Buttons Grid
        st.subheader("⚡ Quick Actions")
        qa1, qa2, qa3, qa4 = st.columns(4)
        if qa1.button("📄 Upload Medical Report", key="qa_upload_btn", use_container_width=True, type="primary"):
            navigate_to("UploadReport")
        if qa2.button("📝 Add Medical History", key="qa_add_btn", use_container_width=True):
            navigate_to("MedicalHistory")
        if qa3.button("⏳ View Medical Timeline", key="qa_timeline_btn", use_container_width=True):
            navigate_to("Timeline")
        if qa4.button("🧠 Generate Health Summary", key="qa_summary_btn", use_container_width=True):
            navigate_to("PeriodSummary")

        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

        col_act, col_emg = st.columns([1.8, 1.2])

        with col_act:
            st.subheader("🕒 Recent Medical Activities")
            recents = stats["recent_activities"]
            if not recents:
                st.info("No medical records logged yet. Use the buttons above to record your first clinical event or upload a report.")
            else:
                for act in recents:
                    src = act.get('record_source', 'Manual Entry')
                    src_badge = ('<span class="badge-ocr">📄 Document Extracted</span>'
                                 if 'document' in str(src).lower() else
                                 '<span class="badge-manual">✍️ Manual Entry</span>')
                    edate = html.escape(str(act.get('event_date', 'N/A')))
                    diag = html.escape(str(act.get('diagnosis') or 'General Visit'))
                    hname = html.escape(str(act.get('hospital_name') or ''))
                    doc = html.escape(str(act.get('doctor_name') or ''))
                    doc_str = f" | Dr. {doc}" if doc else ""

                    st.markdown(textwrap.dedent(f"""\
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-left: 3px solid #0d9488; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
<strong style="color: #0f2942; font-size: 0.95rem;">{edate}</strong>
{src_badge}
</div>
<div style="font-size: 0.9rem; color: #1e293b; margin-top: 4px;">
Diagnosis: <strong>{diag}</strong>
</div>
<div style="font-size: 0.8rem; color: #64748b; margin-top: 2px;">
{hname}{doc_str}
</div>
</div>
"""), unsafe_allow_html=True)

                if st.button("View Full Medical Timeline →", key="dash_view_all_timeline"):
                    navigate_to("Timeline")

        with col_emg:
            st.subheader("🚨 Emergency Information Glance")
            bg_txt = html.escape(profile.get('blood_group') or 'Unknown')
            alg_txt = html.escape(profile.get('allergies') or 'None recorded')
            emg_txt = html.escape(profile.get('emergency_contact') or 'None set')
            emg_phone_txt = html.escape(profile.get('emergency_contact_phone') or '')
            phone_row = f"<span style='color: #64748b;'>Contact Phone:</span> <strong>{emg_phone_txt}</strong>" if emg_phone_txt else ""

            st.markdown(textwrap.dedent(f"""\
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-top: 3px solid #dc2626; border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(15,23,42,0.03);">
<div style="font-size: 0.78rem; text-transform: uppercase; color: #dc2626; font-weight: 700; letter-spacing: 0.5px;">First Responder Summary</div>
<div style="margin-top: 10px; font-size: 0.9rem; line-height: 1.6;">
<span style="color: #64748b;">Blood Group:</span> <strong style="font-size: 1.15rem; color: #0f2942;">{bg_txt}</strong><br>
<span style="color: #64748b;">Known Allergies:</span> <strong style="color: #b91c1c;">{alg_txt}</strong><br>
<span style="color: #64748b;">Primary Emergency Contact:</span><br>
<strong style="color: #0f2942;">{emg_txt}</strong><br>
{phone_row}
</div>
</div>
"""), unsafe_allow_html=True)
            if st.button("Open Full Emergency Card", key="dash_emg_btn", use_container_width=True):
                navigate_to("EmergencyCard")

    # ════════════════════════════════════════════════════════════════════
    # PAGE 2: PERSONAL MEDICAL HISTORY (MANUAL STORAGE & MANAGEMENT)
    # ════════════════════════════════════════════════════════════════════
    elif current_page == "MedicalHistory":
        st.markdown("""
        <div class="med-header-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Personal Records Repository</div>
            <h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">My Medical History</h1>
            <p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
                Manually record and manage your medical consultations, diagnoses, medications, surgeries, and test results.
            </p>
        </div>
        """, unsafe_allow_html=True)

        tab_add, tab_manage = st.tabs(["➕ Add New Medical Record", "📋 Manage & Edit Existing Records"])

        # ── 2.1 ADD MEDICAL RECORD ────────────────────────────────────
        with tab_add:
            st.markdown("""
            <div class="clinical-notice">
                <strong>Self-Reported Entry:</strong> Records entered here are stored as your personal health history. They are labeled as <em>Manual Entry</em> and are not designated as hospital-verified.
            </div>
            """, unsafe_allow_html=True)

            with st.form("manual_add_record_form"):
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    ev_date = st.date_input("Date of Medical Event *", value=date.today(), max_value=date.today(), key="rec_add_date")
                    ev_facility = st.text_input("Hospital / Clinic Name", placeholder="e.g. City Care Hospital", key="rec_add_hosp")
                    ev_doctor = st.text_input("Doctor's Name (if known)", placeholder="e.g. Dr. A. Sharma", key="rec_add_doc")
                    ev_type = st.selectbox("Event Category", [
                        "Consultation", "Prescription", "Lab Test", "Scan / Imaging",
                        "Surgery / Procedure", "Hospital Admission", "Follow-up", "Routine Checkup"
                    ], key="rec_add_type")
                with col_m2:
                    ev_diag = st.text_input("Diagnosis or Health Issue *", placeholder="e.g. Acute Bronchitis, Type 2 Diabetes", key="rec_add_diag")
                    ev_meds = st.text_input("Medicines Taken (with dosage if known)", placeholder="e.g. Azithromycin 500mg once daily for 3 days", key="rec_add_meds")
                    ev_tests = st.text_input("Medical Tests & Results", placeholder="e.g. Fasting Blood Sugar: 110 mg/dL, HbA1c: 6.2%", key="rec_add_tests")
                    ev_surgery = st.text_input("Surgeries or Treatments (if applicable)", placeholder="e.g. Appendectomy, None", key="rec_add_surg")

                col_n1, col_n2 = st.columns(2)
                with col_n1:
                    ev_followup = st.text_input("Follow-up Information / Next Visit", placeholder="e.g. Review after 1 week if symptoms persist", key="rec_add_fu")
                with col_n2:
                    ev_notes = st.text_area("Symptoms & Clinical Notes", placeholder="e.g. Mild chest congestion and persistent dry cough for 3 days...", key="rec_add_notes")

                save_btn = st.form_submit_button("Save Medical Record to Timeline", type="primary", use_container_width=True)

                if save_btn:
                    if not ev_diag.strip() and not ev_notes.strip():
                        st.error("Please provide at least a diagnosis/health issue or descriptive clinical notes.")
                    else:
                        rec_id = db.add_medical_record(
                            user_id=user_id,
                            event_date=ev_date,
                            hospital_name=ev_facility,
                            doctor_name=ev_doctor,
                            diagnosis=ev_diag,
                            medicine=ev_meds,
                            test_result=ev_tests,
                            surgery=ev_surgery,
                            follow_up=ev_followup,
                            notes=ev_notes,
                            event_type=ev_type,
                            record_source="Manual Entry"
                        )
                        db.add_audit_log(user_id, "User", "Added manual medical record", medical_id)
                        st.success("✅ Medical record successfully saved to your timeline!")
                        st.rerun()

        # ── 2.2 MANAGE & EDIT RECORDS ─────────────────────────────────
        with tab_manage:
            user_records = db.get_user_records(user_id)
            if user_records.empty:
                st.info("You currently have no medical records to manage. Add your first record in the tab above.")
            else:
                st.write(f"Total stored records: **{len(user_records)}**")

                active_edit_id = st.session_state.get("edit_record_id")
                if active_edit_id:
                    edit_record = db.get_user_record_by_id(user_id, active_edit_id)
                    if edit_record:
                        st.markdown(textwrap.dedent(f"""\
<div style="background: #ffffff; border: 2px solid #0d9488; border-radius: 10px; padding: 20px; margin-bottom: 20px;">
<h3 style="color: #0f2942; margin-top: 0;">✏️ Edit Medical Record #{edit_record['record_id']}</h3>
</div>
"""), unsafe_allow_html=True)

                        with st.form("edit_record_form"):
                            col_e1, col_e2 = st.columns(2)
                            with col_e1:
                                cur_dt = datetime.strptime(str(edit_record['event_date'])[:10], "%Y-%m-%d").date() if edit_record.get('event_date') else date.today()
                                ed_date = st.date_input("Event Date", value=cur_dt, key="ed_form_date")
                                ed_hosp = st.text_input("Hospital / Clinic Name", value=edit_record.get('hospital_name', ''), key="ed_form_hosp")
                                ed_doc = st.text_input("Doctor Name", value=edit_record.get('doctor_name', ''), key="ed_form_doc")
                                ed_type = st.selectbox("Event Category", [
                                    "Consultation", "Prescription", "Lab Test", "Scan / Imaging",
                                    "Surgery / Procedure", "Hospital Admission", "Follow-up", "Routine Checkup"
                                ], index=0, key="ed_form_type")
                            with col_e2:
                                ed_diag = st.text_input("Diagnosis / Condition", value=edit_record.get('diagnosis', ''), key="ed_form_diag")
                                ed_meds = st.text_input("Medicines Taken", value=edit_record.get('medicine', ''), key="ed_form_meds")
                                ed_tests = st.text_input("Tests & Results", value=edit_record.get('test_result', ''), key="ed_form_tests")
                                ed_surg = st.text_input("Surgery / Procedure", value=edit_record.get('surgery', ''), key="ed_form_surg")

                            col_en1, col_en2 = st.columns(2)
                            with col_en1:
                                ed_fu = st.text_input("Follow-up Instructions", value=edit_record.get('follow_up', ''), key="ed_form_fu")
                            with col_en2:
                                ed_notes = st.text_area("Notes", value=edit_record.get('notes', ''), key="ed_form_notes")

                            col_sub1, col_sub2 = st.columns([1, 1])
                            with col_sub1:
                                if st.form_submit_button("Update Record", type="primary", use_container_width=True):
                                    db.update_medical_record(
                                        user_id=user_id,
                                        record_id=active_edit_id,
                                        event_date=ed_date,
                                        hospital_name=ed_hosp,
                                        doctor_name=ed_doc,
                                        diagnosis=ed_diag,
                                        medicine=ed_meds,
                                        test_result=ed_tests,
                                        surgery=ed_surg,
                                        follow_up=ed_fu,
                                        notes=ed_notes,
                                        event_type=ed_type
                                    )
                                    db.add_audit_log(user_id, "User", f"Updated record #{active_edit_id}", medical_id)
                                    st.session_state["edit_record_id"] = None
                                    st.success("Record updated successfully!")
                                    st.rerun()
                            with col_sub2:
                                if st.form_submit_button("Cancel Editing", use_container_width=True):
                                    st.session_state["edit_record_id"] = None
                                    st.rerun()

                # Record cards with Edit and Delete options
                for _, rec in user_records.iterrows():
                    rec_id = rec["record_id"]
                    src = rec.get("record_source", "Manual Entry")
                    src_badge = ('<span class="badge-ocr">📄 Document Extracted</span>'
                                 if 'document' in str(src).lower() else
                                 '<span class="badge-manual">✍️ Manual Entry</span>')
                    edate = html.escape(str(rec.get('event_date', '')))
                    etype = html.escape(str(rec.get('event_type', 'Clinical Event')))
                    hname = html.escape(str(rec.get('hospital_name', '')))
                    doc = html.escape(str(rec.get('doctor_name', '')))
                    diag = html.escape(str(rec.get('diagnosis', 'N/A')))
                    med = html.escape(str(rec.get('medicine', '')))
                    test = html.escape(str(rec.get('test_result', '')))
                    surg = html.escape(str(rec.get('surgery', '')))
                    notes = html.escape(str(rec.get('notes', '')))
                    doc_meta = f" | Dr. {doc}" if doc else ""

                    with st.container():
                        col_card, col_actions = st.columns([4, 1.2])
                        with col_card:
                            st.markdown(textwrap.dedent(f"""\
<div style="background: #ffffff; border: 1px solid #e2e8f0; border-left: 3px solid #0d9488; border-radius: 8px; padding: 14px 18px; margin-bottom: 8px;">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
<div>
<strong style="color: #0f2942; font-size: 1rem;">{edate}</strong>
<span style="background: #e2e8f0; color: #334155; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin-left: 8px;">{etype}</span>
<span style="margin-left: 8px;">{src_badge}</span>
</div>
<div style="font-size: 0.85rem; color: #64748b;">
{hname}{doc_meta}
</div>
</div>
<div style="margin-top: 8px; font-size: 0.92rem; color: #0f2942;">
<strong>Diagnosis:</strong> {diag}
</div>
{f"<div style='font-size: 0.86rem; color: #0284c7; margin-top: 2px;'><strong>Medications:</strong> {med}</div>" if med else ""}
{f"<div style='font-size: 0.86rem; color: #475569; margin-top: 2px;'><strong>Findings:</strong> {test}</div>" if test else ""}
{f"<div style='font-size: 0.86rem; color: #6366f1; margin-top: 2px;'><strong>Surgery:</strong> {surg}</div>" if surg else ""}
{f"<div style='font-size: 0.84rem; color: #64748b; margin-top: 4px;'><em>Notes: {notes}</em></div>" if notes else ""}
</div>
"""), unsafe_allow_html=True)

                        with col_actions:
                            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                            if st.button("✏️ Edit", key=f"rec_edit_btn_{rec_id}", use_container_width=True):
                                st.session_state["edit_record_id"] = rec_id
                                st.rerun()

                            confirm_del = st.checkbox("Confirm Delete", key=f"chk_del_{rec_id}")
                            if confirm_del:
                                if st.button("🗑️ Delete", key=f"rec_del_btn_{rec_id}", type="primary", use_container_width=True):
                                    db.delete_medical_record(user_id, rec_id)
                                    db.add_audit_log(user_id, "User", f"Deleted medical record #{rec_id}", medical_id)
                                    st.success(f"Record #{rec_id} deleted.")
                                    st.rerun()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 3: OCR MEDICAL DOCUMENT SCANNER & REVIEW
    # ════════════════════════════════════════════════════════════════════
    elif current_page == "UploadReport":
        st.markdown("""
        <div class="med-header-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Document Intelligence</div>
            <h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">Upload Medical Document (OCR Scanner)</h1>
            <p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
                Upload prescriptions, blood test reports, lab results, scans, and discharge summaries in PDF or image format.
            </p>
        </div>
        """, unsafe_allow_html=True)

        engine_status = ocr_module.get_ocr_engine_status()
        st.info(f"ℹ️ **Engine Status:** {engine_status['engine_message']}")

        uploaded_file = st.file_uploader(
            "Choose a medical document (PDF, PNG, JPG, JPEG — max 10MB)",
            type=["pdf", "png", "jpg", "jpeg"],
            key="ocr_file_uploader"
        )

        if uploaded_file is not None:
            is_valid, val_err = ocr_module.validate_uploaded_document(uploaded_file)
            if not is_valid:
                st.error(val_err)
            else:
                with st.spinner("Extracting text from document..."):
                    extracted_text, method = ocr_module.extract_text_from_file(uploaded_file)

                st.success(f"Document processed successfully via **{method}** ({uploaded_file.name}, {len(uploaded_file.getvalue()) / 1024:.1f} KB).")

                with st.expander("🔍 View Raw Extracted Text", expanded=False):
                    st.text_area("Extracted OCR Text", value=extracted_text, height=200, disabled=True, key="raw_ocr_textarea")

                parsed = ocr_module.parse_medical_fields(extracted_text)

                st.markdown("""
                <div class="warning-box">
                    <strong>⚠️ Clinical Review Warning:</strong><br>
                    Optical character recognition (OCR) and text extraction may misread dates, medication names, dosages, and test results.
                    Please review and correct all pre-filled fields below before confirming and saving to your medical timeline.
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### 📋 Review & Correct Extracted Information")
                with st.form("ocr_review_confirm_form"):
                    col_ocr1, col_ocr2 = st.columns(2)
                    with col_ocr1:
                        dt_val = date.today()
                        if parsed.get("event_date"):
                            try:
                                dt_val = datetime.strptime(parsed["event_date"], "%Y-%m-%d").date()
                            except Exception:
                                pass
                        f_date = st.date_input("Event Date *", value=dt_val, max_value=date.today(), key="ocr_f_date")
                        f_hosp = st.text_input("Hospital / Clinic / Lab Name", value=parsed.get("hospital_name", ""), key="ocr_f_hosp")
                        f_doc = st.text_input("Doctor's Name", value=parsed.get("doctor_name", ""), key="ocr_f_doc")
                        f_type = st.selectbox("Document / Event Category", [
                            "Prescription", "Lab Report", "Scan / Imaging",
                            "Discharge Summary", "Surgery / Procedure", "Consultation"
                        ], index=0, key="ocr_f_type")
                    with col_ocr2:
                        f_diag = st.text_input("Diagnosis or Health Issue *", value=parsed.get("diagnosis", ""), key="ocr_f_diag")
                        f_meds = st.text_input("Medications Prescribed / Taken", value=parsed.get("medicine", ""), key="ocr_f_meds")
                        f_tests = st.text_input("Lab Tests & Diagnostic Results", value=parsed.get("test_result", ""), key="ocr_f_tests")
                        f_surg = st.text_input("Surgeries or Treatments", value=parsed.get("surgery", ""), key="ocr_f_surg")

                    col_ocr3, col_ocr4 = st.columns(2)
                    with col_ocr3:
                        f_fu = st.text_input("Follow-up Advice", value=parsed.get("follow_up", ""), key="ocr_f_fu")
                    with col_ocr4:
                        f_notes = st.text_area("Clinical Summary / Notes", value=parsed.get("notes", ""), key="ocr_f_notes")

                    confirm_save = st.form_submit_button("✅ Confirm & Save Verified Medical Record", type="primary", use_container_width=True)

                    if confirm_save:
                        if not f_diag.strip() and not f_notes.strip():
                            st.error("Please provide at least a diagnosis or clinical notes before saving.")
                        else:
                            # Secure private storage: isolate user files and prevent path traversal
                            user_folder = os.path.abspath(os.path.join(UPLOADS_DIR, f"user_{user_id}"))
                            os.makedirs(user_folder, exist_ok=True)

                            # Random cryptographically secure filename
                            _, orig_ext = os.path.splitext(uploaded_file.name)
                            safe_token = secrets.token_hex(16)
                            safe_name = f"doc_{safe_token}{orig_ext.lower()}"
                            save_path = os.path.abspath(os.path.join(user_folder, safe_name))

                            # Path traversal verification
                            if not save_path.startswith(user_folder):
                                st.error("Security violation: Invalid upload path.")
                            else:
                                with open(save_path, "wb") as f:
                                    f.write(uploaded_file.getvalue())

                                doc_id = db.save_user_document(
                                    user_id=user_id,
                                    doc_type=f_type,
                                    file_name=uploaded_file.name,
                                    file_path=save_path,
                                    file_size=len(uploaded_file.getvalue()),
                                    ocr_text=extracted_text
                                )

                                rec_id = db.add_medical_record(
                                    user_id=user_id,
                                    event_date=f_date,
                                    hospital_name=f_hosp,
                                    doctor_name=f_doc,
                                    diagnosis=f_diag,
                                    medicine=f_meds,
                                    test_result=f_tests,
                                    surgery=f_surg,
                                    follow_up=f_fu,
                                    notes=f_notes,
                                    event_type=f_type,
                                    record_source="Document OCR Extracted",
                                    document_id=doc_id
                                )

                                db.add_audit_log(
                                    user_id, "User",
                                    "Uploaded and verified medical document",
                                    medical_id
                                )

                                st.success(f"🎉 Verified medical record saved successfully! Archived document ID: #{doc_id}.")
                                st.balloons()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 4: MEDICAL TIMELINE
    # ════════════════════════════════════════════════════════════════════
    elif current_page == "Timeline":
        st.markdown("""
        <div class="med-header-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Longitudinal Health History</div>
            <h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">My Medical Timeline</h1>
            <p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
                Chronological record of your personal medical events, hospital consultations, prescriptions, and lab tests.
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            col_tf1, col_tf2, col_tf3, col_tf4 = st.columns([1.5, 1.2, 1.2, 1])
            with col_tf1:
                search_query = st.text_input("🔍 Search Condition, Medicine, Doctor...", placeholder="e.g. Diabetes, Metformin, Fever", key="tl_search_q")
            with col_tf2:
                time_filter = st.selectbox("Time Window", [
                    "All Records", "Last 7 Days", "Last 30 Days", "Last 2 Months",
                    "Last 3 Months", "Last 6 Months", "Last 1 Year", "Custom Date Range"
                ], key="tl_time_filter")
            with col_tf3:
                source_filter = st.selectbox("Record Source", [
                    "All Sources", "Manual Entry", "Document OCR Extracted"
                ], key="tl_source_filter")
            with col_tf4:
                sort_order = st.selectbox("Sort By", ["Newest First", "Oldest First"], key="tl_sort_order")

        start_ts = end_ts = None
        if time_filter == "Custom Date Range":
            col_cd1, col_cd2 = st.columns(2)
            with col_cd1:
                cust_start = st.date_input("Start Date", key="tl_cust_start")
            with col_cd2:
                cust_end = st.date_input("End Date", key="tl_cust_end")
            start_ts = cust_start
            end_ts = cust_end
        elif time_filter != "All Records":
            start_ts, end_ts = ai_summary.get_date_range(time_filter)

        sort_dir = "DESC" if sort_order == "Newest First" else "ASC"
        filtered_records = db.get_user_records(
            user_id=user_id,
            search_term=search_query,
            start_date=start_ts,
            end_date=end_ts,
            record_source=source_filter,
            sort_order=sort_dir
        )

        if filtered_records.empty:
            st.info("No medical records match your selected search or filter criteria. Try expanding the date range or clearing search keywords.")
        else:
            st.write(f"Displaying **{len(filtered_records)}** medical event(s):")

            for _, row in filtered_records.iterrows():
                rec_id = row.get("record_id")
                edate = html.escape(str(row.get("event_date", "N/A")))
                etype = html.escape(str(row.get("event_type", "Clinical Event")))
                hname = html.escape(str(row.get("hospital_name", "")))
                doc = html.escape(str(row.get("doctor_name", "")))
                diag = html.escape(str(row.get("diagnosis", "")))
                med = html.escape(str(row.get("medicine", "")))
                test = html.escape(str(row.get("test_result", "")))
                surg = html.escape(str(row.get("surgery", "")))
                fu = html.escape(str(row.get("follow_up", "")))
                notes = html.escape(str(row.get("notes", "")))
                src = str(row.get("record_source", "Manual Entry"))
                doc_path = str(row.get("document_file_path", "") or "")
                doc_name = html.escape(str(row.get("document_file_name", "") or "document.pdf"))

                is_ocr = 'document' in src.lower()
                card_class = "timeline-record ocr-item" if is_ocr else "timeline-record"
                src_badge = ('<span class="badge-ocr">📄 Document OCR Extracted</span>'
                             if is_ocr else '<span class="badge-manual">✍️ Manual Entry</span>')
                doc_meta = f" | Dr. {doc}" if doc else ""

                st.markdown(textwrap.dedent(f"""\
<div class="{card_class}">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
<div>
<strong style="color: #0f2942; font-size: 1.05rem;">{edate}</strong>
<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin-left: 8px;">{etype}</span>
<span style="margin-left: 8px;">{src_badge}</span>
</div>
<div style="font-size: 0.85rem; color: #475569;">
{hname}{doc_meta}
</div>
</div>
{f"<div style='margin-top: 10px; font-size: 0.95rem; color: #0f2942;'><strong>Diagnosis:</strong> <span style='font-size: 1rem; color: #0f2942;'>{diag}</span></div>" if diag else ""}
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-top: 10px; padding-top: 10px; border-top: 1px dashed #e2e8f0; font-size: 0.88rem;">
{f"<div><span style='color:#64748b;'>Medications:</span> <strong style='color:#0284c7;'>{med}</strong></div>" if med else ""}
{f"<div><span style='color:#64748b;'>Findings / Labs:</span> {test}</div>" if test else ""}
{f"<div><span style='color:#64748b;'>Procedure:</span> <strong style='color:#6366f1;'>{surg}</strong></div>" if surg else ""}
{f"<div><span style='color:#64748b;'>Follow-up:</span> <strong style='color:#d97706;'>{fu}</strong></div>" if fu else ""}
</div>
{f"<div style='margin-top: 8px; font-size: 0.84rem; color: #475569;'><em>Notes: {notes}</em></div>" if notes else ""}
</div>
"""), unsafe_allow_html=True)

                # Secure document download: verifies file exists and is strictly within user storage
                if doc_path and os.path.exists(doc_path):
                    user_folder = os.path.abspath(os.path.join(UPLOADS_DIR, f"user_{user_id}"))
                    if os.path.abspath(doc_path).startswith(user_folder):
                        with open(doc_path, "rb") as df_file:
                            file_data = df_file.read()
                            st.download_button(
                                label=f"📎 Download Attached Report ({doc_name})",
                                data=file_data,
                                file_name=doc_name,
                                key=f"dl_doc_{rec_id}",
                                help="Download your securely stored medical document"
                            )
                st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # PAGE 5: PERIOD-BASED MEDICAL HISTORY AND AI SUMMARY (FIXED HTML)
    # ════════════════════════════════════════════════════════════════════
    elif current_page == "PeriodSummary":
        st.markdown("""
        <div class="med-header-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Clinical Health Intelligence</div>
            <h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">Period-Based Medical History & AI Summary</h1>
            <p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
                Select any timeframe to analyze your personal records and generate a structured health intelligence report.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_ps1, col_ps2 = st.columns([2, 1])
        with col_ps1:
            period_choice = st.selectbox(
                "Select Time Period for Health Summary",
                [
                    "All Records", "Last 7 Days", "Last 30 Days", "Last 2 Months",
                    "Last 3 Months", "Last 6 Months", "Last 1 Year", "Custom Date Range"
                ],
                index=(
                    ["All Records", "Last 7 Days", "Last 30 Days", "Last 2 Months",
                     "Last 3 Months", "Last 6 Months", "Last 1 Year", "Custom Date Range"]
                    .index(st.session_state.get("summary_selected_period", "All Records"))
                ),
                key="summary_period_select"
            )
            st.session_state["summary_selected_period"] = period_choice

        start_date = end_date = None
        if period_choice == "Custom Date Range":
            col_cs1, col_cs2 = st.columns(2)
            with col_cs1:
                cust_s = st.date_input("Start Date", key="sum_cust_s")
            with col_cs2:
                cust_e = st.date_input("End Date", key="sum_cust_e")
            start_date = cust_s
            end_date = cust_e
        else:
            start_date, end_date = ai_summary.get_date_range(period_choice)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        st.button("Generate Medical Summary for Selected Period", type="primary", key="gen_summary_btn")

        user_history = db.get_user_records(user_id)

        # Extract structured summary data
        summary_data = ai_summary.extract_period_summary_data(
            hist_df=user_history,
            start_date=start_date,
            end_date=end_date,
            period_label=period_choice
        )

        if not summary_data["has_records"]:
            st.info(f"ℹ️ {summary_data['message']}")
        else:
            # 1. Native Streamlit Metric Cards Row
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Clinical Events", summary_data["total_records"])
            m2.metric("Diagnoses", len(summary_data["diagnoses"]))
            m3.metric("Medications", len(summary_data["medicines"]))
            m4.metric("Facilities Consulted", len(summary_data["facilities"]))

            st.caption(f"📅 **Active Timeframe:** {summary_data['period_label']} ({summary_data['date_display']})")

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

            # 2. Four Clinical Entity Overview Cards (Using Native Streamlit Columns)
            col_sc1, col_sc2 = st.columns(2)
            with col_sc1:
                with st.container():
                    st.markdown("#### 🩺 Recorded Diagnoses & Conditions")
                    if summary_data["diagnoses"]:
                        for d in summary_data["diagnoses"]:
                            st.markdown(f"- **{html.escape(d)}**")
                    else:
                        st.caption("None recorded in this period.")

                with st.container():
                    st.markdown("#### 💊 Prescribed Medications")
                    if summary_data["medicines"]:
                        for m in summary_data["medicines"]:
                            st.markdown(f"- **{html.escape(m)}**")
                    else:
                        st.caption("None recorded in this period.")

            with col_sc2:
                with st.container():
                    st.markdown("#### 🔬 Laboratory & Diagnostic Tests")
                    if summary_data["test_results"]:
                        for t in summary_data["test_results"]:
                            st.markdown(f"- {html.escape(t)}")
                    else:
                        st.caption("No diagnostic tests recorded.")

                with st.container():
                    st.markdown("#### 🏥 Surgeries & Procedures")
                    if summary_data["surgeries"]:
                        for s in summary_data["surgeries"]:
                            st.markdown(f"- **{html.escape(s)}**")
                    else:
                        st.caption("No surgical procedures recorded.")

            # 3. Follow-ups Alert Banner
            if summary_data["follow_ups"]:
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                st.warning("🔔 **Pending Follow-ups & Scheduled Reviews:**\n\n"
                           + "\n".join([f"- **{html.escape(f)}**" for f in summary_data["follow_ups"]]))

            # 4. Health Continuity & Attention Highlights
            st.markdown("#### 🛡️ Health Attention & Care Continuity Highlights")
            for item in summary_data["attention_items"]:
                with st.expander(f"• {html.escape(item['title'])}", expanded=True):
                    st.write(item["desc"])

            # 5. Chronological Event Details
            with st.expander("📈 Chronological Event Progression (Click to Expand)", expanded=True):
                for ev in summary_data["events"]:
                    edate = html.escape(ev["event_date"])
                    etype = html.escape(ev["event_type"])
                    hname = html.escape(ev["hospital_name"])
                    doc = html.escape(ev["doctor_name"])
                    diag = html.escape(ev["diagnosis"])
                    med = html.escape(ev["medicine"])
                    test = html.escape(ev["test_result"])
                    surg = html.escape(ev["surgery"])
                    fu = html.escape(ev["follow_up"])
                    notes = html.escape(ev["notes"])
                    src = ev["record_source"]

                    src_badge = ('<span class="badge-ocr">📄 Document Extracted</span>'
                                 if 'document' in src.lower() else
                                 '<span class="badge-manual">✍️ Manual Entry</span>')
                    doc_meta = f" | Dr. {doc}" if doc else ""

                    st.markdown(textwrap.dedent(f"""\
<div style="border-left: 3px solid #0d9488; padding: 12px 16px; margin-bottom: 10px; background: #ffffff; border-radius: 0 8px 8px 0; border-top: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;">
<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
<div>
<strong style="color: #0f2942; font-size: 0.95rem;">{edate}</strong>
<span style="background: #e2e8f0; color: #334155; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin-left: 8px;">{etype}</span>
<span style="margin-left: 8px;">{src_badge}</span>
</div>
<div style="font-size: 0.8rem; color: #475569;">{hname}{doc_meta}</div>
</div>
{f"<div style='margin-top: 6px; font-size: 0.9rem;'><strong>Diagnosis:</strong> <strong style='color:#0f2942;'>{diag}</strong></div>" if diag else ""}
{f"<div style='font-size: 0.86rem; color: #0284c7;'><strong>Medications:</strong> {med}</div>" if med else ""}
{f"<div style='font-size: 0.86rem;'><strong>Findings:</strong> {test}</div>" if test else ""}
{f"<div style='font-size: 0.86rem; color: #6366f1;'><strong>Procedure:</strong> {surg}</div>" if surg else ""}
{f"<div style='font-size: 0.86rem; color: #d97706;'><strong>Follow-up:</strong> {fu}</div>" if fu else ""}
{f"<div style='font-size: 0.82rem; color: #64748b; margin-top: 4px;'><em>Notes: {notes}</em></div>" if notes else ""}
</div>
"""), unsafe_allow_html=True)

            # 6. Clinical Safety Notice
            st.markdown(textwrap.dedent("""\
<div class="security-notice">
<strong>Clinical & Safety Notice:</strong> This summary is generated from your personal electronic health entries using structured clinical synthesis. It is designed for personal health reference and discussion with your doctor. It is NOT a replacement for professional clinical judgment or medical diagnosis.
</div>
"""), unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # PAGE 6: PERSONAL EMERGENCY MEDICAL CARD (FIXED HTML & PRINTABLE)
    # ════════════════════════════════════════════════════════════════════
    elif current_page == "EmergencyCard":
        st.markdown("""
        <div class="med-header-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Critical Care Alert</div>
            <h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">Personal Emergency Medical Card</h1>
            <p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
                Rapid clinical reference card for first responders, paramedics, and emergency triage.
            </p>
        </div>
        """, unsafe_allow_html=True)

        user_records = db.get_user_records(user_id)

        major_diagnoses = []
        major_surgeries = []
        current_medicines = []

        if not user_records.empty:
            for d in user_records['diagnosis'].dropna():
                d_str = str(d).strip()
                if d_str and d_str.lower() not in ['', 'none', 'n/a', 'normal', 'healthy birth, no complications', 'clear – no abnormality']:
                    if d_str not in major_diagnoses:
                        major_diagnoses.append(d_str)

            if 'surgery' in user_records.columns:
                for s in user_records['surgery'].dropna():
                    s_str = str(s).strip()
                    if s_str and s_str.lower() not in ['', 'none', 'n/a']:
                        if s_str not in major_surgeries:
                            major_surgeries.append(s_str)

            recent_recs = user_records.head(5)
            for m in recent_recs['medicine'].dropna():
                m_str = str(m).strip()
                if m_str and m_str.lower() not in ['', 'none', 'n/a']:
                    if m_str not in current_medicines:
                        current_medicines.append(m_str)

        # Accurate data mapping with "Not provided" fallbacks (never fabricated)
        p_name = profile.get('full_name') or profile.get('username') or 'Not provided'
        p_dob = profile.get('date_of_birth') or 'Not provided'
        p_age = current_age if current_age > 0 else 'Not provided'
        p_blood = profile.get('blood_group') or 'Not provided'
        p_allergies = profile.get('allergies') or 'None recorded'
        p_emg_contact = profile.get('emergency_contact') or 'Not provided'
        p_emg_phone = profile.get('emergency_contact_phone') or 'Not provided'

        # ── 1. PROPERLY FORMATTED EMERGENCY CARD (RESPONSIVE NATIVE STREAMLIT LAYOUT) ──
        # Emergency Banner Container
        with st.container():
            st.markdown(textwrap.dedent(f"""\
<div class="emergency-banner">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.25); padding-bottom: 12px; margin-bottom: 18px;">
<div>
<span style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #fecaca; font-weight: 700;">Critical Care Alert</span>
<h2 style="margin: 0; font-size: 1.6rem; color: #ffffff;">EMERGENCY MEDICAL PROFILE</h2>
</div>
<div style="background: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 8px; font-family: monospace; font-size: 1.1rem; font-weight: 700; color: #ffffff;">
{html.escape(medical_id)}
</div>
</div>
</div>
"""), unsafe_allow_html=True)

            # Responsive Info Grid
            col_ec1, col_ec2 = st.columns(2)
            with col_ec1:
                st.markdown(f"""
                <div class="med-card" style="border-left: 4px solid #b91c1c;">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: #64748b; font-weight: 600;">Patient Identity</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: #0f2942; margin-top: 4px;">{html.escape(p_name)}</div>
                    <div style="font-size: 0.9rem; color: #334155; margin-top: 4px;">
                        Age: <strong>{p_age} yrs</strong> | Date of Birth: <strong>{html.escape(str(p_dob))}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="med-card" style="border-left: 4px solid #d97706;">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: #64748b; font-weight: 600;">Known Allergies & Contraindications</div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #b91c1c; margin-top: 4px;">{html.escape(p_allergies)}</div>
                </div>
                """, unsafe_allow_html=True)

            with col_ec2:
                st.markdown(f"""
                <div class="med-card" style="border-left: 4px solid #dc2626;">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: #64748b; font-weight: 600;">Blood Group</div>
                    <div style="font-size: 1.8rem; font-weight: 800; color: #b91c1c; margin-top: 2px;">{html.escape(p_blood)}</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="med-card" style="border-left: 4px solid #0d9488;">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: #64748b; font-weight: 600;">Primary Emergency Contact</div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #0f2942; margin-top: 4px;">{html.escape(p_emg_contact)}</div>
                    <div style="font-size: 0.9rem; color: #475569; margin-top: 2px;">Phone: <strong>{html.escape(p_emg_phone)}</strong></div>
                </div>
                """, unsafe_allow_html=True)

            # Clinical Conditions & Prescriptions
            col_med1, col_med2 = st.columns(2)
            with col_med1:
                st.markdown("#### 🩺 Major Diagnosed Conditions")
                if major_diagnoses:
                    for d in major_diagnoses:
                        st.markdown(f"- **{html.escape(d)}**")
                else:
                    st.caption("None recorded in medical history.")

                st.markdown("#### 🏥 Surgical Procedures")
                if major_surgeries:
                    for s in major_surgeries:
                        st.markdown(f"- **{html.escape(s)}**")
                else:
                    st.caption("None recorded in medical history.")

            with col_med2:
                st.markdown("#### 💊 Active / Recent Prescriptions")
                if current_medicines:
                    for m in current_medicines:
                        st.markdown(f"- **{html.escape(m)}**")
                else:
                    st.caption("None recorded in medical history.")

        st.caption("🔒 **Privacy Notice:** This emergency card is private to your authenticated account and is not publicly accessible without authentication.")

        st.markdown("---")

        # ── 2. PRINT-FRIENDLY EMERGENCY CARD VIEW ─────────────────────
        with st.expander("🖨️ Print-Friendly Emergency Card Layout", expanded=False):
            print_card_html = textwrap.dedent(f"""\
<!DOCTYPE html>
<html>
<head>
<title>Emergency Medical Card - {html.escape(p_name)}</title>
<style>
@media print {{
  body {{ margin: 0; padding: 10px; font-family: sans-serif; }}
  .no-print {{ display: none; }}
}}
.print-card {{
  border: 3px solid #b91c1c;
  border-radius: 12px;
  padding: 20px;
  max-width: 600px;
  background: #ffffff;
  color: #0f172a;
  font-family: Arial, sans-serif;
}}
.header {{
  background: #b91c1c;
  color: white;
  padding: 10px 14px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.section {{ margin-top: 14px; }}
.label {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold; }}
.val {{ font-size: 15px; font-weight: bold; color: #0f2942; }}
</style>
</head>
<body>
<div class="print-card">
<div class="header">
<div><strong>EMERGENCY MEDICAL PROFILE</strong></div>
<div><code>{html.escape(medical_id)}</code></div>
</div>
<div style="display: flex; justify-content: space-between; margin-top: 14px;">
<div>
<div class="label">Patient Name</div>
<div class="val">{html.escape(p_name)}</div>
<div style="font-size: 13px; color: #334155; margin-top: 2px;">Age: {p_age} yrs | DOB: {html.escape(str(p_dob))}</div>
</div>
<div style="text-align: right;">
<div class="label">Blood Group</div>
<div style="font-size: 26px; font-weight: bold; color: #b91c1c;">{html.escape(p_blood)}</div>
</div>
</div>
<hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 12px 0;">
<div style="display: flex; justify-content: space-between;">
<div>
<div class="label">Known Allergies</div>
<div style="font-size: 14px; font-weight: bold; color: #b91c1c;">{html.escape(p_allergies)}</div>
</div>
<div>
<div class="label">Primary Emergency Contact</div>
<div style="font-size: 14px; font-weight: bold;">{html.escape(p_emg_contact)}</div>
<div style="font-size: 13px; color: #475569;">{html.escape(p_emg_phone)}</div>
</div>
</div>
<hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 12px 0;">
<div>
<div class="label">Diagnosed Conditions</div>
<div style="font-size: 13px;">{', '.join([html.escape(d) for d in major_diagnoses]) or 'None recorded'}</div>
</div>
<div style="margin-top: 8px;">
<div class="label">Active Prescriptions</div>
<div style="font-size: 13px;">{', '.join([html.escape(m) for m in current_medicines]) or 'None recorded'}</div>
</div>
</div>
</body>
</html>
""")
            st.download_button(
                label="📥 Download Printable Emergency Card (HTML)",
                data=print_card_html,
                file_name=f"Emergency_Card_{medical_id}.html",
                mime="text/html",
                key="dl_print_card_btn"
            )

        # ── 3. UPDATE EMERGENCY INFORMATION FORM ──────────────────────
        st.markdown("### ✏️ Update Emergency Contact & Critical Information")
        with st.form("update_emergency_card_form"):
            col_ue1, col_ue2 = st.columns(2)
            with col_ue1:
                cur_blood = profile.get('blood_group', '')
                blood_opts = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
                b_idx = blood_opts.index(cur_blood) if cur_blood in blood_opts else 0
                ue_blood = st.selectbox("Blood Group", blood_opts, index=b_idx, key="ue_blood_select")
                ue_allergies = st.text_input("Known Allergies & Contraindications", value=profile.get('allergies', ''), key="ue_allergies_input")
            with col_ue2:
                ue_emg_name = st.text_input("Emergency Contact Person (Name & Relation)", value=profile.get('emergency_contact', ''), key="ue_emg_name_input")
                ue_emg_phone = st.text_input("Emergency Contact Phone Number", value=profile.get('emergency_contact_phone', ''), key="ue_emg_phone_input")

            if st.form_submit_button("Update Emergency Information", type="primary"):
                db.update_user_profile(
                    user_id=user_id,
                    blood_group=ue_blood,
                    allergies=ue_allergies,
                    emergency_contact=ue_emg_name,
                    emergency_phone=ue_emg_phone
                )
                db.add_audit_log(user_id, "User", "Updated emergency medical details", medical_id)
                st.success("Emergency medical profile updated successfully!")
                st.rerun()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 7: MY ACCOUNT & AGE-BASED SECURITY SETTINGS
    # ════════════════════════════════════════════════════════════════════
    elif current_page == "MyAccount":
        st.markdown("""
        <div class="med-header-card">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; font-weight: 700;">Account Settings</div>
            <h1 style="color: white; margin: 4px 0 0 0; font-size: 1.7rem;">My Account & Security</h1>
            <p style="color: #cbd5e1; font-size: 0.9rem; margin: 6px 0 0 0;">
                Review personal demographics, age-based security verification, guardian status, and access audit log.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_acc1, col_acc2 = st.columns([1.5, 1])

        with col_acc1:
            st.subheader("👤 Personal Profile & Age Verification")
            st.markdown(textwrap.dedent(f"""\
<div class="med-card">
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; font-size: 0.9rem;">
<div><span style="color:#64748b;">Full Legal Name:</span><br><strong>{html.escape(str(profile.get('full_name') or ''))}</strong></div>
<div><span style="color:#64748b;">Username:</span><br><code>{html.escape(str(profile.get('username') or ''))}</code></div>
<div><span style="color:#64748b;">Medical ID:</span><br><strong style="color: #0d9488;">{html.escape(medical_id)}</strong></div>
<div><span style="color:#64748b;">Date of Birth:</span><br><strong>{html.escape(str(profile.get('date_of_birth') or 'N/A'))}</strong></div>
<div><span style="color:#64748b;">Calculated Age:</span><br><strong>{current_age} years</strong></div>
<div><span style="color:#64748b;">Account Status:</span><br>{'<span class="badge-minor">Minor (Guardian Supervised)</span>' if is_minor else '<span class="badge-adult">Independent Adult</span>'}</div>
<div><span style="color:#64748b;">Primary Email:</span><br><strong>{html.escape(str(profile.get('email') or 'Not set'))}</strong></div>
<div><span style="color:#64748b;">Primary Phone:</span><br><strong>{html.escape(str(profile.get('phone') or 'Not set'))}</strong></div>
</div>
</div>
"""), unsafe_allow_html=True)

            if is_minor:
                st.subheader("🛡️ Parent / Guardian Consent Details")
                g_name = html.escape(str(profile.get('guardian_name') or 'Not Recorded'))
                g_rel = html.escape(str(profile.get('guardian_relationship') or 'Parent'))
                g_con = html.escape(str(profile.get('guardian_contact') or 'N/A'))
                g_status = ('<span class="badge-approved" style="color:#065f46; background:#ecfdf5; padding:2px 8px; border-radius:4px;">Verified</span>'
                            if profile.get('guardian_verified') == 1 else
                            '<span class="badge-pending" style="color:#92400e; background:#fef3c7; padding:2px 8px; border-radius:4px;">Pending Consent</span>')

                st.markdown(textwrap.dedent(f"""\
<div class="med-card" style="border-top: 3px solid #f59e0b;">
<div style="font-size: 0.9rem; line-height: 1.6;">
<span style="color:#64748b;">Guardian Name:</span> <strong>{g_name}</strong><br>
<span style="color:#64748b;">Relationship:</span> <strong>{g_rel}</strong><br>
<span style="color:#64748b;">Guardian Contact:</span> <strong>{g_con}</strong><br>
<span style="color:#64748b;">Verification Status:</span> {g_status}
</div>
</div>
"""), unsafe_allow_html=True)

            st.subheader("✏️ Edit Profile Information")
            with st.form("edit_user_profile_form"):
                ep_name = st.text_input("Full Legal Name", value=profile.get('full_name', ''), key="ep_name_in")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    ep_email = st.text_input("Email", value=profile.get('email', ''), key="ep_email_in")
                with col_c2:
                    ep_phone = st.text_input("Phone", value=profile.get('phone', ''), key="ep_phone_in")

                if st.form_submit_button("Save Profile Changes", type="primary"):
                    db.update_user_profile(user_id=user_id, full_name=ep_name, email=ep_email, phone=ep_phone)
                    db.add_audit_log(user_id, "User", "Updated personal account details", medical_id)
                    st.success("Profile updated successfully!")
                    st.rerun()

        with col_acc2:
            st.subheader("📋 Account Security Audit Log")
            st.markdown("""
            <p style="color: #64748b; font-size: 0.84rem;">
                Every login, record creation, update, and report upload is tracked with an immutable timestamp.
            </p>
            """, unsafe_allow_html=True)

            user_logs = db.get_user_audit_logs(user_id, limit=20)
            if user_logs.empty:
                st.info("No security logs recorded yet.")
            else:
                st.dataframe(
                    user_logs,
                    column_config={
                        "timestamp": "Timestamp",
                        "action": "Activity"
                    },
                    width="stretch",
                    hide_index=True
                )


# ════════════════════════════════════════════════════════════════════════
# 3. APPLICATION ROUTER
# ════════════════════════════════════════════════════════════════════════

if not st.session_state.get("logged_in"):
    login_and_registration_page()
else:
    main_app()
