"""Default OCR is cache-only: earlier readings are reused, a new scanned page is never sent anywhere."""
import pymupdf

from amber import docs
from amber.ocr import CachedOCR, VisionOCR, reader_from_env


def _scanned_pdf(tmp_path):
    p = tmp_path / "scan.pdf"
    d = pymupdf.open()
    pg = d.new_page()
    pg.draw_rect(pymupdf.Rect(50, 50, 300, 200), color=(0, 0, 0), fill=(0.5, 0.5, 0.5))  # an image-only page
    d.save(p)
    return p


def test_default_reader_is_cache_only(monkeypatch):
    monkeypatch.delenv("AMBER_OCR", raising=False)
    assert isinstance(reader_from_env(), CachedOCR)
    monkeypatch.setenv("AMBER_OCR", "off")
    assert reader_from_env() is None
    monkeypatch.setenv("AMBER_OCR", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert isinstance(reader_from_env(), VisionOCR)


def test_uncached_scan_stays_unread_and_nothing_is_called(tmp_path, monkeypatch):
    monkeypatch.setattr(docs, "CACHE", tmp_path / "ocr")
    d = docs.load(_scanned_pdf(tmp_path), ocr=CachedOCR())
    assert d.scanned_pages == [1]  # reported as unread, not guessed


def test_cached_reading_from_another_engine_is_reused(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(docs, "CACHE", tmp_path / "ocr")
    pdf = _scanned_pdf(tmp_path)
    sha = docs._sha(pdf)
    (tmp_path / "ocr").mkdir()
    (tmp_path / "ocr" / f"{sha[:16]}-p1-{CachedOCR.prefer_cached[0]}.json").write_text(json.dumps({"text": "COOLANT HEATER 3744-4992W"}))
    d = docs.load(pdf, ocr=CachedOCR())
    assert d.pages[0].ocr and "3744-4992W" in d.pages[0].text and d.scanned_pages == []
