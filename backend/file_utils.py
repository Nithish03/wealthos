"""Decryption helpers for password-protected statement files.

Both helpers speak a small protocol with the frontend: when a file needs a
password (or the given one is wrong) they raise HTTP 422 with a machine-readable
detail code so the UI can prompt the user and retry the same upload.
"""
import io
from typing import Optional
from fastapi import HTTPException

# Encrypted .xlsx files are wrapped in an OLE compound container
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _password_error(password_was_provided: bool) -> HTTPException:
    if password_was_provided:
        return HTTPException(status_code=422, detail={
            "code": "password_incorrect",
            "message": "Incorrect password for this file — try again.",
        })
    return HTTPException(status_code=422, detail={
        "code": "password_required",
        "message": "This file is password-protected. Enter the password to import it.",
    })


def decrypt_pdf_if_needed(content: bytes, password: Optional[str] = None) -> bytes:
    """Return decrypted PDF bytes. Unencrypted PDFs pass through untouched."""
    import pikepdf
    try:
        pdf = pikepdf.open(io.BytesIO(content))
    except pikepdf.PasswordError:
        if not password:
            raise _password_error(False)
        try:
            pdf = pikepdf.open(io.BytesIO(content), password=password)
        except pikepdf.PasswordError:
            raise _password_error(True)
    except Exception:
        # Not a PDF pikepdf understands — let the actual parsers report the error
        return content

    with pdf:
        if not pdf.is_encrypted:
            return content
        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()


def decrypt_xlsx_if_needed(content: bytes, password: Optional[str] = None) -> bytes:
    """Return decrypted XLSX bytes. Plain XLSX/CSV files pass through untouched."""
    if content[:8] != OLE_MAGIC:
        return content
    try:
        import msoffcrypto
    except ImportError:
        raise HTTPException(status_code=422, detail={
            "code": "password_required",
            "message": "This Excel file is encrypted; install 'msoffcrypto-tool' to import it.",
        })
    office = msoffcrypto.OfficeFile(io.BytesIO(content))
    try:
        if not office.is_encrypted():
            return content
    except Exception:
        return content
    if not password:
        raise _password_error(False)
    try:
        office.load_key(password=password)
        out = io.BytesIO()
        office.decrypt(out)
        return out.getvalue()
    except Exception:
        raise _password_error(True)
