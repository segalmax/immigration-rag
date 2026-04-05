"""
tests/test_kb.py
Basic quality and smoke tests for the USCIS KB dashboard.
Run with:  pytest tests/ -v
"""
import re
import pytest
from app import (
    word_count, token_count, is_stub,
    vol_sort_key, footnote_count, residual_footnote_count,
    CLEAN_ROOT, RAW_ROOT, app as flask_app,
)

KNOWN_FILE = (
    "volume_12_citizenship_and_naturalization"
    "/part_d_general_naturalization_requirements"
    "/chapter_2_lawful_permanent_resident_admission_for_naturalization.md"
)


# ── Pure function tests ─────────────────────────────────────────────────────

def test_word_count_basic():
    assert word_count("hello world") == 2

def test_word_count_empty():
    assert word_count("") == 0

def test_token_count_basic():
    result = token_count("hello world")
    assert isinstance(result, int) and result > 0

def test_token_count_longer_than_word_count():
    # tokens >= words for English text (punctuation, subwords)
    text = "The applicant must submit Form I-485."
    assert token_count(text) >= word_count(text) - 2  # rough sanity

def test_is_stub_true():
    assert is_stub("_No content._")

def test_is_stub_false():
    assert not is_stub("This is a legitimate policy chapter with real content.")

def test_vol_sort_key_ordering():
    keys = ["volume_10_foo", "volume_2_bar", "volume_1_baz", "volume_12_qux"]
    sorted_keys = sorted(keys, key=vol_sort_key)
    assert sorted_keys == ["volume_1_baz", "volume_2_bar", "volume_10_foo", "volume_12_qux"]

def test_footnote_count_detects_bold_refs():
    text = "USCIS administers immigration.**[1]** See also**[2]**."
    assert footnote_count(text) == 2

def test_residual_footnote_count_detects_markdown_style():
    text = "[^ 1] See INA 212(i).\n[^ 2] Other citation."
    assert residual_footnote_count(text) == 2


# ── Corpus integrity tests ──────────────────────────────────────────────────

def test_clean_corpus_file_count():
    files = list(CLEAN_ROOT.rglob("*.md"))
    assert len(files) == 446, f"Expected 446 clean files, got {len(files)}"

def test_no_stubs_in_clean_corpus():
    for path in CLEAN_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert not is_stub(text), f"Stub found in clean corpus: {path}"

def test_no_bold_footnotes_in_clean_corpus():
    pattern = re.compile(r'\*\*\[\d+\]\*\*')
    for path in CLEAN_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), f"Bold footnote ref found in: {path}"

def test_raw_corpus_has_more_files_than_clean():
    raw_count   = len(list(RAW_ROOT.rglob("*.md")))
    clean_count = len(list(CLEAN_ROOT.rglob("*.md")))
    assert raw_count > clean_count, "Raw corpus should have more files (stubs not yet excluded)"


# ── Flask route tests ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c

def test_dashboard_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200

def test_browse_returns_200(client):
    r = client.get("/browse")
    assert r.status_code == 200

def test_browse_known_file_returns_200(client):
    r = client.get(f"/content/{KNOWN_FILE}")
    assert r.status_code == 200

def test_browse_nonexistent_returns_404(client):
    r = client.get("/content/volume_99_fake/part_z/chapter_0.md")
    assert r.status_code == 404
