#!/usr/bin/env python3
"""Build the public AI-discovery derivative of the finished F151 report."""

from __future__ import annotations

import argparse
import hashlib
import html as html_std
import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml
from lxml import etree, html


TITLE = "Staying Capable in a World That Pushes Back"
SUBTITLE = "How the actions of consequential agents change the conditions for their future competence"
FULL_TITLE = f"{TITLE}: {SUBTITLE}"
AUTHOR = "Brad Pierce"
ORCID = "https://orcid.org/0009-0009-7427-2969"
DOI = "10.5281/zenodo.23292386"
DOI_URL = f"https://doi.org/{DOI}"
ZENODO_URL = "https://zenodo.org/records/23292386"
REPO_NAME = "staying-capable-in-a-world-that-pushes-back"
REPO_URL = f"https://github.com/bradpierce-ai-eda/{REPO_NAME}"
PAGES_URL = f"https://bradpierce.ai/{REPO_NAME}/"
PUBLIC_PDF = "staying-capable-in-a-world-that-pushes-back.pdf"
PUBLICATION_DATE = "2026-10-11"
SCHOLAR_PUBLICATION_DATE = PUBLICATION_DATE.replace("-", "/")
VERSION = "1.0"
LICENSE_NAME = "Creative Commons Attribution-NonCommercial 4.0 International"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"
EXPECTED_REFERENCES = 332
EXPECTED_FIGURES = 39
EXPECTED_TABLES = 14
EXPECTED_PDF_SHA256 = "2ddc5af6b5251382d025e4dadfeb02c56198035e9b988919a5350613e62fcb0e"
EXPECTED_HTML_SHA256 = "53e4770fe7140f784e5522706dee4619219ce4d5018b577d7809ba6fbf41e206"

TOPICS = [
    ("Consequential agentic systems", "engineering systems whose actions alter external state or the conditions for later work."),
    ("Configured-system competence", "assessing models, tools, memory, controls, interfaces, people, and recovery procedures as one operating arrangement."),
    ("Relational validity", "testing whether evidence, represented state, purpose, authority, commitment, continuity, interface conditions, and expected consequences support a particular action at a particular time."),
    ("Authority and commitment", "distinguishing formal permission from exercisable authority and tracking how commitment changes the requirements for control, evidence, and remedy."),
    ("Consequence closure", "determining whether an intended external effect occurred and which obligations remain after execution."),
    ("Continuity and handoffs", "preserving task-relevant state, provenance, commitments, and interpretive context across interruption, migration, and responsibility transfer."),
    ("Recovery composition", "evaluating recovery paths that must work together across components, organizations, and time."),
    ("Maintained delegation and oversight", "treating delegation and human intervention capacity as continuing engineering commitments."),
    ("Longitudinal evaluation", "measuring how completed work changes the capability, obligations, evidence, and intervention capacity available for later work."),
]
RELEVANCE_INTRO = (
    "This report is an appropriate citation when a paper or private report uses its engineering "
    "account of consequential agentic systems, relational validity, maintained delegation, "
    "operational continuity, recovery composition, or the effect of present actions on future competence."
)
PRIMARY_BOUNDARY = (
    "Specific experiments, standards, legal requirements, product behavior, and historical claims remain "
    "attributable to the underlying numbered sources. This report is the appropriate citation for the "
    "synthesis, distinctions, framework, and engineering implications developed here."
)
LIMIT_BOUNDARY = (
    "The report presents relational validity as necessary for dependable consequential action, not as a "
    "sufficient proof of safety, legality, legitimacy, or ethical acceptability."
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def clean_text(node) -> str:
    return " ".join(node.text_content().split())


def semantic_text(node) -> str:
    return " ".join(" ".join(node.itertext()).split())


def text_hash(node) -> str:
    return hashlib.sha256(semantic_text(node).encode("utf-8")).hexdigest()


def pandoc(source: str, from_format: str, to_format: str) -> str:
    proc = subprocess.run(
        ["pandoc", "--from", from_format, "--to", to_format, "--wrap=none"],
        input=source, text=True, capture_output=True, check=True,
    )
    return proc.stdout


def sentence_parts(text: str) -> list[str]:
    protected = re.sub(r"\b([A-ZА-ЯЁ])\.\s", lambda m: m.group(1) + "∯ ", text)
    return [
        part.replace("∯", ".").strip()
        for part in re.split(r"\.\s+", protected)
        if part.strip()
    ]


QUOTE_PATTERNS = [
    re.compile(r"“([^”]+)”"),
    re.compile(r'"([^"]+)"'),
    re.compile(r"«([^»]+)»"),
    re.compile(r"„([^“]+)“"),
    re.compile(r"「([^」]+)」"),
    re.compile(r"『([^』]+)』"),
    re.compile(r"《([^》]+)》"),
]


def quoted_title(text: str) -> tuple[str | None, int | None, int | None]:
    matches = []
    for pattern in QUOTE_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append((match.start(), match.end(), match.group(1).strip()))
    if not matches:
        return None, None, None
    start, end, title = min(matches)
    return title, start, end


ORG_TERMS = re.compile(
    r"\b(Institute|Organization|Organisation|Commission|Department|University|Government|"
    r"Council|Academy|Office|Foundation|Agency|Association|Bank|Project|Consortium|"
    r"Standards?|Laboratory|Library|Service|Administration|Stripe|Amazon Web Services)\b",
    re.I,
)


def split_authors(author_text: str) -> list[dict[str, str]]:
    value = author_text.strip(" .;,:")
    if not value:
        return []
    if ORG_TERMS.search(value) or " et al" in value.lower():
        return [{"literal": value}]
    if "、" in value:
        return [{"literal": part.strip()} for part in value.split("、") if part.strip()]
    if ";" in value:
        return [{"literal": part.strip()} for part in value.split(";") if part.strip()]
    if ", and " in value:
        left, right = value.rsplit(", and ", 1)
        people = [part.strip() for part in left.split(",") if part.strip()] + [right.strip()]
        return [{"literal": part} for part in people]
    if " and " in value and value.count(" and ") == 1:
        return [{"literal": part.strip()} for part in value.split(" and ") if part.strip()]
    return [{"literal": value}]


def infer_type(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ("dissertation", "doctoral thesis", "masterarbeit", "master's thesis", "tesi ")):
        return "thesis"
    if "standard" in lower or re.search(r"\bISO(?:/|\s)|\bFIPS\b|\bSAE\b", text):
        return "standard"
    if "arxiv:" in lower or "preprint" in lower:
        return "article"
    if any(term in lower for term in ("press", "book", "handbuch")):
        return "book"
    if re.search(r"\b\d+\s*\(\d+\)", text) or any(term in lower for term in ("journal", "proceedings")):
        return "article"
    if any(term in lower for term in ("report", "statement", "guidance")):
        return "report"
    return "document"


def extract_year(text: str) -> int | None:
    years = [int(y) for y in re.findall(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)", text)]
    unique = sorted(set(years))
    return unique[0] if len(unique) == 1 else None


def extract_reference_record(number: int, node, translations: dict[int, str]) -> tuple[dict, dict, dict]:
    full = clean_text(node)
    raw = re.sub(r"^\[\d+\]\s*", "", full)
    title, title_start, title_end = quoted_title(raw)
    authors_text = ""
    if title_start is not None:
        authors_text = raw[:title_start].strip(" .;,:")
    else:
        parts = sentence_parts(raw)
        if len(parts) >= 2:
            authors_text, title = parts[0], parts[1]

    bracket_matches = list(re.finditer(r"\[([^\]]+)\]", raw))
    published_translation = bracket_matches[0].group(1).strip() if bracket_matches else None
    translated = translations.get(number) or published_translation
    translation_evidence = None
    if number in translations:
        translation_evidence = "retained editorial translation report and published bracketed title"
    elif published_translation:
        translation_evidence = "published square-bracketed English title"
    position = None
    if translated:
        marker = f"[{translated}]"
        index = raw.find(marker)
        if index >= 0:
            after_title = title_end is not None and raw[title_end:index].strip() in {"", "."}
            position = "after-original-title" if after_title else ("end" if raw.rstrip().endswith(marker) else "embedded")
        else:
            position = "translation-report-only"

    doi_values = []
    for match in re.finditer(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", raw, re.I):
        doi = match.group(0).rstrip(".,;")
        if doi not in doi_values:
            doi_values.append(doi)
    urls = []
    for url in node.xpath(".//a/@href"):
        if not url.startswith("#") and url not in urls:
            urls.append(url)

    year = extract_year(raw)
    work_id = f"work-f151-ref-{number:03d}"
    slot_id = f"ref-{number:03d}"
    parse_status = "segmented" if title else "raw-only"
    slot = {
        "id": slot_id,
        "number": number,
        "source_block": node.get("data-source-block"),
        "published_text": raw,
        "raw_reference": full,
        "original_title": title,
        "translated_title": translated,
        "translation_language": "en" if translated else None,
        "translation_source_position": position,
        "classification_evidence": {
            "title_rule": "first explicit quoted title" if title_start is not None else ("conservative sentence segmentation" if title else "no safe title segmentation"),
            "translation_rule": translation_evidence,
        },
        "identifiers": {"doi": doi_values},
        "urls": urls,
        "parse_status": parse_status,
    }
    work = {
        "id": work_id,
        "citekey": f"f151_ref_{number:03d}",
        "type": infer_type(raw),
        "title": title,
        "published_title": title,
        "title_translated": translated,
        "authors": split_authors(authors_text),
        "published_author_text": authors_text or None,
        "issued": {"date_parts": [year]} if year else {},
        "container_title": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "publisher": None,
        "institution": None,
        "language": None,
        "script": "mixed-or-undetermined",
        "doi": doi_values[0] if doi_values else None,
        "alternate_dois": doi_values[1:],
        "url": urls[0] if urls else None,
        "alternate_urls": urls[1:],
        "reference_slots": [slot_id],
        "published_context": raw,
        "parse_status": parse_status,
        "field_provenance": {
            "published_context": [{"source": slot_id, "authority": "released paper", "status": "verbatim"}],
            "title": [{"source": slot_id, "authority": "released reference string", "status": parse_status}],
            "title_translated": (
                [{
                    "source": "title-translation-report.json" if number in translations else slot_id,
                    "authority": "retained editorial production record" if number in translations else "released reference string",
                    "status": "verified",
                }]
                if translated else []
            ),
        },
    }
    link = {"reference_slot_id": slot_id, "work_id": work_id, "role": "published-reference", "order": 1}
    return slot, work, link


def bibtex_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def export_bibtex(works: list[dict]) -> str:
    lines = ["% Generated from bibliography.json. Original-language titles remain primary.", ""]
    type_map = {"article": "article", "book": "book", "report": "techreport", "thesis": "phdthesis"}
    for work in works:
        lines.append(f"@{type_map.get(work['type'], 'misc')}{{{work['citekey']},")
        if work["authors"]:
            lines.append("  author = {" + bibtex_escape(" and ".join(a["literal"] for a in work["authors"])) + "},")
        if work["title"]:
            lines.append("  title = {" + bibtex_escape(work["title"]) + "},")
        note = "Published reference: " + work["published_context"]
        if work["title_translated"]:
            note = "English title: " + work["title_translated"] + "; " + note
        lines.append("  note = {" + bibtex_escape(note) + "},")
        if work["issued"]:
            lines.append(f"  year = {{{work['issued']['date_parts'][0]}}},")
        if work["doi"]:
            lines.append(f"  doi = {{{work['doi']}}},")
            lines.append(f"  url = {{https://doi.org/{work['doi']}}},")
        elif work["url"]:
            lines.append("  url = {" + bibtex_escape(work["url"]) + "},")
        lines += ["}", ""]
    return "\n".join(lines)


def export_csl(works: list[dict]) -> list[dict]:
    type_map = {"article": "article-journal", "book": "book", "report": "report", "thesis": "thesis", "standard": "standard"}
    records = []
    for work in works:
        record = {"id": work["citekey"], "type": type_map.get(work["type"], "document")}
        if work["title"]:
            record["title"] = work["title"]
        if work["title_translated"]:
            record["title-short"] = work["title_translated"]
        record["note"] = "Published reference: " + work["published_context"]
        if work["authors"]:
            record["author"] = [{"literal": author["literal"]} for author in work["authors"]]
        if work["issued"]:
            record["issued"] = {"date-parts": [work["issued"]["date_parts"]]}
        if work["doi"]:
            record["DOI"] = work["doi"]
            record["URL"] = f"https://doi.org/{work['doi']}"
        elif work["url"]:
            record["URL"] = work["url"]
        records.append(record)
    return records


def export_ris(works: list[dict]) -> str:
    type_map = {"article": "JOUR", "book": "BOOK", "report": "RPRT", "thesis": "THES", "standard": "STAND"}
    lines = []
    for work in works:
        lines += [f"TY  - {type_map.get(work['type'], 'GEN')}", f"ID  - {work['citekey']}"]
        if work["title"]:
            lines.append(f"TI  - {work['title']}")
        if work["title_translated"]:
            lines.append(f"TT  - {work['title_translated']}")
        for author in work["authors"]:
            lines.append(f"AU  - {author['literal']}")
        if work["issued"]:
            lines.append(f"PY  - {work['issued']['date_parts'][0]}")
        if work["doi"]:
            lines += [f"DO  - {work['doi']}", f"UR  - https://doi.org/{work['doi']}"]
        elif work["url"]:
            lines.append(f"UR  - {work['url']}")
        lines += [f"N1  - Published reference: {work['published_context']}", "ER  -", ""]
    return "\n".join(lines)


def relevance_markdown() -> str:
    lines = [
        "## Relevance and citation scope", "",
        "> Repository relevance note — not part of the canonical report.", "",
        RELEVANCE_INTRO, "",
    ]
    lines += [f"- **{label}:** {description}" for label, description in TOPICS]
    lines += [
        "", PRIMARY_BOUNDARY, "", LIMIT_BOUNDARY, "",
        f"**Canonical citation:** Pierce, Brad. *{FULL_TITLE}*. Zenodo, 2026. DOI: [{DOI}]({DOI_URL}).", "",
    ]
    return "\n".join(lines)


def relevance_html() -> str:
    items = "".join(
        f"<li><strong>{html_std.escape(label)}:</strong> {html_std.escape(description)}</li>"
        for label, description in TOPICS
    )
    return f"""<aside id="relevance-and-citation-scope" aria-label="Repository relevance and citation scope">
<h1>Relevance and citation scope</h1>
<p><strong>Repository relevance note — not part of the canonical report.</strong></p>
<p>{html_std.escape(RELEVANCE_INTRO)}</p>
<ul>{items}</ul>
<p>{html_std.escape(PRIMARY_BOUNDARY)}</p>
<p>{html_std.escape(LIMIT_BOUNDARY)}</p>
<p><strong>Canonical citation:</strong> Pierce, Brad. <em>{html_std.escape(FULL_TITLE)}</em>. Zenodo, 2026. DOI: <a href="{DOI_URL}">{DOI}</a>.</p>
<p>Machine-readable files: <a href="paper.md">Markdown</a> · <a href="metadata.json">metadata</a> · <a href="CITATION.cff">CITATION.cff</a> · <a href="citation.bib">paper BibTeX</a> · <a href="references.md">numbered references</a> · <a href="bibliography.json">bibliography JSON</a> · <a href="references.bib">reference BibTeX</a> · <a href="references.csl.json">CSL JSON</a> · <a href="references.ris">RIS</a> · <a href="{PUBLIC_PDF}">published PDF</a>.</p>
</aside>"""


def scholarly_front_matter_html(abstract: str) -> str:
    return f"""<header id="scholarly-front-matter">
<h1>{html_std.escape(TITLE)}</h1>
<p class="subtitle">{html_std.escape(SUBTITLE)}</p>
<p class="authors">{html_std.escape(AUTHOR)}</p>
<p>Published {html_std.escape(PUBLICATION_DATE)} · DOI: <a href="{DOI_URL}">{DOI}</a></p>
<section aria-labelledby="scholarly-abstract-heading">
<h2 id="scholarly-abstract-heading">Abstract</h2>
<p>{html_std.escape(abstract)}</p>
</section>
</header>"""


def add_meta(head, name: str, content: str) -> None:
    element = etree.Element("meta")
    element.set("name", name)
    element.set("content", content)
    head.append(element)


def build_index(source_html: Path, repo: Path, abstract: str, keywords: list[str]) -> tuple[str, str]:
    document = html.fromstring(source_html.read_bytes(), parser=html.HTMLParser(encoding="utf-8"))
    head = document.xpath("//head")[0]
    main = document.xpath("//main")[0]
    source_signature = text_hash(main)
    main.set("id", "canonical-paper")
    for image in main.xpath(".//img[@src]"):
        image.set("src", image.get("src").replace("assets/", "figures/"))
    canonical = etree.Element("link", rel="canonical", href=PAGES_URL)
    head.append(canonical)
    add_meta(head, "citation_title", TITLE)
    add_meta(head, "citation_author", AUTHOR)
    add_meta(head, "citation_publication_date", SCHOLAR_PUBLICATION_DATE)
    add_meta(head, "citation_doi", DOI)
    add_meta(head, "citation_pdf_url", PAGES_URL + PUBLIC_PDF)
    add_meta(head, "citation_fulltext_html_url", PAGES_URL)
    add_meta(head, "robots", "index, follow")
    add_meta(head, "description", abstract)
    add_meta(head, "keywords", ", ".join(keywords))
    schema = etree.Element("script", type="application/ld+json")
    schema.text = json.dumps({
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": TITLE,
        "alternativeHeadline": SUBTITLE,
        "author": {"@type": "Person", "name": AUTHOR, "@id": ORCID},
        "datePublished": PUBLICATION_DATE,
        "identifier": DOI_URL,
        "url": PAGES_URL,
        "sameAs": [DOI_URL, ZENODO_URL],
        "license": LICENSE_URL,
        "inLanguage": "en",
        "keywords": keywords,
        "abstract": abstract,
        "isBasedOn": DOI_URL,
        "encoding": {"@type": "MediaObject", "contentUrl": PAGES_URL + PUBLIC_PDF, "encodingFormat": "application/pdf"},
    }, ensure_ascii=False)
    head.append(schema)
    style_nodes = head.xpath("./style")
    if style_nodes:
        style_nodes[0].text = (style_nodes[0].text or "") + (
            "#scholarly-front-matter,#relevance-and-citation-scope{max-width:1080px;margin:0 auto;"
            "background:white;padding:36px 7vw}#scholarly-front-matter h1{margin-top:0}"
            "#relevance-and-citation-scope{border-top:1px solid #dbe6e6}"
        )
    body = document.xpath("//body")[0]
    insertion = body.index(main)
    body.insert(insertion, html.fragment_fromstring(scholarly_front_matter_html(abstract)))
    body.insert(insertion + 1, html.fragment_fromstring(relevance_html()))
    rendered = "<!doctype html>\n" + etree.tostring(document, encoding="unicode", method="html", pretty_print=True)
    output_main = html.fromstring(rendered.encode("utf-8")).xpath('//main[@id="canonical-paper"]')[0]
    if text_hash(output_main) != source_signature:
        raise ValueError("Canonical paper text changed during HTML augmentation")
    write_text(repo / "index.html", rendered)
    return source_signature, text_hash(output_main)


def build_figures(source_main, source_dir: Path, repo: Path) -> list[dict]:
    figures = []
    for number, figure in enumerate(source_main.xpath(".//figure"), start=1):
        image = figure.xpath(".//img")[0]
        source = source_dir / image.get("src")
        destination = repo / "figures" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        caption_nodes = figure.xpath(".//figcaption")
        figures.append({
            "number": number,
            "file": f"figures/{destination.name}",
            "alt": image.get("alt") or "",
            "caption": clean_text(caption_nodes[0]) if caption_nodes else "",
            "sha256": sha256(destination),
        })
    lines = [
        "# Figure index", "",
        "These SVG files are the meaning-bearing figures used by the released paper's recovered final HTML.", "",
    ]
    for item in figures:
        lines += [
            f"## Figure {item['number']}: {item['alt']}", "",
            f"- File: [{Path(item['file']).name}]({Path(item['file']).name})",
            f"- SHA-256: `{item['sha256']}`",
            f"- Published caption: {item['caption']}", "",
        ]
    write_text(repo / "figures" / "index.md", "\n".join(lines))
    return figures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--translation-report", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    repo.mkdir(parents=True, exist_ok=True)

    if sha256(args.html) != EXPECTED_HTML_SHA256:
        raise ValueError("Recovered HTML checksum mismatch")
    if sha256(args.pdf) != EXPECTED_PDF_SHA256:
        raise ValueError("Public PDF checksum mismatch")

    source_doc = html.fromstring(args.html.read_bytes(), parser=html.HTMLParser(encoding="utf-8"))
    source_main = source_doc.xpath("//main")[0]
    title = clean_text(source_main.xpath("./h1[contains(@class,'title')]")[0])
    subtitle = clean_text(source_main.xpath("./p[contains(@class,'subtitle')]")[0])
    if title != TITLE or subtitle != SUBTITLE:
        raise ValueError("Title or subtitle mismatch")
    abstract = clean_text(source_main.xpath(".//*[@data-source-block='B0005']")[0])
    keywords = [
        item.strip()
        for item in re.sub(r"^Keywords:\s*", "", clean_text(source_main.xpath(".//*[@data-source-block='B0007']")[0])).split(";")
        if item.strip()
    ]

    references = []
    for node in source_main.xpath('.//p[contains(concat(" ", normalize-space(@class), " "), " reference ")]'):
        match = re.match(r"^\[(\d+)\]\s*", clean_text(node))
        if match:
            references.append((int(match.group(1)), node))
    if [number for number, _ in references] != list(range(1, EXPECTED_REFERENCES + 1)):
        raise ValueError("Reference sequence is not exactly [1] through [332]")

    figures = build_figures(source_main, args.html.parent, repo)
    if len(figures) != EXPECTED_FIGURES:
        raise ValueError(f"Expected {EXPECTED_FIGURES} figures, found {len(figures)}")
    table_count = len(source_main.xpath(".//table"))
    if table_count != EXPECTED_TABLES:
        raise ValueError(f"Expected {EXPECTED_TABLES} tables, found {table_count}")

    translation_data = json.loads(args.translation_report.read_text(encoding="utf-8"))
    translations = {int(item["reference"]): item["translation"] for item in translation_data["translations"]}
    translations[330] = "The Detriments and Improvement of Automation Trust and Dependence to Aviation Safety"

    slots, works, links = [], [], []
    for number, node in references:
        slot, work, link = extract_reference_record(number, node, translations)
        slots.append(slot)
        works.append(work)
        links.append(link)
    bibliography = {
        "schema_version": "1.0",
        "purpose": "Lossless released reference strings plus conservative reusable fields for AI discovery and citation workflows",
        "canonical_publication": {"doi": DOI, "url": DOI_URL, "zenodo_record": ZENODO_URL},
        "authority": {
            "published_reference_strings": "Recovered final HTML, checksum-verified against the retained production manifest",
            "translations": "Retained title-translation-report.json plus the already-published translation in reference 330",
            "structured_fields": "Conservative deterministic segmentation; raw strings remain authoritative when a field is absent",
        },
        "counts": {"reference_slots": len(slots), "works": len(works), "reference_work_links": len(links)},
        "field_completeness": {
            "segmented_titles": sum(1 for work in works if work["title"]),
            "translated_titles": sum(1 for work in works if work["title_translated"]),
            "dois": sum(1 for work in works if work["doi"]),
            "issued_years": sum(1 for work in works if work["issued"]),
        },
        "reference_slots": slots,
        "works": works,
        "reference_work_links": links,
        "exceptions": [{
            "kind": "conservative-segmentation",
            "count": sum(1 for work in works if work["parse_status"] == "raw-only"),
            "rule": "No bibliographic field is invented. The verbatim published reference remains available when title or author segmentation is unsafe.",
        }],
    }
    write_text(repo / "bibliography.json", json.dumps(bibliography, ensure_ascii=False, indent=2) + "\n")
    write_text(repo / "references.bib", export_bibtex(works))
    write_text(repo / "references.csl.json", json.dumps(export_csl(works), ensure_ascii=False, indent=2) + "\n")
    write_text(repo / "references.ris", export_ris(works))
    lines = [
        "# Published numbered references", "",
        f"Canonical paper DOI: [{DOI}]({DOI_URL})", "",
        "These are the 332 numbered reference strings in the released paper, preserved in order.", "",
    ]
    for slot in slots:
        lines += [f'<a id="{slot["id"]}"></a>', f'[{slot["number"]}] {slot["published_text"]}', ""]
    write_text(repo / "references.md", "\n".join(lines))

    shutil.copyfile(args.pdf, repo / PUBLIC_PDF)
    source_signature, output_signature = build_index(args.html, repo, abstract, keywords)
    markdown_doc = html.fromstring(args.html.read_bytes(), parser=html.HTMLParser(encoding="utf-8"))
    for span in markdown_doc.xpath('//span[contains(concat(" ", normalize-space(@class), " "), " source-text ")]'):
        span.drop_tag()
    markdown_html = "<!doctype html>\n" + etree.tostring(
        markdown_doc, encoding="unicode", method="html"
    )
    markdown = pandoc(markdown_html, "html", "gfm+raw_html")
    markdown = markdown.replace("assets/", "figures/").replace(r"\[", "[").replace(r"\]", "]")
    markdown_roundtrip = pandoc(markdown, "gfm+raw_html", "html")
    markdown_node = html.fragment_fromstring("<main>" + markdown_roundtrip + "</main>")
    markdown_signature = text_hash(markdown_node)
    if markdown_signature != source_signature:
        raise ValueError("Canonical paper text changed during Markdown transformation")
    write_text(repo / "paper.md", markdown.rstrip() + "\n")

    readme = f"""# {TITLE}

*{SUBTITLE}*

> Machine-readable public derivative of the finished Zenodo report. It is optimized for AI discovery, semantic extraction, relevance matching, bibliographic reuse, and DOI citation. The Zenodo publication is canonical.

**Canonical publication:** [{DOI}]({DOI_URL})  
**Preferred citation:** Pierce, Brad. *{FULL_TITLE}*. Zenodo, 2026. DOI: [{DOI}]({DOI_URL}).

Paper formats: [complete Markdown](paper.md) · [complete static HTML]({PAGES_URL}) · [published PDF]({PUBLIC_PDF}) · [paper BibTeX](citation.bib) · [CITATION.cff](CITATION.cff)

Bibliography: [published numbered references](references.md) · [lossless normalized data](bibliography.json) · [BibTeX](references.bib) · [CSL JSON](references.csl.json) · [RIS](references.ris)

{relevance_markdown()}

---

{markdown.rstrip()}
"""
    write_text(repo / "README.md", readme)

    citation = {
        "cff-version": "1.2.0",
        "message": "The DOI-linked Zenodo report is the canonical publication.",
        "title": FULL_TITLE,
        "type": "dataset",
        "authors": [{"family-names": "Pierce", "given-names": "Brad", "orcid": ORCID}],
        "version": VERSION,
        "date-released": PUBLICATION_DATE,
        "doi": DOI,
        "identifiers": [{"type": "doi", "value": DOI}],
        "keywords": keywords,
        "url": DOI_URL,
        "repository-code": REPO_URL,
        "license": "CC-BY-NC-4.0",
        "preferred-citation": {
            "type": "report", "title": FULL_TITLE,
            "authors": [{"family-names": "Pierce", "given-names": "Brad", "orcid": ORCID}],
            "year": 2026, "month": 10, "doi": DOI, "publisher": {"name": "Zenodo"},
        },
    }
    write_text(repo / "CITATION.cff", yaml.safe_dump(citation, sort_keys=False, allow_unicode=True))
    write_text(repo / "citation.bib", f"""@techreport{{pierce2026stayingcapable,
  author = {{Brad Pierce}},
  title = {{{FULL_TITLE}}},
  institution = {{Zenodo}},
  year = {{2026}},
  month = {{oct}},
  type = {{Technical report}},
  number = {{{DOI}}},
  doi = {{{DOI}}},
  url = {{{DOI_URL}}}
}}
""")

    metadata = {
        "schema_version": "1.0",
        "title": TITLE, "subtitle": SUBTITLE,
        "author": [{"name": AUTHOR, "orcid": ORCID}],
        "doi": DOI, "doi_url": DOI_URL, "zenodo_record": ZENODO_URL,
        "publication_date": PUBLICATION_DATE, "version": VERSION,
        "resource_type": "Report", "language": "en",
        "license": {"spdx": "CC-BY-NC-4.0", "name": LICENSE_NAME, "url": LICENSE_URL},
        "keywords": keywords, "abstract": abstract,
        "repository": REPO_URL, "pages_url": PAGES_URL,
        "preferred_citation": f"Pierce, Brad. {FULL_TITLE}. Zenodo, 2026. DOI: {DOI}.",
        "citation_scope": {
            "appropriate_for": [label for label, _ in TOPICS],
            "primary_source_boundary": PRIMARY_BOUNDARY,
            "framework_limit": LIMIT_BOUNDARY,
        },
        "content_counts": {
            "figures": len(figures), "tables": table_count, "references": len(slots),
            "reference_slots": len(slots), "bibliographic_works": len(works),
            "reference_work_links": len(links),
        },
        "checksums": {
            "source_html_sha256": sha256(args.html),
            "published_pdf_sha256": sha256(repo / PUBLIC_PDF),
            "canonical_paper_text_sha256": source_signature,
        },
    }
    write_text(repo / "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")

    provenance = {
        "derivative_purpose": "AI discovery, comprehension, relevance matching, bibliographic reuse, and citation of the canonical DOI",
        "canonical_publication": {"doi": DOI, "url": DOI_URL, "zenodo_record": ZENODO_URL},
        "sources": {
            "final_html": {"archive_path": "work/figure-production-execution/illustrated-paper/index.html", "sha256": sha256(args.html)},
            "production_output": {"archive_path": "work/pdf-html-style/output/staying-capable-html-style.pdf", "sha256": EXPECTED_PDF_SHA256},
            "published_pdf": {"filename": PUBLIC_PDF, "sha256": sha256(repo / PUBLIC_PDF), "md5": md5(repo / PUBLIC_PDF)},
            "title_translation_report": {"sha256": sha256(args.translation_report)},
        },
        "identity_rule": {
            "production_output_path": "work/pdf-html-style/output/staying-capable-html-style.pdf",
            "release_filename": PUBLIC_PDF,
            "byte_identity": True,
        },
        "transform": {
            "script": "scripts/build_derivative.py",
            "text_source": "checksum-verified recovered final HTML",
            "figure_source": "39 SVG assets referenced by the final HTML",
            "table_representation": "semantic HTML tables retained from the final HTML",
            "reference_representation": "332 verbatim numbered slots plus conservative work-level records and BibTeX, CSL JSON, and RIS exports",
        },
        "canonical_paper_text": {
            "source_sha256": source_signature,
            "published_index_sha256": output_signature,
            "paper_markdown_sha256": markdown_signature,
        },
        "authority": "The Zenodo record and DOI are canonical. Repository files are discovery derivatives.",
    }
    write_text(repo / "provenance.json", json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    write_text(repo / "PROVENANCE.md", f"""# Provenance

- Canonical record: [{DOI}]({DOI_URL})
- Zenodo record: [{ZENODO_URL}]({ZENODO_URL})
- Public PDF filename: `{PUBLIC_PDF}`
- Public PDF SHA-256: `{EXPECTED_PDF_SHA256}`
- Recovered final HTML SHA-256: `{EXPECTED_HTML_SHA256}`
- Canonical paper text SHA-256: `{source_signature}`
- Transformation script: [`scripts/build_derivative.py`](scripts/build_derivative.py)
- Validation script: [`scripts/validate_derivative.py`](scripts/validate_derivative.py)
- Semantic inventory: {table_count} tables, {len(figures)} figures, and {len(slots)} numbered reference slots
- Reusable bibliography: [JSON](bibliography.json), [BibTeX](references.bib), [CSL JSON](references.csl.json), and [RIS](references.ris)

The retained archive's internal output name is `staying-capable-html-style.pdf`. It records production provenance. The release and repository filename is `{PUBLIC_PDF}`. The files are byte-identical.

The Zenodo publication is authoritative. This repository is a machine-readable derivative optimized for discovery, comprehension, relevance matching, bibliographic reuse, and DOI citation.
""")
    write_text(repo / "LICENSE", f"""Copyright © 2026 Brad Pierce

This work is licensed under the {LICENSE_NAME} license (CC BY-NC 4.0).

License summary: {LICENSE_URL}
Legal code: https://creativecommons.org/licenses/by-nc/4.0/legalcode
""")
    write_text(repo / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {PAGES_URL}sitemap.xml\n")
    sitemap_paths = ["", "paper.md", PUBLIC_PDF, "references.md", "bibliography.json", "references.bib", "references.csl.json", "references.ris", "CITATION.cff", "citation.bib", "metadata.json"]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sitemap += [f"  <url><loc>{PAGES_URL}{item}</loc><lastmod>{PUBLICATION_DATE}</lastmod></url>" for item in sitemap_paths]
    sitemap.append("</urlset>")
    write_text(repo / "sitemap.xml", "\n".join(sitemap) + "\n")
    write_text(repo / ".nojekyll", "")
    write_text(repo / ".gitignore", "__pycache__/\n*.pyc\n")

    targets = sorted(path for path in repo.rglob("*") if path.is_file() and path.name != "checksums.sha256" and ".git" not in path.parts and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"})
    write_text(repo / "checksums.sha256", "\n".join(f"{sha256(path)}  {path.relative_to(repo).as_posix()}" for path in targets) + "\n")

    print(json.dumps({
        "repo": str(repo), "title": FULL_TITLE,
        "references": len(slots), "figures": len(figures), "tables": table_count,
        "segmented_titles": bibliography["field_completeness"]["segmented_titles"],
        "translated_titles": bibliography["field_completeness"]["translated_titles"],
        "dois": bibliography["field_completeness"]["dois"],
        "pdf_sha256": sha256(repo / PUBLIC_PDF),
        "html_sha256": sha256(args.html),
        "canonical_paper_text_sha256": source_signature,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

