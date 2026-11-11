"""Upload validation, parsing, chunking, status lifecycle, dedupe and cleanup."""

from app.api import deps
from app.parsers import Section, parse_document
from app.services.chunking import chunk_sections
from tests.conftest import DB_NOTES, USER_A, upload
from tests.helpers import make_blank_pdf, make_docx, make_pdf


def _chunks(doc_id):
    return deps.memory_db.select("document_chunks", {"document_id": doc_id})


# ---------------------------------------------------------------- parsers & chunking (unit)
def test_pdf_parser_keeps_page_numbers():
    parsed = parse_document("pdf", make_pdf(["Page one about TCP.", "Page two about UDP."]))
    assert parsed.page_count == 2
    assert [s.page_number for s in parsed.sections] == [1, 2]
    assert "UDP" in parsed.sections[1].text


def test_docx_parser_uses_headings_as_sections():
    data = make_docx([("Week 1", ["Intro to SQL."]), ("Week 2", ["Joins combine tables."])])
    parsed = parse_document("docx", data)
    assert [s.section_title for s in parsed.sections] == ["Week 1", "Week 2"]


def test_markdown_parser_ignores_headings_in_code_blocks():
    md = b"# Real\ntext one\n```\n# not a heading\n```\n## Second\ntext two\n"
    parsed = parse_document("markdown", md)
    assert [s.section_title for s in parsed.sections] == ["Real", "Second"]
    assert "# not a heading" in parsed.sections[0].text


def test_chunker_respects_size_overlap_and_pages():
    long_text = " ".join(f"Sentence number {i} explains a concept." for i in range(300))
    chunks = chunk_sections([Section(long_text, page_number=7)], chunk_tokens=100, overlap_tokens=20)
    assert len(chunks) > 5
    assert all(len(c.content) <= 100 * 4 + 80 + 10 for c in chunks)
    assert all(c.page_number == 7 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # overlap: the start of chunk 2 repeats the end of chunk 1
    assert chunks[1].content.split()[0] in chunks[0].content


def test_chunks_never_cross_page_boundaries():
    chunks = chunk_sections([Section("Alpha page.", 1), Section("Beta page.", 2)], 600, 100)
    assert [(c.content, c.page_number) for c in chunks] == [("Alpha page.", 1), ("Beta page.", 2)]


# ---------------------------------------------------------------- upload + ingestion (API)
def test_upload_markdown_becomes_ready_with_chunks(client_a, workspace):
    r = upload(client_a, workspace["id"], "db-notes.md", DB_NOTES.encode(), "text/markdown")
    assert r.status_code == 201, r.text
    doc = client_a.get(f"/api/v1/documents/{r.json()['id']}").json()
    assert doc["status"] == "READY"
    assert doc["chunk_count"] == len(_chunks(doc["id"])) > 0
    assert all(len(c["embedding"]) == 768 for c in _chunks(doc["id"]))
    assert "storage_path" not in doc  # internal path is never exposed
    # stored privately under the owner's prefix
    assert any(k.startswith(f"{USER_A}/{workspace['id']}/") for k in deps.memory_storage.objects)


def test_upload_pdf_and_docx_and_txt(client_a, workspace):
    files = [
        ("week1.pdf", make_pdf(["Normalization reduces redundancy.", "BCNF is stricter than 3NF."]), "application/pdf"),
        (
            "week2.docx",
            make_docx([("Indexes", ["B+ trees keep keys sorted."])]),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("notes.txt", b"Plain text notes about query optimisation.", "text/plain"),
    ]
    for name, data, mime in files:
        r = upload(client_a, workspace["id"], name, data, mime)
        assert r.status_code == 201, (name, r.text)
        assert client_a.get(f"/api/v1/documents/{r.json()['id']}").json()["status"] == "READY", name
    docs = client_a.get(f"/api/v1/workspaces/{workspace['id']}/documents").json()
    pdf = next(d for d in docs if d["filename"] == "week1.pdf")
    assert pdf["page_count"] == 2
    assert {c["page_number"] for c in _chunks(pdf["id"])} == {1, 2}


def test_rejects_unsupported_extension(client_a, workspace):
    r = upload(client_a, workspace["id"], "slides.pptx", b"PK\x03\x04data", "application/octet-stream")
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_type"


def test_rejects_executable_disguised_as_text(client_a, workspace):
    r = upload(client_a, workspace["id"], "notes.txt", b"MZ\x90\x00 fake exe", "text/plain")
    assert r.status_code == 422 and r.json()["error"]["code"] == "executable_rejected"


def test_rejects_content_that_does_not_match_extension(client_a, workspace):
    r = upload(client_a, workspace["id"], "paper.pdf", b"just text, not a pdf", "application/pdf")
    assert r.status_code == 422 and r.json()["error"]["code"] == "mime_mismatch"
    r = upload(client_a, workspace["id"], "paper.pdf", make_pdf(["x"]), "image/png")
    assert r.status_code == 422 and r.json()["error"]["code"] == "mime_mismatch"


def test_rejects_files_over_size_limit(client_a, workspace, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = upload(client_a, workspace["id"], "big.txt", b"a" * (1024 * 1024 + 1), "text/plain")
    assert r.status_code == 422 and r.json()["error"]["code"] == "file_too_large"


def test_duplicate_file_in_same_workspace_is_rejected(client_a, workspace, ready_doc):
    r = upload(client_a, workspace["id"], "copy.md", DB_NOTES.encode(), "text/markdown")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_file"


def test_same_file_in_another_workspace_reuses_embeddings(client_a, workspace, ready_doc, monkeypatch):
    other = client_a.post("/api/v1/workspaces", json={"name": "Other"}).json()
    from app.providers.mock import MockProvider

    calls = []
    orig = MockProvider.embed_texts
    monkeypatch.setattr(MockProvider, "embed_texts", lambda self, texts, task: calls.append(task) or orig(self, texts, task=task))
    r = upload(client_a, other["id"], "db-notes.md", DB_NOTES.encode(), "text/markdown")
    doc = client_a.get(f"/api/v1/documents/{r.json()['id']}").json()
    assert doc["status"] == "READY" and doc["chunk_count"] == ready_doc["chunk_count"]
    assert "document" not in calls  # no new embedding API calls


def test_scanned_pdf_fails_with_clear_reason_and_can_be_reprocessed(client_a, workspace):
    r = upload(client_a, workspace["id"], "scan.pdf", make_blank_pdf(2), "application/pdf")
    doc = client_a.get(f"/api/v1/documents/{r.json()['id']}").json()
    assert doc["status"] == "FAILED"
    assert "OCR" in doc["error_message"]
    r = client_a.post(f"/api/v1/documents/{doc['id']}/process")
    assert r.status_code == 202
    assert client_a.get(f"/api/v1/documents/{doc['id']}").json()["status"] == "FAILED"


def test_processing_errors_never_leave_document_stuck(client_a, workspace, monkeypatch):
    from app.providers.mock import MockProvider

    def boom(self, texts, task):
        raise RuntimeError("provider down")

    monkeypatch.setattr(MockProvider, "embed_texts", boom)
    r = upload(client_a, workspace["id"], "n.md", b"# A\nsome text here", "text/markdown")
    doc = client_a.get(f"/api/v1/documents/{r.json()['id']}").json()
    assert doc["status"] == "FAILED" and doc["error_message"]


def test_reprocess_blocked_while_processing(client_a, ready_doc):
    from datetime import UTC, datetime

    deps.memory_db.update(
        "documents", {"id": ready_doc["id"]}, {"status": "PROCESSING", "processing_started_at": datetime.now(UTC).isoformat()}
    )
    r = client_a.post(f"/api/v1/documents/{ready_doc['id']}/process")
    assert r.status_code == 409


def test_other_user_cannot_access_or_upload(client_b, workspace, ready_doc):
    assert client_b.get(f"/api/v1/documents/{ready_doc['id']}").status_code == 404
    assert client_b.delete(f"/api/v1/documents/{ready_doc['id']}").status_code == 404
    assert client_b.get(f"/api/v1/workspaces/{workspace['id']}/documents").status_code == 404
    r = upload(client_b, workspace["id"], "x.md", b"# hi\nthere", "text/markdown")
    assert r.status_code == 404


def test_delete_document_removes_file_and_vectors(client_a, ready_doc):
    assert _chunks(ready_doc["id"])
    assert client_a.delete(f"/api/v1/documents/{ready_doc['id']}").status_code == 204
    assert _chunks(ready_doc["id"]) == []
    assert deps.memory_storage.objects == {}


def test_delete_workspace_cleans_everything(client_a, workspace, ready_doc):
    client_a.post(f"/api/v1/workspaces/{workspace['id']}/chat", json={"question": "What is normalization?"})
    assert client_a.delete(f"/api/v1/workspaces/{workspace['id']}").status_code == 204
    db = deps.memory_db
    for table in ("documents", "document_chunks", "conversations", "messages", "message_citations"):
        assert db.select(table) == [], table
    assert deps.memory_storage.objects == {}
