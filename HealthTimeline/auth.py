"""
MediTimeline - Personal Authentication & Session Management Module
Handles bcrypt password hashing, session state lifecycle, inactivity timeouts,
and password complexity validation.
"""

from datetime import datetime, timedelta
import os
import re
from typing import Tuple, Optional, Dict, Any
import bcrypt
import streamlit as st

DEFAULT_SESSION_TIMEOUT_MINUTES = 30
DEFAULT_MAX_SESSION_HOURS = 8


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with 12 rounds of salt.
    Safely enforces bcrypt's 72-byte max length limit.
    """
    if not password:
        return ""
    pwd_bytes = password.encode('utf-8')[:72] if isinstance(password, str) else password[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(rounds=12)).decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash in constant time."""
    if not password or not hashed_password:
        return False
    try:
        pwd_bytes = password.encode('utf-8')[:72] if isinstance(password, str) else password[:72]
        hash_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validates password complexity:
    - Minimum 8 characters, maximum 72 bytes
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    - At least 1 special character
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password.encode('utf-8')) > 72:
        return False, "Password cannot exceed 72 bytes in length."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one numeric digit (0-9)."
    if not re.search(r'[\W_]', password):
        return False, "Password must contain at least one special character (!@#$%^&* etc)."
    return True, ""


def login(user_dict: dict):
    """Initializes an authenticated personal user session with session start timestamps."""
    # Reset any previous session data safely
    logout(keep_notice=False)

    st.session_state['user_id'] = user_dict.get('id')
    st.session_state['username'] = user_dict.get('username', '')
    st.session_state['full_name'] = user_dict.get('full_name') or user_dict.get('username', '')
    st.session_state['email'] = user_dict.get('email', '')
    st.session_state['medical_id'] = user_dict.get('medical_id', '')
    st.session_state['role'] = 'User'
    st.session_state['is_minor'] = user_dict.get('is_minor', 0)
    st.session_state['guardian_verified'] = user_dict.get('guardian_verified', 1)
    st.session_state['logged_in'] = True

    now_iso = datetime.now().isoformat()
    st.session_state['login_timestamp'] = now_iso
    st.session_state['last_active'] = now_iso
    st.session_state['current_page'] = "Dashboard"


def check_session_validity() -> Tuple[bool, str]:
    """
    Checks if the current session has timed out due to inactivity or exceeded max lifetime.
    Returns: (is_valid: bool, message: str)
    """
    if not st.session_state.get('logged_in', False):
        return False, ""

    now = datetime.now()

    # Inactivity timeout check
    timeout_mins = int(os.getenv("SESSION_TIMEOUT_MINUTES", DEFAULT_SESSION_TIMEOUT_MINUTES))
    last_active_str = st.session_state.get('last_active')
    if last_active_str:
        try:
            last_active = datetime.fromisoformat(last_active_str)
            if now - last_active > timedelta(minutes=timeout_mins):
                logout(keep_notice=True)
                return False, f"Your session expired due to {timeout_mins} minutes of inactivity. Please sign in again."
        except Exception:
            pass

    # Maximum session lifetime check
    max_hours = int(os.getenv("MAX_SESSION_HOURS", DEFAULT_MAX_SESSION_HOURS))
    login_ts_str = st.session_state.get('login_timestamp')
    if login_ts_str:
        try:
            login_ts = datetime.fromisoformat(login_ts_str)
            if now - login_ts > timedelta(hours=max_hours):
                logout(keep_notice=True)
                return False, f"Maximum session duration ({max_hours} hours) reached. Please sign in again."
        except Exception:
            pass

    # Update last active timestamp
    st.session_state['last_active'] = now.isoformat()
    return True, ""


def logout(keep_notice: bool = False):
    """
    Destroys current session and wipes all cached user information from memory.
    Safely resets state without causing Streamlit widget key mutations.
    """
    notice = st.session_state.get('session_notice') if keep_notice else None

    # Reset authentication and identity state
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""
    st.session_state['full_name'] = ""
    st.session_state['email'] = ""
    st.session_state['medical_id'] = ""
    st.session_state['role'] = "User"
    st.session_state['is_minor'] = 0
    st.session_state['guardian_verified'] = 1
    st.session_state['login_timestamp'] = None
    st.session_state['last_active'] = None
    st.session_state['current_page'] = "Dashboard"

    # Clear user cached medical & session content
    for key in [
        'active_summary', 'summary_period_label', 'ocr_preview_data',
        'ocr_uploaded_filename', 'ocr_temp_filepath', 'pdf_download_bytes',
        'pdf_download_name'
    ]:
        if key in st.session_state:
            try:
                st.session_state[key] = None
            except Exception:
                pass

    if keep_notice and notice:
        st.session_state['session_notice'] = notice
    elif not keep_notice and 'session_notice' in st.session_state:
        st.session_state['session_notice'] = None


def is_authenticated() -> bool:
    """Checks if current session has an authenticated user."""
    return bool(st.session_state.get('logged_in', False)) and st.session_state.get('user_id') is not None


def get_current_user_id() -> Optional[int]:
    """Safely returns current session user_id or None."""
    return st.session_state.get('user_id', None)
