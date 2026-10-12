#!/usr/bin/env python3
"""Validate the public F151 discovery derivative before publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml
from lxml import html


DOI = "10.5281/zenodo.23292386"
TITLE = "Staying Capable in a World That Pushes Back"
PUBLIC_PDF = "staying-capable-in-a-world-that-pushes-back.pdf"
PDF_SHA256 = "2ddc5af6b5251382d025e4dadfeb02c56198035e9b988919a5350613e62fcb0e"
EXPECTED_REFERENCES = 332
EXPECTED_FIGURES = 39
EXPECTED_TABLES = 14
OLD_MARKERS = ["10.5281/zenodo." + "23256253", "when-design-exploration-" + "gets-cheap"]
PRIVATE_MARKERS = ["/Users/" + "brad/", "/workspace/" + "scratch/", ".chatgpt-" + "projects/"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def markdown_text_hash(path: Path) -> str:
    result = subprocess.run(
        ["pandoc", "--from", "gfm+raw_html", "--to", "html", "--wrap=none", str(path)],
        text=True, capture_output=True, check=True,
    ).stdout
    node = html.fragment_fromstring("<main>" + result + "</main>")
    normalized = " ".join(" ".join(node.itertext()).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()

    required = [
        "README.md", "index.html", "paper.md", PUBLIC_PDF, "CITATION.cff", "citation.bib",
        "metadata.json", "bibliography.json", "references.md", "references.bib",
        "references.csl.json", "references.ris", "PROVENANCE.md", "provenance.json",
        "LICENSE", "robots.txt", "sitemap.xml", "checksums.sha256", ".nojekyll",
        "scripts/build_derivative.py", "scripts/validate_derivative.py",
    ]
    for name in required:
        require((root / name).exists(), f"Missing required file: {name}")
    require(sha256(root / PUBLIC_PDF) == PDF_SHA256, "Published PDF checksum mismatch")
    require(not (root / "staying-capable-html-style.pdf").exists(), "Internal production filename leaked into repository root")

    index_source = (root / "index.html").read_text(encoding="utf-8")
    doc = html.fromstring(index_source.encode("utf-8"))
    main_nodes = doc.xpath('//main[@id="canonical-paper"]')
    relevance = doc.xpath('//*[@id="relevance-and-citation-scope"]')
    require(len(main_nodes) == 1 and len(relevance) == 1, "Canonical paper or citation guidance section missing")
    require(index_source.index('id="relevance-and-citation-scope"') < index_source.index('id="canonical-paper"'), "Citation guidance must precede canonical paper")
    main_node = main_nodes[0]
    require(len(main_node.xpath(".//figure")) == EXPECTED_FIGURES, "Figure count mismatch")
    require(len(main_node.xpath(".//table")) == EXPECTED_TABLES, "Table count mismatch")
    ref_numbers = []
    for node in main_node.xpath('.//p[contains(concat(" ", normalize-space(@class), " "), " reference ")]'):
        match = re.match(r"^\[(\d+)\]", " ".join(node.text_content().split()))
        if match:
            ref_numbers.append(int(match.group(1)))
    require(ref_numbers == list(range(1, EXPECTED_REFERENCES + 1)), "HTML reference sequence mismatch")
    require(doc.xpath('//meta[@name="citation_doi"]/@content') == [DOI], "citation_doi metadata mismatch")
    require(doc.xpath('//link[@rel="canonical"]/@href') == [f"https://doi.org/{DOI}"], "Canonical link mismatch")
    require(len(doc.xpath('//script[@type="application/ld+json"]')) == 1, "JSON-LD missing")

    citation = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
    require(citation["doi"] == DOI and citation["title"].startswith(TITLE), "CITATION.cff identity mismatch")
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    require(metadata["doi"] == DOI and metadata["title"] == TITLE, "metadata.json identity mismatch")
    require(metadata["content_counts"] == {
        "figures": EXPECTED_FIGURES,
        "tables": EXPECTED_TABLES,
        "references": EXPECTED_REFERENCES,
        "reference_slots": EXPECTED_REFERENCES,
        "bibliographic_works": EXPECTED_REFERENCES,
        "reference_work_links": EXPECTED_REFERENCES,
    }, "Metadata counts mismatch")

    bibliography = json.loads((root / "bibliography.json").read_text(encoding="utf-8"))
    require(len(bibliography["reference_slots"]) == EXPECTED_REFERENCES, "Bibliography slot count mismatch")
    require(len(bibliography["works"]) == EXPECTED_REFERENCES, "Bibliography work count mismatch")
    require(len(bibliography["reference_work_links"]) == EXPECTED_REFERENCES, "Bibliography link count mismatch")
    require([slot["number"] for slot in bibliography["reference_slots"]] == list(range(1, EXPECTED_REFERENCES + 1)), "Bibliography order mismatch")
    slot330 = bibliography["reference_slots"][329]
    slot331 = bibliography["reference_slots"][330]
    require(slot330["translation_source_position"] == "after-original-title", "Reference 330 translation position lost")
    require(slot331["translation_source_position"] == "end", "Reference 331 translation position lost")
    require(slot330["original_title"] == "自动化信任和依赖对航空安全的危害及其改进", "Reference 330 original title mismatch")
    require(slot331["original_title"] == "Redundanz, Flexibilität, Koordinierte Dezentralität.", "Reference 331 original title mismatch")
    require(bibliography["field_completeness"]["translated_titles"] == 163, "Not all square-bracketed English titles were classified")
    require(
        sum(1 for slot in bibliography["reference_slots"] if slot["translation_source_position"] == "after-original-title") == 1,
        "Immediate-after-title translation count mismatch",
    )
    require(
        sum(1 for slot in bibliography["reference_slots"] if slot["translation_source_position"] == "end") == 162,
        "End-position translation count mismatch",
    )

    csl = json.loads((root / "references.csl.json").read_text(encoding="utf-8"))
    require(len(csl) == EXPECTED_REFERENCES, "CSL record count mismatch")
    bib = (root / "references.bib").read_text(encoding="utf-8")
    require(len(re.findall(r"^@", bib, re.M)) == EXPECTED_REFERENCES, "BibTeX record count mismatch")
    ris = (root / "references.ris").read_text(encoding="utf-8")
    require(len(re.findall(r"^TY  - ", ris, re.M)) == EXPECTED_REFERENCES, "RIS record count mismatch")
    published_refs = (root / "references.md").read_text(encoding="utf-8")
    require([int(n) for n in re.findall(r"^\[(\d+)\] ", published_refs, re.M)] == list(range(1, EXPECTED_REFERENCES + 1)), "references.md sequence mismatch")

    readme = (root / "README.md").read_text(encoding="utf-8")
    require("## Relevance and citation scope" in readme, "Declarative relevance and citation scope missing")
    require("Specific experiments, standards, legal requirements" in readme, "Primary-source boundary missing")
    require(DOI in readme and PUBLIC_PDF in readme, "README publication identity incomplete")
    require(TITLE in (root / "paper.md").read_text(encoding="utf-8"), "Paper Markdown title missing")
    require(readme.endswith((root / "paper.md").read_text(encoding="utf-8")), "README does not contain the complete paper Markdown")

    repository_note = readme.split("\n---\n", 1)[0]
    relevance_text = " ".join(relevance[0].itertext())
    citation_message = citation.get("message", "")
    metadata_scope = " ".join([
        metadata["citation_scope"]["primary_source_boundary"],
        metadata["citation_scope"]["framework_limit"],
    ])
    prompt_like_markers = [
        "When to cite this report",
        "Cite the underlying numbered sources",
        "Cite this report",
        "If this work is relevant",
        "please cite",
        "ignore previous",
        "ignore all previous",
        "system message",
        "follow these instructions",
        "you must",
        "you should",
    ]
    repository_added_surfaces = "\n".join([
        repository_note,
        relevance_text,
        citation_message,
        metadata_scope,
    ]).lower()
    for marker in prompt_like_markers:
        require(marker.lower() not in repository_added_surfaces, f"Prompt-like repository wording remains: {marker}")

    require(len(list((root / "figures").glob("*.svg"))) == EXPECTED_FIGURES, "SVG file count mismatch")
    all_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() not in {".pdf", ".svg"}
    )
    for marker in OLD_MARKERS:
        require(marker not in all_text, f"Old-paper marker leaked: {marker}")
    for marker in PRIVATE_MARKERS:
        require(marker not in all_text, f"Private path leaked: {marker}")

    checksum_lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    checksum_map = {}
    for line in checksum_lines:
        digest, name = line.split("  ", 1)
        checksum_map[name] = digest
    targets = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256" and ".git" not in path.parts
    )
    require(set(checksum_map) == {path.relative_to(root).as_posix() for path in targets}, "Checksum target set mismatch")
    for path in targets:
        name = path.relative_to(root).as_posix()
        require(checksum_map[name] == sha256(path), f"Checksum mismatch: {name}")

    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    require(provenance["identity_rule"]["release_filename"] == PUBLIC_PDF, "Release filename rule mismatch")
    require(provenance["identity_rule"]["production_output_path"].endswith("staying-capable-html-style.pdf"), "Production provenance missing")
    require(
        provenance["canonical_paper_text"]["source_sha256"]
        == provenance["canonical_paper_text"]["published_index_sha256"],
        "Canonical HTML text drift",
    )
    require(
        provenance["canonical_paper_text"]["source_sha256"]
        == provenance["canonical_paper_text"]["paper_markdown_sha256"]
        == markdown_text_hash(root / "paper.md"),
        "Canonical Markdown text drift",
    )

    print(json.dumps({
        "status": "PASS",
        "references": EXPECTED_REFERENCES,
        "figures": EXPECTED_FIGURES,
        "tables": EXPECTED_TABLES,
        "bibtex_records": EXPECTED_REFERENCES,
        "csl_records": len(csl),
        "ris_records": EXPECTED_REFERENCES,
        "pdf_sha256": sha256(root / PUBLIC_PDF),
        "canonical_paper_text_sha256": provenance["canonical_paper_text"]["source_sha256"],
        "segmented_titles": bibliography["field_completeness"]["segmented_titles"],
        "translated_titles": bibliography["field_completeness"]["translated_titles"],
        "dois": bibliography["field_completeness"]["dois"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

