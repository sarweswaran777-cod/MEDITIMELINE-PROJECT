"""
MediTimeline - Personal Medical History Management Database Module
SQLite schema, migrations, personal record operations, keyed HMAC verification,
and enterprise security controls.
"""

import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import os
import hmac
import hashlib
import secrets
import time
from auth import hash_password

DB_NAME = 'meditimeline.db'
DEFAULT_HMAC_KEY = "meditimeline_default_hmac_secret_key_change_in_production"


def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_age_from_dob(dob_str):
    """Accurately calculates age from a YYYY-MM-DD date string."""
    if not dob_str:
        return 0
    try:
        if isinstance(dob_str, str):
            dob = datetime.strptime(dob_str.strip()[:10], "%Y-%m-%d").date()
        elif isinstance(dob_str, (datetime, date)):
            dob = dob_str if isinstance(dob_str, date) else dob_str.date()
        else:
            return 0
        today = date.today()
        if dob > today:
            return 0
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 0


def create_database():
    """Initializes tables and runs safe migration to ensure schema compatibility."""
    conn = get_connection()
    c = conn.cursor()

    # ── users ──────────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT DEFAULT 'User',
        email TEXT,
        phone TEXT,
        full_name TEXT,
        date_of_birth TEXT,
        age INTEGER,
        blood_group TEXT,
        allergies TEXT,
        emergency_contact TEXT,
        emergency_contact_phone TEXT,
        medical_id TEXT,
        is_minor INTEGER DEFAULT 0,
        guardian_name TEXT,
        guardian_relationship TEXT,
        guardian_contact TEXT,
        guardian_verified INTEGER DEFAULT 0,
        needs_age_transition INTEGER DEFAULT 0,
        failed_login_attempts INTEGER DEFAULT 0,
        locked_until DATETIME,
        active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── patients (legacy preservation) ──────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS patients (
        medical_id TEXT PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        date_of_birth TEXT,
        age INTEGER,
        gender TEXT,
        blood_group TEXT,
        allergies TEXT,
        emergency_contact TEXT,
        phone TEXT,
        address TEXT,
        registered_by_hospital INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # ── medical_history ────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS medical_history (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        medical_id TEXT,
        hospital_id INTEGER,
        hospital_name TEXT,
        doctor_name TEXT,
        event_date TEXT,
        event_type TEXT DEFAULT 'Consultation',
        description TEXT,
        diagnosis TEXT,
        medicine TEXT,
        test_result TEXT,
        surgery TEXT,
        follow_up TEXT,
        notes TEXT,
        record_source TEXT DEFAULT 'Manual Entry',
        document_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # ── documents ──────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
        document_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        medical_id TEXT,
        hospital_id INTEGER,
        document_type TEXT,
        file_name TEXT,
        file_path TEXT,
        file_size INTEGER DEFAULT 0,
        ocr_text TEXT,
        uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # ── otps (Security & Verification Tokens) ──────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        contact TEXT,
        otp_hash TEXT,
        purpose TEXT,
        attempts INTEGER DEFAULT 0,
        is_used INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME
    )''')

    # ── audit_logs ─────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT DEFAULT 'User',
        action TEXT,
        medical_id TEXT,
        hospital_id TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # ── legacy tables preservation (hospitals, consent_requests) ───────
    c.execute('''CREATE TABLE IF NOT EXISTS hospitals (
        hospital_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        hospital_name TEXT,
        hospital_code TEXT,
        email TEXT,
        address TEXT,
        phone TEXT,
        authorized_doctor TEXT,
        status TEXT DEFAULT 'Approved',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS consent_requests (
        consent_id INTEGER PRIMARY KEY AUTOINCREMENT,
        medical_id TEXT,
        hospital_id INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'Pending',
        requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        approved_at DATETIME,
        expiry_date DATETIME
    )''')

    conn.commit()

    # Run safe migrations & data backfilling
    _safe_migrate(conn)

    conn.close()


def _add_column_if_missing(cursor, table, column, col_type):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _safe_migrate(conn):
    """Safely upgrades database schema and backfills user associations without data loss."""
    c = conn.cursor()

    # Add missing columns to users
    _add_column_if_missing(c, 'users', 'phone', 'TEXT')
    _add_column_if_missing(c, 'users', 'full_name', 'TEXT')
    _add_column_if_missing(c, 'users', 'date_of_birth', 'TEXT')
    _add_column_if_missing(c, 'users', 'age', 'INTEGER')
    _add_column_if_missing(c, 'users', 'blood_group', 'TEXT')
    _add_column_if_missing(c, 'users', 'allergies', 'TEXT')
    _add_column_if_missing(c, 'users', 'emergency_contact', 'TEXT')
    _add_column_if_missing(c, 'users', 'emergency_contact_phone', 'TEXT')
    _add_column_if_missing(c, 'users', 'medical_id', 'TEXT')
    _add_column_if_missing(c, 'users', 'is_minor', 'INTEGER DEFAULT 0')
    _add_column_if_missing(c, 'users', 'guardian_name', 'TEXT')
    _add_column_if_missing(c, 'users', 'guardian_relationship', 'TEXT')
    _add_column_if_missing(c, 'users', 'guardian_contact', 'TEXT')
    _add_column_if_missing(c, 'users', 'guardian_verified', 'INTEGER DEFAULT 0')
    _add_column_if_missing(c, 'users', 'needs_age_transition', 'INTEGER DEFAULT 0')
    _add_column_if_missing(c, 'users', 'failed_login_attempts', 'INTEGER DEFAULT 0')
    _add_column_if_missing(c, 'users', 'locked_until', 'DATETIME')

    # Add missing columns to medical_history
    _add_column_if_missing(c, 'medical_history', 'user_id', 'INTEGER')
    _add_column_if_missing(c, 'medical_history', 'hospital_name', 'TEXT')
    _add_column_if_missing(c, 'medical_history', 'doctor_name', 'TEXT')
    _add_column_if_missing(c, 'medical_history', 'surgery', 'TEXT')
    _add_column_if_missing(c, 'medical_history', 'follow_up', 'TEXT')
    _add_column_if_missing(c, 'medical_history', 'notes', 'TEXT')
    _add_column_if_missing(c, 'medical_history', 'record_source', "TEXT DEFAULT 'Manual Entry'")
    _add_column_if_missing(c, 'medical_history', 'document_id', 'INTEGER')

    # Add missing columns to documents
    _add_column_if_missing(c, 'documents', 'user_id', 'INTEGER')
    _add_column_if_missing(c, 'documents', 'file_size', 'INTEGER DEFAULT 0')
    _add_column_if_missing(c, 'documents', 'ocr_text', 'TEXT')

    conn.commit()

    # Backfill users from patients table if users table lacks details
    c.execute("SELECT medical_id, user_id, name, date_of_birth, age, blood_group, allergies, emergency_contact, phone FROM patients")
    patients_data = c.fetchall()
    for p in patients_data:
        m_id, u_id, name, dob, p_age, blood, allergies, emg, phone = (
            p['medical_id'], p['user_id'], p['name'], p['date_of_birth'],
            p['age'], p['blood_group'], p['allergies'], p['emergency_contact'], p['phone']
        )
        if u_id:
            calc_age = calculate_age_from_dob(dob) or p_age or 0
            is_minor = 1 if calc_age < 18 else 0
            c.execute("""
                UPDATE users SET
                    full_name = COALESCE(NULLIF(full_name, ''), ?),
                    date_of_birth = COALESCE(NULLIF(date_of_birth, ''), ?),
                    age = COALESCE(NULLIF(age, 0), ?),
                    blood_group = COALESCE(NULLIF(blood_group, ''), ?),
                    allergies = COALESCE(NULLIF(allergies, ''), ?),
                    emergency_contact = COALESCE(NULLIF(emergency_contact, ''), ?),
                    phone = COALESCE(NULLIF(phone, ''), ?),
                    medical_id = COALESCE(NULLIF(medical_id, ''), ?),
                    is_minor = ?
                WHERE id = ?
            """, (name, dob, calc_age, blood, allergies, emg, phone, m_id, is_minor, u_id))

    # Backfill medical_history user_id using patients.medical_id linkage
    c.execute("""
        UPDATE medical_history
        SET user_id = (SELECT user_id FROM patients WHERE patients.medical_id = medical_history.medical_id)
        WHERE (user_id IS NULL OR user_id = 0) AND medical_id IS NOT NULL
    """)

    # Ensure record_source is filled
    c.execute("UPDATE medical_history SET record_source = 'Manual Entry' WHERE record_source IS NULL OR record_source = ''")

    # Backfill documents user_id using patients.medical_id linkage
    c.execute("""
        UPDATE documents
        SET user_id = (SELECT user_id FROM patients WHERE patients.medical_id = documents.medical_id)
        WHERE (user_id IS NULL OR user_id = 0) AND medical_id IS NOT NULL
    """)

    # Index creation for performant user-scoped queries
    c.execute("CREATE INDEX IF NOT EXISTS idx_medhist_user ON medical_history(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_medhist_date ON medical_history(event_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_docs_user ON documents(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_otps_contact ON otps(contact)")

    conn.commit()


# ════════════════════════════════════════════════════════════════════════
# PERSONAL USER & AUTHENTICATION (WITH RATE LIMITING)
# ════════════════════════════════════════════════════════════════════════

def generate_medical_id():
    """Generates a sequential Medical ID identifier (e.g. MED2026001)."""
    conn = get_connection()
    c = conn.cursor()
    year = datetime.now().year
    c.execute(
        "SELECT medical_id FROM users WHERE medical_id LIKE ? ORDER BY medical_id DESC LIMIT 1",
        (f"MED{year}%",)
    )
    row = c.fetchone()
    if not row or not row['medical_id']:
        c.execute(
            "SELECT medical_id FROM patients WHERE medical_id LIKE ? ORDER BY medical_id DESC LIMIT 1",
            (f"MED{year}%",)
        )
        row = c.fetchone()
    conn.close()
    if row and row['medical_id']:
        try:
            last_num = int(row['medical_id'][7:])
            return f"MED{year}{last_num + 1:03d}"
        except Exception:
            pass
    return f"MED{year}001"


def register_personal_user(username, password, email, phone, full_name, dob_str,
                           blood_group="", allergies="", emergency_contact="", emergency_phone="",
                           guardian_name="", guardian_rel="", guardian_contact=""):
    """
    Registers an individual personal user account with age validation and minor protection.
    """
    conn = get_connection()
    c = conn.cursor()

    age = calculate_age_from_dob(dob_str)
    is_minor = 1 if age < 18 else 0
    guardian_verified = 0 if is_minor else 1
    med_id = generate_medical_id()
    pwd_hash = hash_password(password)

    try:
        c.execute("""
            INSERT INTO users (
                username, password_hash, role, email, phone, full_name,
                date_of_birth, age, blood_group, allergies,
                emergency_contact, emergency_contact_phone, medical_id,
                is_minor, guardian_name, guardian_relationship, guardian_contact,
                guardian_verified, needs_age_transition, failed_login_attempts, active
            ) VALUES (?, ?, 'User', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
        """, (
            (username or "").strip(), pwd_hash, (email or "").strip().lower(), (phone or "").strip(), (full_name or "").strip(),
            (dob_str or "").strip(), age, (blood_group or "").strip(), (allergies or "").strip(),
            (emergency_contact or "").strip(), (emergency_phone or "").strip(), med_id,
            is_minor, (guardian_name or "").strip(), (guardian_rel or "").strip(), (guardian_contact or "").strip(),
            guardian_verified
        ))
        conn.commit()
        user_id = c.lastrowid

        # Insert into patients table for legacy reference preservation
        c.execute("""
            INSERT OR REPLACE INTO patients (
                medical_id, user_id, name, date_of_birth, age, gender,
                blood_group, allergies, emergency_contact, phone, address
            ) VALUES (?, ?, ?, ?, ?, 'Not Specified', ?, ?, ?, ?, '')
        """, (med_id, user_id, (full_name or "").strip(), (dob_str or "").strip(), age, (blood_group or "").strip(),
              (allergies or "").strip(), (emergency_contact or "").strip(), (phone or "").strip()))
        conn.commit()
        return user_id, med_id
    except sqlite3.IntegrityError:
        return None, None
    finally:
        conn.close()


def authenticate_user(username):
    """
    Retrieves user by username for authentication and session bootstrap.
    Checks account lockout status due to repeated failed login attempts.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """SELECT id, password_hash, role, active, username, full_name, email,
                  date_of_birth, age, is_minor, guardian_verified, needs_age_transition,
                  medical_id, failed_login_attempts, locked_until
           FROM users WHERE LOWER(username) = LOWER(?)""",
        ((username or "").strip(),)
    )
    user = c.fetchone()
    conn.close()

    if not user:
        return None

    user_dict = dict(user)

    # Check lockout
    locked_until_str = user_dict.get('locked_until')
    if locked_until_str:
        try:
            locked_until = datetime.strptime(locked_until_str[:19], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < locked_until:
                remaining_secs = int((locked_until - datetime.now()).total_seconds())
                user_dict['is_locked'] = True
                user_dict['lockout_remaining_seconds'] = max(remaining_secs, 1)
                return user_dict
        except Exception:
            pass

    user_dict['is_locked'] = False
    return user_dict


def record_failed_login(username, max_attempts: int = 5, lockout_minutes: int = 15):
    """Increments failed login counter and locks account if threshold exceeded."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, failed_login_attempts FROM users WHERE LOWER(username)=LOWER(?)", ((username or "").strip(),))
    row = c.fetchone()
    if row:
        u_id = row['id']
        new_attempts = (row['failed_login_attempts'] or 0) + 1
        locked_until = None
        if new_attempts >= max_attempts:
            locked_until = (datetime.now() + timedelta(minutes=lockout_minutes)).strftime("%Y-%m-%d %H:%M:%S")

        c.execute("""
            UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?
        """, (new_attempts, locked_until, u_id))
        conn.commit()
    conn.close()


def record_successful_login(user_id):
    """Resets failed login counter and clears any lockout after successful login."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?
    """, (user_id,))
    conn.commit()
    conn.close()


def get_user_profile(user_id):
    """Retrieves complete profile details for an authenticated user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        u = dict(row)
        if u.get('date_of_birth'):
            dyn_age = calculate_age_from_dob(u['date_of_birth'])
            u['current_age'] = dyn_age
            if u.get('is_minor') == 1 and dyn_age >= 18:
                u['transition_due'] = True
            else:
                u['transition_due'] = False
        return u
    return None


def update_user_profile(user_id, full_name=None, email=None, phone=None,
                        blood_group=None, allergies=None, emergency_contact=None,
                        emergency_phone=None, guardian_name=None, guardian_rel=None,
                        guardian_contact=None):
    """Updates editable user profile fields."""
    conn = get_connection()
    c = conn.cursor()
    fields = []
    params = []
    if full_name is not None:
        fields.append("full_name = ?")
        params.append((full_name or "").strip())
    if email is not None:
        fields.append("email = ?")
        params.append((email or "").strip().lower())
    if phone is not None:
        fields.append("phone = ?")
        params.append((phone or "").strip())
    if blood_group is not None:
        fields.append("blood_group = ?")
        params.append((blood_group or "").strip())
    if allergies is not None:
        fields.append("allergies = ?")
        params.append((allergies or "").strip())
    if emergency_contact is not None:
        fields.append("emergency_contact = ?")
        params.append((emergency_contact or "").strip())
    if emergency_phone is not None:
        fields.append("emergency_contact_phone = ?")
        params.append((emergency_phone or "").strip())
    if guardian_name is not None:
        fields.append("guardian_name = ?")
        params.append((guardian_name or "").strip())
    if guardian_rel is not None:
        fields.append("guardian_relationship = ?")
        params.append((guardian_rel or "").strip())
    if guardian_contact is not None:
        fields.append("guardian_contact = ?")
        params.append((guardian_contact or "").strip())

    if fields:
        params.append(user_id)
        sql = f"UPDATE users SET {', '.join(fields)} WHERE id = ?"
        c.execute(sql, tuple(params))
        conn.commit()

    conn.close()


def transition_minor_to_independent(user_id):
    """Transitions a user who has turned 18 to independent personal account management."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE users SET
            is_minor = 0,
            guardian_verified = 1,
            needs_age_transition = 0
        WHERE id = ?
    """, (user_id,))
    conn.commit()
    conn.close()


def verify_guardian_consent(user_id):
    """Marks guardian consent as verified for a minor account."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET guardian_verified = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════════════════
# KEYED HMAC OTP & RATE-LIMITED VERIFICATION TOKENS
# ════════════════════════════════════════════════════════════════════════

def _get_hmac_secret() -> bytes:
    """Retrieves HMAC secret key from environment or fallback."""
    secret = os.getenv("OTP_SECRET_KEY", DEFAULT_HMAC_KEY)
    return secret.encode('utf-8')


def _hash_otp(code: str, contact: str, purpose: str) -> str:
    """Hashes an OTP code using Keyed HMAC-SHA256 bound to contact and purpose."""
    key = _get_hmac_secret()
    payload = f"{contact.strip().lower()}:{purpose}:{code.strip()}".encode('utf-8')
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def generate_and_store_otp(contact: str, purpose: str = "registration", user_id=None,
                           expiry_minutes: int = 5, cooldown_seconds: int = 60):
    """
    Generates a secure 6-digit OTP, computes its keyed HMAC-SHA256, and stores it.
    Enforces cooldown to prevent OTP spamming.
    Returns: (otp_code: str or None, error_message: str or None)
    """
    clean_contact = (contact or "").strip().lower()
    conn = get_connection()
    c = conn.cursor()

    # Check cooldown: has an OTP been issued for this contact in the last cooldown_seconds?
    c.execute("""
        SELECT created_at FROM otps
        WHERE contact = ? AND purpose = ?
        ORDER BY created_at DESC LIMIT 1
    """, (clean_contact, purpose))
    recent = c.fetchone()
    if recent and recent['created_at']:
        try:
            # Use UTC for comparison since SQLite CURRENT_TIMESTAMP stores UTC
            last_created = datetime.strptime(recent['created_at'][:19], "%Y-%m-%d %H:%M:%S")
            diff_secs = (datetime.utcnow() - last_created).total_seconds()
            if diff_secs < cooldown_seconds:
                wait_sec = int(cooldown_seconds - diff_secs)
                conn.close()
                return None, f"Please wait {wait_sec} seconds before requesting a new verification code."
        except Exception:
            pass

    # Invalidate previous unused OTPs for this contact and purpose
    c.execute(
        "UPDATE otps SET is_used = 1 WHERE contact = ? AND purpose = ? AND is_used = 0",
        (clean_contact, purpose)
    )

    # 6-digit cryptographically secure random code
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    otp_hash = _hash_otp(otp_code, clean_contact, purpose)
    # Use UTC for expires_at to stay consistent with SQLite CURRENT_TIMESTAMP
    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)

    c.execute("""
        INSERT INTO otps (user_id, contact, otp_hash, purpose, attempts, is_used, expires_at)
        VALUES (?, ?, ?, ?, 0, 0, ?)
    """, (user_id, clean_contact, otp_hash, purpose, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return otp_code, None


def verify_otp_code(contact: str, code_entered: str, purpose: str = "registration", max_attempts: int = 3):
    """
    Verifies an entered OTP code using keyed HMAC comparison.
    Enforces expiry, max attempt limiting, and single-use invalidation.
    Returns: (success: bool, message: str)
    """
    clean_contact = (contact or "").strip().lower()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, otp_hash, attempts, is_used, expires_at
        FROM otps
        WHERE contact = ? AND purpose = ? AND is_used = 0
        ORDER BY created_at DESC LIMIT 1
    """, (clean_contact, purpose))
    row = c.fetchone()

    if not row:
        conn.close()
        return False, "No active verification code found for this contact. Please request a new code."

    otp_id = row['id']
    stored_hash = row['otp_hash']
    attempts = row['attempts']
    expires_at_str = row['expires_at']

    # Check expiration — compare in UTC (consistent with CURRENT_TIMESTAMP storage)
    expires_at = datetime.strptime(expires_at_str[:19], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires_at:
        c.execute("UPDATE otps SET is_used = 1 WHERE id = ?", (otp_id,))
        conn.commit()
        conn.close()
        return False, "Verification code has expired. Please request a new code."

    # Check attempt limit
    if attempts >= max_attempts:
        c.execute("UPDATE otps SET is_used = 1 WHERE id = ?", (otp_id,))
        conn.commit()
        conn.close()
        return False, f"Maximum verification attempts ({max_attempts}) exceeded. Code is invalidated."

    # Verify keyed HMAC hash in constant time
    entered_hash = _hash_otp(code_entered.strip(), clean_contact, purpose)
    if hmac.compare_digest(entered_hash, stored_hash):
        # Invalidate OTP on successful use
        c.execute("UPDATE otps SET is_used = 1 WHERE id = ?", (otp_id,))
        conn.commit()
        conn.close()
        return True, "Verification successful."
    else:
        # Increment attempt counter
        new_attempts = attempts + 1
        c.execute("UPDATE otps SET attempts = ? WHERE id = ?", (new_attempts, otp_id))
        conn.commit()
        conn.close()
        remaining = max_attempts - new_attempts
        return False, f"Incorrect verification code. {remaining} attempt(s) remaining."


# ════════════════════════════════════════════════════════════════════════
# PERSONAL MEDICAL HISTORY (STRICT USER OWNERSHIP ENFORCED)
# ════════════════════════════════════════════════════════════════════════

def add_medical_record(user_id, event_date, hospital_name, doctor_name, diagnosis,
                       medicine="", test_result="", surgery="", follow_up="", notes="",
                       event_type="Consultation", record_source="Manual Entry", document_id=None):
    """
    Inserts a personal medical history record strictly associated with user_id.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT medical_id FROM users WHERE id=?", (user_id,))
    urow = c.fetchone()
    med_id = urow['medical_id'] if urow and urow['medical_id'] else f"USER{user_id}"

    h_name = (hospital_name or "").strip()
    d_name = (doctor_name or "").strip()
    e_date = str(event_date or "").strip()
    e_type = (event_type or "Consultation").strip()
    c_diag = (diagnosis or "").strip()
    c_meds = (medicine or "").strip()
    c_test = (test_result or "").strip()
    c_surg = (surgery or "").strip()
    c_fu = (follow_up or "").strip()
    c_notes = (notes or "").strip()

    c.execute("""
        INSERT INTO medical_history (
            user_id, medical_id, hospital_name, doctor_name, event_date,
            event_type, description, diagnosis, medicine, test_result,
            surgery, follow_up, notes, record_source, document_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, med_id, h_name, d_name, e_date,
        e_type, c_notes, c_diag, c_meds, c_test,
        c_surg, c_fu, c_notes, record_source, document_id
    ))
    conn.commit()
    record_id = c.lastrowid
    conn.close()
    return record_id


def update_medical_record(user_id, record_id, event_date, hospital_name, doctor_name,
                          diagnosis, medicine="", test_result="", surgery="",
                          follow_up="", notes="", event_type="Consultation"):
    """
    Updates an existing medical history record.
    Enforces user ownership check: record must belong to user_id.
    """
    conn = get_connection()
    c = conn.cursor()
    h_name = (hospital_name or "").strip()
    d_name = (doctor_name or "").strip()
    e_date = str(event_date or "").strip()
    e_type = (event_type or "Consultation").strip()
    c_diag = (diagnosis or "").strip()
    c_meds = (medicine or "").strip()
    c_test = (test_result or "").strip()
    c_surg = (surgery or "").strip()
    c_fu = (follow_up or "").strip()
    c_notes = (notes or "").strip()

    c.execute("""
        UPDATE medical_history SET
            event_date = ?,
            hospital_name = ?,
            doctor_name = ?,
            diagnosis = ?,
            medicine = ?,
            test_result = ?,
            surgery = ?,
            follow_up = ?,
            notes = ?,
            event_type = ?
        WHERE record_id = ? AND user_id = ?
    """, (
        e_date, h_name, d_name,
        c_diag, c_meds, c_test,
        c_surg, c_fu, c_notes, e_type,
        record_id, user_id
    ))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def delete_medical_record(user_id, record_id):
    """
    Deletes a medical record after verifying the logged-in user owns it.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM medical_history WHERE record_id = ? AND user_id = ?", (record_id, user_id))
    rows_affected = c.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def get_user_records(user_id, search_term=None, start_date=None, end_date=None,
                     record_source=None, sort_order="DESC"):
    """
    Retrieves all medical records belonging exclusively to user_id.
    Supports filtering by date range, search query across diagnosis, medicine, facility, doctor, notes.
    """
    conn = get_connection()
    sql = """
        SELECT mh.*, d.file_name as document_file_name, d.file_path as document_file_path
        FROM medical_history mh
        LEFT JOIN documents d ON mh.document_id = d.document_id
        WHERE mh.user_id = ?
    """
    params = [user_id]

    if start_date:
        sql += " AND mh.event_date >= ?"
        params.append(str(start_date)[:10])
    if end_date:
        sql += " AND mh.event_date <= ?"
        params.append(str(end_date)[:10])
    if record_source and record_source != "All Sources":
        sql += " AND mh.record_source = ?"
        params.append(record_source)

    if search_term and search_term.strip():
        term = f"%{search_term.strip()}%"
        sql += """ AND (
            mh.diagnosis LIKE ? OR
            mh.medicine LIKE ? OR
            mh.test_result LIKE ? OR
            mh.surgery LIKE ? OR
            mh.hospital_name LIKE ? OR
            mh.doctor_name LIKE ? OR
            mh.notes LIKE ?
        )"""
        params.extend([term, term, term, term, term, term, term])

    order = "ASC" if str(sort_order).upper() == "ASC" else "DESC"
    sql += f" ORDER BY mh.event_date {order}, mh.record_id {order}"

    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_user_record_by_id(user_id, record_id):
    """Retrieves a single record if and only if it belongs to user_id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT mh.*, d.file_name as document_file_name, d.file_path as document_file_path
        FROM medical_history mh
        LEFT JOIN documents d ON mh.document_id = d.document_id
        WHERE mh.record_id = ? AND mh.user_id = ?
    """, (record_id, user_id))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_user_stats(user_id):
    """Calculates dashboard metrics for the personal user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM medical_history WHERE user_id=?", (user_id,))
    total_records = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM documents WHERE user_id=?", (user_id,))
    total_documents = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT hospital_name) FROM medical_history WHERE user_id=? AND hospital_name != ''", (user_id,))
    total_facilities = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT doctor_name) FROM medical_history WHERE user_id=? AND doctor_name != ''", (user_id,))
    total_doctors = c.fetchone()[0]

    c.execute("""
        SELECT event_date, diagnosis, hospital_name, doctor_name, record_source
        FROM medical_history WHERE user_id=?
        ORDER BY event_date DESC, record_id DESC LIMIT 5
    """, (user_id,))
    recent_rows = [dict(r) for r in c.fetchall()]

    conn.close()
    return {
        "total_records": total_records,
        "total_documents": total_documents,
        "total_facilities": total_facilities,
        "total_doctors": total_doctors,
        "recent_activities": recent_rows
    }


# ════════════════════════════════════════════════════════════════════════
# DOCUMENTS & OCR STORAGE (STRICT USER OWNERSHIP ENFORCED)
# ════════════════════════════════════════════════════════════════════════

def save_user_document(user_id, doc_type, file_name, file_path, file_size=0, ocr_text=""):
    """
    Saves metadata for an uploaded medical document tied to the authenticated user.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT medical_id FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    med_id = row['medical_id'] if row and row['medical_id'] else f"USER{user_id}"

    c.execute("""
        INSERT INTO documents (
            user_id, medical_id, document_type, file_name, file_path, file_size, ocr_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, med_id, doc_type, file_name, file_path, file_size, ocr_text))
    conn.commit()
    doc_id = c.lastrowid
    conn.close()
    return doc_id


def get_user_documents(user_id):
    """Retrieves all documents belonging to user_id."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM documents WHERE user_id=? ORDER BY uploaded_at DESC",
        conn, params=[user_id]
    )
    conn.close()
    return df


def get_user_document_by_id(user_id, document_id):
    """Retrieves document metadata if and only if owned by user_id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def delete_user_document(user_id, document_id):
    """Deletes document record and unlinks from medical history if owned by user_id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT file_path FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id))
    row = c.fetchone()
    if not row:
        conn.close()
        return False

    fpath = row['file_path']
    c.execute("UPDATE medical_history SET document_id = NULL WHERE document_id = ? AND user_id = ?", (document_id, user_id))
    c.execute("DELETE FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id))
    conn.commit()
    conn.close()

    # Safely remove file from filesystem if exists
    if fpath and os.path.exists(fpath):
        try:
            os.remove(fpath)
        except Exception:
            pass

    return True


# ════════════════════════════════════════════════════════════════════════
# AUDIT LOGGING
# ════════════════════════════════════════════════════════════════════════

def add_audit_log(user_id, role="User", action="Action", medical_id="", hospital_id=""):
    """Logs user actions for privacy audit compliance without storing sensitive data."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO audit_logs (user_id, role, action, medical_id, hospital_id) VALUES (?, ?, ?, ?, ?)",
        (user_id, role, action, str(medical_id), str(hospital_id))
    )
    conn.commit()
    conn.close()


def get_user_audit_logs(user_id, limit=50):
    """Retrieves personal audit events for this user."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT timestamp, action FROM audit_logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
        conn, params=[user_id, limit]
    )
    conn.close()
    return df
