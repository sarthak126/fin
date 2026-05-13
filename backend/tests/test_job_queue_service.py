from services.job_queue_service import classify_analysis_error


def test_classify_analysis_error_detects_ai_provider_access_issue():
    code, message = classify_analysis_error(
        "403 PERMISSION_DENIED. {'error': {'message': 'Your project has been denied access.'}}"
    )

    assert code == "ai_provider_access_denied"
    assert message is not None
    assert "Gemini project" in message


def test_classify_analysis_error_detects_password_protected_pdf():
    code, message = classify_analysis_error("This PDF is password-protected. Please provide the password.")

    assert code == "pdf_password_required"
    assert message is not None
    assert "password-protected" in message


def test_classify_analysis_error_detects_ocr_provider_unavailable():
    code, message = classify_analysis_error("OCR provider unavailable: Google Document AI OCR processor is not configured.")

    assert code == "ocr_provider_unavailable"
    assert message is not None
    assert "OCR is unavailable" in message


def test_classify_analysis_error_detects_tesseract_missing():
    code, message = classify_analysis_error("Tesseract missing: Tesseract OCR executable is not installed or not available.")

    assert code == "tesseract_missing"
    assert message is not None
    assert "Tesseract" in message


def test_classify_analysis_error_detects_image_decode_failure():
    code, message = classify_analysis_error("Image decode failure: Uploaded image could not be decoded.")

    assert code == "image_decode_failed"
    assert message is not None
    assert "could not be decoded" in message


def test_classify_analysis_error_detects_ocr_no_readable_text():
    code, message = classify_analysis_error("OCR completed with no readable text.")

    assert code == "ocr_no_readable_text"
    assert message is not None
    assert "readable text" in message


def test_classify_analysis_error_detects_blocked_ocr_quality():
    code, message = classify_analysis_error(
        "OCR quality is insufficient for analysis (failed OCR pages: 2; unreliable OCR pages: 4)."
    )

    assert code == "ocr_quality_blocked"
    assert message is not None
    assert "blocked because OCR" in message


def test_classify_analysis_error_detects_unreadable_document_stream():
    code, message = classify_analysis_error("Failed to open stream")

    assert code == "document_stream_unreadable"
    assert message is not None
    assert "could not be opened" in message
