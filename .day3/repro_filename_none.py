"""
Day 3 / BUG-D3-1 reproduction.

mypy reported:
    app\\routers\\documents.py:38: error: Item "None" of "str | None" has no
    attribute "lower"  [union-attr]

`_validate_metadata()` calls `file.filename.lower()`. Starlette types
`UploadFile.filename` as `str | None`. The question this script answers is not
"is the annotation right" but "can a real HTTP client actually make filename
None, and what does the server do when it happens" — a type error that no
request can trigger is a documentation issue, not a defect.

Run from backend/ with the project venv:
    python ..\\.day3\\repro_filename_none.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def post_raw(body: bytes, label: str) -> None:
    """POST a hand-built multipart body so the filename parameter can be omitted."""
    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.post(
            "/api/documents/upload",
            content=body,
            headers={"Content-Type": "multipart/form-data; boundary=BOUNDARY"},
        )
        print(f"  {label:<46} -> HTTP {resp.status_code}  {resp.text[:110]}")
    except Exception as exc:  # the crash we are hunting for
        print(f"  {label:<46} -> RAISED {type(exc).__name__}: {exc}")


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

CASES = {
    # filename parameter entirely absent, but a Content-Type is present. This is
    # the shape that makes Starlette build an UploadFile with filename=None.
    "no filename param, with Content-Type": (
        b"--BOUNDARY\r\n"
        b'Content-Disposition: form-data; name="file"\r\n'
        b"Content-Type: application/pdf\r\n"
        b"\r\n" + PDF_BYTES + b"\r\n"
        b"--BOUNDARY--\r\n"
    ),
    # filename present but empty — the near-miss case, expected to be a clean 400.
    'filename="" (empty)': (
        b"--BOUNDARY\r\n"
        b'Content-Disposition: form-data; name="file"; filename=""\r\n'
        b"Content-Type: application/pdf\r\n"
        b"\r\n" + PDF_BYTES + b"\r\n"
        b"--BOUNDARY--\r\n"
    ),
    # control: a normal, valid upload.
    'filename="ok.pdf" (control)': (
        b"--BOUNDARY\r\n"
        b'Content-Disposition: form-data; name="file"; filename="ok.pdf"\r\n'
        b"Content-Type: application/pdf\r\n"
        b"\r\n" + PDF_BYTES + b"\r\n"
        b"--BOUNDARY--\r\n"
    ),
}


if __name__ == "__main__":
    print("POST /api/documents/upload — multipart filename variants\n")
    for label, body in CASES.items():
        post_raw(body, label)
    print(
        "\nA 500 or a raised AttributeError on the first case reproduces the defect."
        "\nA 400 on the first two cases means the guard already holds."
    )
