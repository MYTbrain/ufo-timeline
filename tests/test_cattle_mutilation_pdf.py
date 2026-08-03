import hashlib

import pytest

from scripts import cattle_mutilation_pdf as catalog_pdf


class FakePage:
    def __init__(self, text: str | None):
        self.text = text

    def extract_text(self) -> str | None:
        return self.text


def reader_factory_for(*texts: str | None):
    class FakeReader:
        def __init__(self, _path: str):
            self.pages = [FakePage(text) for text in texts]

    return FakeReader


def write_fake_pdf(tmp_path, content: bytes = b"not-a-real-pdf"):
    path = tmp_path / "COMBINED.pdf"
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def test_catalog_hash_mismatch_fails_before_reader_is_opened(tmp_path):
    path, _actual_hash = write_fake_pdf(tmp_path)

    def reader_must_not_open(_path: str):
        pytest.fail("reader opened before the source identity passed")

    with pytest.raises(catalog_pdf.CatalogPdfIntegrityError, match="SHA-256 mismatch"):
        catalog_pdf.scan_catalog_pdf(
            path,
            expected_sha256="0" * 64,
            reader_factory=reader_must_not_open,
        )


def test_catalog_scan_is_deterministic_and_preserves_page_order(tmp_path):
    path, expected_hash = write_fake_pdf(tmp_path)
    reader_factory = reader_factory_for(
        "1966 november Gallipolis\nOhio | United States",
        "1975 march 10 Whiteface\nTexas | United States",
    )

    first = catalog_pdf.scan_catalog_pdf(
        path,
        expected_sha256=expected_hash,
        reader_factory=reader_factory,
    )
    second = catalog_pdf.scan_catalog_pdf(
        path,
        expected_sha256=expected_hash,
        reader_factory=reader_factory,
    )

    assert first == second
    assert [page["provenance"]["page_number"] for page in first["pages"]] == [1, 2]
    assert [slot["location_text"] for slot in first["slots"]] == [
        "Gallipolis",
        "Whiteface",
    ]
    assert first["pages"][0]["text_sha256"] == hashlib.sha256(
        b"1966 november Gallipolis\nOhio | United States"
    ).hexdigest()


def test_slot_records_include_bounded_factual_text_and_exact_pdf_provenance(tmp_path):
    path, expected_hash = write_fake_pdf(tmp_path)
    result = catalog_pdf.scan_catalog_pdf(
        path,
        expected_sha256=expected_hash,
        reader_factory=reader_factory_for(
            "1966 november Gallipolis\nPennsylvania | United States\n"
            "1967Alamosa\nColorado | United States"
        ),
    )

    first, second = result["slots"]
    assert first["provenance"] == {
        "pdf_sha256": expected_hash,
        "page_number": 1,
        "slot_number": 1,
        "source_locator": "COMBINED.pdf#page=1&slot=1",
    }
    assert first["date_text"] == "1966 november"
    assert first["factual_text"] == (
        "1966 november - Gallipolis, Pennsylvania, United States"
    )
    assert second["date_text"] == "1967"
    assert second["location_text"] == "Alamosa"
    assert len(first["factual_text"]) <= catalog_pdf.MAX_FACTUAL_TEXT_CHARS


def test_index_only_page_does_not_turn_absence_into_negative_evidence(tmp_path):
    path, expected_hash = write_fake_pdf(tmp_path)
    result = catalog_pdf.scan_catalog_pdf(
        path,
        expected_sha256=expected_hash,
        reader_factory=reader_factory_for(
            "www.cropcirclecenter.com/donation\n"
            "no diagram\n"
            "more info needed\n"
            "1975 march 10 Whiteface\n"
            "Texas | United States"
        ),
    )

    page = result["pages"][0]
    assert page["narrative_coverage"] == "index_only"
    assert page["narrative_excerpt"] is None
    assert page["absence_interpretation"] == "unknown_not_negative_evidence"
    assert result["absence_policy"] == "unknown_not_negative_evidence"
    assert result["counts"]["index_only_pages"] == 1
    assert result["slots"][0]["narrative_coverage"] == "index_only"


def test_residual_story_text_is_short_and_classified_as_narrative(tmp_path):
    path, expected_hash = write_fake_pdf(tmp_path)
    result = catalog_pdf.scan_catalog_pdf(
        path,
        expected_sha256=expected_hash,
        reader_factory=reader_factory_for(
            "1972 june Pelotas\n"
            "Rio Grande do Sul | Brazil\n"
            "A report described sheep found mutilated beside the formation."
        ),
    )

    page = result["pages"][0]
    assert page["narrative_coverage"] == "narrative_present"
    assert "sheep found mutilated" in page["narrative_excerpt"]
    assert len(page["narrative_excerpt"]) <= catalog_pdf.MAX_FACTUAL_TEXT_CHARS
    assert result["counts"]["narrative_present_pages"] == 1
