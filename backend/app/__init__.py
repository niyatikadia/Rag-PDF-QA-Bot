"""
app — the PDF Q&A RAG Chatbot backend package.

`__version__` is the single source of the application's version number.

It lived in three independent places before this (the FastAPI app in main.py,
the /api/health response in routers/health.py, and frontend/package.json), and
a test asserted the health value literally. A release bump was therefore four
edits that had to agree, and the first missed one would make /api/health report
a version the process is not running — exactly the "I deployed, but am I hitting
the new code?" failure the version field was added to prevent.

frontend/package.json necessarily keeps its own copy, because npm owns that
file's format; the two are reconciled at release time and the release procedure
in CHANGELOG.md says so.
"""

__version__ = "1.1.0"
