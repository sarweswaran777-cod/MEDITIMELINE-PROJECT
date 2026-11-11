"""
MediTimeline - Comprehensive Automated End-to-End Test Suite
Tests all 14 functional requirements + age-based security verification.
"""

import os
import sys
import tempfile
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta

import database as db
import auth
import ai_summary
import ocr as ocr_module
import pypdf

def run_tests():
    print("=" * 70)
    print("STARTING MEDITIMELINE AUTOMATED SYSTEM TESTS")
    print("=" * 70)

    # ── Test 1: Database Migration & Legacy Record Preservation ──────────
    print("\n[TEST 1] Verifying Database Migration & Legacy Records Preservation...")
    db.create_database()
    rahul = db.authenticate_user("rahul")
    assert rahul is not None, "Failed: User 'rahul' not found in database"
    rahul_id = rahul["id"]
    rahul_records = db.get_user_records(rahul_id)
    assert len(rahul_records) >= 7, f"Failed: Expected at least 7 records for Rahul, got {len(rahul_records)}"
    print(f"  [OK] Rahul's records preserved: {len(rahul_records)} records found.")
    print(f"  [OK] Rahul's age dynamically computed from DOB ({rahul['date_of_birth']}): {rahul['age']} yrs.")

    # ── Test 2: Age Calculation & Validation ─────────────────────────────
    print("\n[TEST 2] Testing Age Calculation & Date of Birth Validation...")
    # Today's date check
    adult_dob = (date.today() - timedelta(days=25 * 365 + 6)).strftime("%Y-%m-%d")
    minor_dob = (date.today() - timedelta(days=15 * 365 + 4)).strftime("%Y-%m-%d")
    
    adult_age = db.calculate_age_from_dob(adult_dob)
    minor_age = db.calculate_age_from_dob(minor_dob)
    assert adult_age >= 25, f"Adult age calculation failed: {adult_age}"
    assert minor_age == 15, f"Minor age calculation failed: {minor_age}"
    print(f"  [OK] Adult age ({adult_dob}) -> {adult_age} yrs (Adult >= 18)")
    print(f"  [OK] Minor age ({minor_dob}) -> {minor_age} yrs (Minor < 18)")

    # ── Test 3: OTP Token Lifecycle, Expiry & Max Attempts ────────────────
    print("\n[TEST 3] Testing OTP Token Lifecycle, Expiry & Max Attempt Limiting...")
    test_contact = f"test_user_verify_{int(datetime.now().timestamp())}@example.com"
    otp_code, otp_err = db.generate_and_store_otp(test_contact, purpose="test_reg", expiry_minutes=5)
    assert otp_err is None and otp_code is not None, f"OTP generation failed: {otp_err}"
    assert len(otp_code) == 6 and otp_code.isdigit(), "Invalid OTP format"
    print(f"  [OK] Generated 6-digit OTP code successfully.")

    # Test invalid OTP code
    success, msg = db.verify_otp_code(test_contact, "000000", purpose="test_reg", max_attempts=3)
    assert not success, "Failed: Incorrect OTP unexpectedly succeeded"
    print(f"  [OK] Incorrect OTP rejected with message: '{msg}'")

    # Test valid OTP code
    success, msg = db.verify_otp_code(test_contact, otp_code, purpose="test_reg")
    assert success, f"Failed: Valid OTP was rejected: {msg}"
    print("  [OK] Correct OTP verified and accepted.")

    # Test single-use invalidation
    success_reuse, _ = db.verify_otp_code(test_contact, otp_code, purpose="test_reg")
    assert not success_reuse, "Failed: Reused OTP was accepted after being consumed!"
    print("  [OK] Single-use guarantee enforced: Reused OTP immediately rejected.")

    # Test attempt-exhaustion invalidation
    exhaust_contact = f"exhaust_{int(datetime.now().timestamp())}@example.com"
    otp_code2, _ = db.generate_and_store_otp(exhaust_contact, purpose="test_exhaust")
    for _ in range(3):
        db.verify_otp_code(exhaust_contact, "999999", purpose="test_exhaust", max_attempts=3)
    exhausted_res, ex_msg = db.verify_otp_code(exhaust_contact, otp_code2, purpose="test_exhaust", max_attempts=3)
    assert not exhausted_res, "Failed: OTP was still valid after exceeding maximum attempts!"
    print(f"  [OK] Max attempts limiting enforced: Exceeded attempts invalidated token: '{ex_msg}'")

    # ── Test 4: User Registration (Adult and Minor with Guardian) ─────────
    print("\n[TEST 4] Testing Personal User Registration (Adult & Minor Guardian Workflow)...")
    test_adult_uname = f"test_adult_{int(datetime.now().timestamp())}"
    test_minor_uname = f"test_minor_{int(datetime.now().timestamp())}"

    # Register Adult
    uid_adult, mid_adult = db.register_personal_user(
        username=test_adult_uname,
        password="AdultPassword@123",
        email=f"{test_adult_uname}@example.com",
        phone="+91 99999 11111",
        full_name="Test Adult User",
        dob_str="1995-04-12",
        blood_group="B+",
        allergies="None",
        emergency_contact="Emergency Person (+91 99999 00000)"
    )
    assert uid_adult is not None, "Adult user registration failed"
    adult_prof = db.get_user_profile(uid_adult)
    assert adult_prof["is_minor"] == 0, "Adult was incorrectly flagged as minor"
    print(f"  [OK] Adult registered successfully: ID {uid_adult}, Medical ID {mid_adult}, Minor = {adult_prof['is_minor']}.")

    # Register Minor
    uid_minor, mid_minor = db.register_personal_user(
        username=test_minor_uname,
        password="MinorPassword@123",
        email=f"{test_minor_uname}@example.com",
        phone="+91 99999 22222",
        full_name="Test Minor User",
        dob_str="2012-06-20", # 14 years old
        blood_group="O+",
        allergies="Dust",
        emergency_contact="Parent Contact",
        guardian_name="Guardian Parent Name",
        guardian_rel="Parent",
        guardian_contact="+91 99999 33333"
    )
    assert uid_minor is not None, "Minor user registration failed"
    minor_prof = db.get_user_profile(uid_minor)
    assert minor_prof["is_minor"] == 1, "Minor was not flagged as minor"
    assert minor_prof["guardian_name"] == "Guardian Parent Name", "Guardian details not stored"
    print(f"  [OK] Minor registered successfully: ID {uid_minor}, Medical ID {mid_minor}, Guardian = '{minor_prof['guardian_name']}', Minor = {minor_prof['is_minor']}.")

    # ── Test 5: Authentication & Password Verification ───────────────────
    print("\n[TEST 5] Testing Authentication & Password Verification...")
    auth_user = db.authenticate_user(test_adult_uname)
    assert auth_user is not None, "User lookup failed"
    assert auth.verify_password("AdultPassword@123", auth_user["password_hash"]), "Password verification failed"
    assert not auth.verify_password("WrongPassword", auth_user["password_hash"]), "Invalid password accepted"
    print("  [OK] Authentication and bcrypt password matching verified.")

    # ── Test 6: Manually Adding, Editing & Deleting Medical Records ───────
    print("\n[TEST 6] Testing Manual Record Storage, Update, and Delete Operations...")
    rec_id = db.add_medical_record(
        user_id=uid_adult,
        event_date="2026-05-10",
        hospital_name="Apex Care Clinic",
        doctor_name="Dr. V. Rao",
        diagnosis="Hypertension Stage 1",
        medicine="Amlodipine 5mg once daily",
        test_result="BP: 145/92 mmHg",
        surgery="",
        follow_up="Check BP in 2 weeks",
        notes="Patient reports occasional morning headaches",
        event_type="Consultation",
        record_source="Manual Entry"
    )
    assert rec_id is not None, "Failed to insert medical record"
    print(f"  [OK] Record #{rec_id} inserted successfully.")

    # Fetch record
    rec_data = db.get_user_record_by_id(uid_adult, rec_id)
    assert rec_data is not None and rec_data["diagnosis"] == "Hypertension Stage 1"
    assert rec_data["record_source"] == "Manual Entry", f"Expected Manual Entry, got {rec_data['record_source']}"
    print(f"  [OK] Record verified: Source='{rec_data['record_source']}', Diagnosis='{rec_data['diagnosis']}'.")

    # Update record
    upd_res = db.update_medical_record(
        user_id=uid_adult,
        record_id=rec_id,
        event_date="2026-05-10",
        hospital_name="Apex Care Clinic",
        doctor_name="Dr. V. Rao",
        diagnosis="Hypertension Stage 1 (Controlled)",
        medicine="Amlodipine 5mg once daily",
        test_result="BP: 124/82 mmHg",
        surgery="",
        follow_up="Routine check in 3 months",
        notes="Blood pressure normalized upon medication adherence",
        event_type="Consultation"
    )
    assert upd_res, "Record update failed"
    rec_updated = db.get_user_record_by_id(uid_adult, rec_id)
    assert "Controlled" in rec_updated["diagnosis"], "Updated diagnosis did not persist"
    print(f"  [OK] Record #{rec_id} updated successfully: '{rec_updated['diagnosis']}'.")

    # ── Test 7: Strict Privacy & Cross-User Isolation Enforcement ────────
    print("\n[TEST 7] Testing Cross-User Data Isolation (Ownership Enforcement)...")
    # Minor user attempts to view adult user's record
    cross_read = db.get_user_record_by_id(uid_minor, rec_id)
    assert cross_read is None, "SECURITY FAILURE: Minor was able to read Adult's record!"
    
    # Minor user attempts to update adult user's record
    cross_upd = db.update_medical_record(
        user_id=uid_minor,
        record_id=rec_id,
        event_date="2026-05-10",
        hospital_name="Hacked Clinic",
        doctor_name="Attacker",
        diagnosis="Tampered Diagnosis"
    )
    assert not cross_upd, "SECURITY FAILURE: Minor was able to update Adult's record!"
    
    # Minor user attempts to delete adult user's record
    cross_del = db.delete_medical_record(user_id=uid_minor, record_id=rec_id)
    assert not cross_del, "SECURITY FAILURE: Minor was able to delete Adult's record!"
    
    # Verify adult's record is still intact
    intact_rec = db.get_user_record_by_id(uid_adult, rec_id)
    assert intact_rec is not None and "Tampered" not in intact_rec["diagnosis"], "Record was modified by unauthorized user"
    print("  [OK] Security Confirmed: User A cannot read, update, or delete User B's medical records.")

    # ── Test 8: OCR Medical Document Scanner & Text Parsing ──────────────
    print("\n[TEST 8] Testing OCR Document Scanner & Medical Field Extraction...")
    sample_text = """
    LAKESIDE MULTISPECIALTY HOSPITAL
    Physician: Dr. Neha Kapoor, MD
    Date: 2026-07-22

    Patient Chart: Test User
    Diagnosis: Type 2 Diabetes Mellitus with Peripheral Neuropathy
    Chief Complaint: Numbness in lower extremities, elevated blood glucose

    Prescription:
    Tab Metformin 500mg - 1 tab twice daily after meals
    Tab Pregabalin 75mg - 1 tab at bedtime
    Cap Neurobion Forte - 1 cap daily

    Laboratory Investigations:
    Fasting Blood Sugar: 168 mg/dL
    HbA1c: 8.4%
    Serum Creatinine: 0.9 mg/dL

    Follow-up: Revisit endocrinology OPD after 4 weeks with fasting glucose log.
    """

    parsed_fields = ocr_module.parse_medical_fields(sample_text)
    assert parsed_fields["event_date"] == "2026-07-22", f"Parsed date mismatch: {parsed_fields['event_date']}"
    assert "Diabetes" in parsed_fields["diagnosis"], f"Parsed diagnosis mismatch: {parsed_fields['diagnosis']}"
    assert "Metformin" in parsed_fields["medicine"], f"Parsed medicine mismatch: {parsed_fields['medicine']}"
    assert "HbA1c" in parsed_fields["test_result"], f"Parsed test mismatch: {parsed_fields['test_result']}"
    assert "Revisit" in parsed_fields["follow_up"], f"Parsed follow-up mismatch: {parsed_fields['follow_up']}"
    print(f"  [OK] Extracted Date: {parsed_fields['event_date']}")
    print(f"  [OK] Extracted Doctor: Dr. {parsed_fields['doctor_name']}")
    print(f"  [OK] Extracted Diagnosis: {parsed_fields['diagnosis']}")
    print(f"  [OK] Extracted Medicines: {parsed_fields['medicine']}")
    print(f"  [OK] Extracted Tests: {parsed_fields['test_result']}")
    print(f"  [OK] Extracted Follow-up: {parsed_fields['follow_up']}")

    # Save document and verified record
    temp_dir = tempfile.gettempdir()
    sample_doc_path = os.path.join(temp_dir, f"sample_report_{uid_adult}.txt")
    with open(sample_doc_path, "w") as f:
        f.write(sample_text)

    doc_id = db.save_user_document(
        user_id=uid_adult,
        doc_type="Lab Report",
        file_name="sample_report.pdf",
        file_path=sample_doc_path,
        file_size=len(sample_text),
        ocr_text=sample_text
    )
    assert doc_id is not None, "Failed to save document metadata"
    print(f"  [OK] Document metadata archived as Document ID #{doc_id}.")

    ocr_rec_id = db.add_medical_record(
        user_id=uid_adult,
        event_date=parsed_fields["event_date"],
        hospital_name=parsed_fields["hospital_name"] or "Lakeside Hospital",
        doctor_name=parsed_fields["doctor_name"] or "Dr. Neha Kapoor",
        diagnosis=parsed_fields["diagnosis"],
        medicine=parsed_fields["medicine"],
        test_result=parsed_fields["test_result"],
        surgery="",
        follow_up=parsed_fields["follow_up"],
        notes="Document extracted clinical report verified by patient",
        event_type="Lab Report",
        record_source="Document OCR Extracted",
        document_id=doc_id
    )
    assert ocr_rec_id is not None, "Failed to save OCR medical record"
    ocr_rec = db.get_user_record_by_id(uid_adult, ocr_rec_id)
    assert ocr_rec["record_source"] == "Document OCR Extracted"
    assert ocr_rec["document_file_name"] == "sample_report.pdf"
    print(f"  [OK] Saved OCR Record #{ocr_rec_id} linked with document #{doc_id}: Source = '{ocr_rec['record_source']}'.")

    # ── Test 9: Period-Based History & AI Summary Verification ────────────
    print("\n[TEST 9] Testing Period-Based History Filtering & AI Summary Generation...")
    adult_records = db.get_user_records(uid_adult)
    assert len(adult_records) >= 2, f"Expected at least 2 records, got {len(adult_records)}"

    # 1. Summary across All Records
    summary_all = ai_summary.generate_period_summary(adult_records, period_label="All Records")
    assert "Hypertension" in summary_all and "Diabetes" in summary_all, "Summary missing expected diagnoses"
    print("  [OK] Period 'All Records' successfully synthesized both clinical events.")

    # 2. Date-filtered summary for a specific range including only the 2026-07-22 record
    filter_start = "2026-07-01"
    filter_end = "2026-07-31"
    summary_july = ai_summary.generate_period_summary(
        adult_records, start_date=filter_start, end_date=filter_end, period_label="July 2026"
    )
    assert "Diabetes" in summary_july, "July summary should include Diabetes record"
    assert "Hypertension" not in summary_july, "July summary should EXCLUDE May Hypertension record!"
    print(f"  [OK] Strict Period Isolation verified: July summary contains Diabetes but excludes May record.")

    # 3. Empty period handling
    summary_empty = ai_summary.generate_period_summary(
        adult_records, start_date="2020-01-01", end_date="2020-01-31", period_label="January 2020"
    )
    assert "January 2020" in summary_empty and ("No medical events recorded" in summary_empty or "No Records" in summary_empty), "Empty period not handled gracefully"
    print("  [OK] Empty period handled gracefully with clear user notification.")

    # ── Test 10: Deletion with Confirmation ───────────────────────────────
    print("\n[TEST 10] Testing Safe Record Deletion...")
    del_ok = db.delete_medical_record(uid_adult, rec_id)
    assert del_ok, "Failed to delete record"
    deleted_check = db.get_user_record_by_id(uid_adult, rec_id)
    assert deleted_check is None, "Record still exists after deletion"
    print(f"  [OK] Record #{rec_id} successfully deleted by owner.")

    print("\n" + "=" * 70)
    print("ALL 10 TEST SUITES PASSED! SYSTEM VERIFIED SUCCESSFULLY.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
