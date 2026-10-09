import json
from pathlib import Path

import pytest
from middleware.corpus_sources import (
    SourceFormatError,
    canonical_ref,
    is_known,
    merge_sources,
    parse_arxiv_atom,
    parse_s2_bulk,
    strip_version,
    title_key,
)

FIX = Path(__file__).parent / "fixtures" / "refresh"


def test_real_arxiv_response_parses():
    got = parse_arxiv_atom((FIX / "arxiv_real.xml").read_bytes())
    assert len(got) == 2
    first = got[0]
    assert first["ref"] == "arxiv:2610.07639" and first["arxivId"] == "2610.07639"
    assert first["title"].startswith("HarnessSecurity-Bench")
    assert first["year"] == 2026 and first["publishedAt"] == "2026-10-06"
    assert first["abstract"].startswith("Coding agent harnesses mediate")
    assert first["source"] == "arxiv" and first["authors"]


def test_real_s2_response_parses():
    got = parse_s2_bulk(json.loads((FIX / "s2_real.json").read_text()))
    assert len(got) == 2
    by_ref = {c["ref"]: c for c in got}
    assert "doi:10.66104/z67gjz21" in by_ref
    assert any(r.startswith("arxiv:") for r in by_ref)
    assert all(c["source"] == "s2" and c["title"] for c in got)


@pytest.mark.parametrize(
    "arxiv,doi,s2,expected",
    [
        ("2610.07639v2", None, None, "arxiv:2610.07639"),
        ("cs/0112017v1", None, None, "arxiv:cs/0112017"),
        (None, "10.48550/arXiv.2609.22049", None, "arxiv:2609.22049"),
        (None, "10.1145/ABC.123", None, "doi:10.1145/abc.123"),
        (None, None, "abc123", "s2:abc123"),
        (None, None, None, None),
    ],
)
def test_refs_follow_the_corpus_convention(arxiv, doi, s2, expected):
    assert canonical_ref(arxiv_id=arxiv, doi=doi, s2_id=s2) == expected


def test_version_suffix_is_stripped_only_at_the_end():
    assert strip_version("2610.07639v12") == "2610.07639"
    assert strip_version("2610.07639") == "2610.07639"


def test_dtd_and_entities_are_refused():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE feed [<!ENTITY a "aaaa">]>'
        b'<feed xmlns="http://www.w3.org/2005/Atom"><title>&a;</title></feed>'
    )
    with pytest.raises(SourceFormatError, match=r"DTD|entities"):
        parse_arxiv_atom(bomb)


@pytest.mark.parametrize(
    "body",
    [
        b" " * 3000 + b'<!DOCTYPE feed><feed xmlns="http://www.w3.org/2005/Atom"/>',
        '<!DOCTYPE feed><feed xmlns="http://www.w3.org/2005/Atom"/>'.encode("utf-16"),
    ],
    ids=["late-dtd", "utf16-dtd"],
)
def test_dtd_cannot_hide_after_the_prefix_or_in_utf16(body):
    with pytest.raises(SourceFormatError):
        parse_arxiv_atom(body)


@pytest.mark.parametrize("data", [None, "bad", {}])
def test_s2_data_must_be_an_array(data):
    with pytest.raises(SourceFormatError):
        parse_s2_bulk({"data": data})


def test_non_atom_xml_is_refused():
    with pytest.raises(SourceFormatError):
        parse_arxiv_atom(b"<error>upstream unavailable</error>")


def test_malformed_xml_is_a_source_format_error():
    with pytest.raises(SourceFormatError):
        parse_arxiv_atom(b"<feed><entry>")


def test_s2_without_data_is_refused():
    with pytest.raises(SourceFormatError):
        parse_s2_bulk({"message": "Too Many Requests"})


def test_entries_without_title_or_id_are_skipped():
    xml = (
        b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1v1</id>'
        b"<title> </title></entry></feed>"
    )
    assert parse_arxiv_atom(xml) == []


def test_merge_prefers_arxiv_text_and_fills_gaps_from_s2():
    arxiv = {
        "ref": "arxiv:1",
        "source": "arxiv",
        "title": "T",
        "abstract": "A",
        "venue": "arXiv",
        "doi": None,
        "s2Id": None,
        "citationCount": None,
        "url": "u",
    }
    s2 = {
        "ref": "arxiv:1",
        "source": "s2",
        "title": "T",
        "abstract": "other",
        "venue": "NeurIPS",
        "doi": "10.1/x",
        "s2Id": "p",
        "citationCount": 7,
        "url": "v",
    }
    [one] = merge_sources([s2, arxiv])
    assert one["abstract"] == "A" and one["venue"] == "NeurIPS"
    assert (
        one["doi"] == "10.1/x"
        and one["citationCount"] == 7
        and one["source"] == "arxiv"
    )


def test_known_by_ref_or_by_title():
    cand = {"ref": "arxiv:2", "title": "A  Study of: Things!"}
    assert is_known(cand, {"arxiv:2"}, set())
    assert is_known(cand, set(), {title_key("a study of things")})
    assert not is_known(cand, {"arxiv:3"}, {"other"})
