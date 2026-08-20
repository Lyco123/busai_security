import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W_NS, "r": R_NS}

BULLET_FMTS = {
    "bullet",
    "none",
    "hyphen",
}

ORDERED_FMTS = {
    "decimal",
    "decimalZero",
    "upperRoman",
    "lowerRoman",
    "upperLetter",
    "lowerLetter",
    "ordinal",
    "cardinalText",
    "ordinalText",
    "chicago",
}


def read_xml(zf, name):
    try:
        return ET.fromstring(zf.read(name))
    except KeyError:
        return None


def is_on(el):
    if el is None:
        return False
    val = el.get(f"{{{W_NS}}}val")
    if val is None:
        return True
    return val not in {"0", "false", "False"}


def build_numbering_map(numbering_root):
    if numbering_root is None:
        return {}
    abstract_map = {}
    for abs_num in numbering_root.findall("w:abstractNum", NS):
        abs_id = abs_num.get(f"{{{W_NS}}}abstractNumId")
        lvl_map = {}
        for lvl in abs_num.findall("w:lvl", NS):
            ilvl = lvl.get(f"{{{W_NS}}}ilvl")
            num_fmt = lvl.find("w:numFmt", NS)
            fmt = num_fmt.get(f"{{{W_NS}}}val") if num_fmt is not None else "bullet"
            lvl_map[ilvl] = fmt
        abstract_map[abs_id] = lvl_map

    num_map = {}
    for num in numbering_root.findall("w:num", NS):
        num_id = num.get(f"{{{W_NS}}}numId")
        abs_id_el = num.find("w:abstractNumId", NS)
        abs_id = abs_id_el.get(f"{{{W_NS}}}val") if abs_id_el is not None else None
        lvl_map = abstract_map.get(abs_id, {})
        for ilvl, fmt in lvl_map.items():
            num_map[(num_id, ilvl)] = fmt
    return num_map


def build_rels_map(rels_root):
    if rels_root is None:
        return {}
    rels = {}
    for rel in rels_root.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rel_id = rel.get("Id")
        target = rel.get("Target")
        rels[rel_id] = target
    return rels


def run_text(run):
    parts = []
    for node in run:
        tag = node.tag
        if tag == f"{{{W_NS}}}t":
            parts.append(node.text or "")
        elif tag == f"{{{W_NS}}}tab":
            parts.append("\t")
        elif tag in {f"{{{W_NS}}}br", f"{{{W_NS}}}cr"}:
            parts.append("\n")
    return "".join(parts)


def iter_runs(node):
    for child in node:
        if child.tag == f"{{{W_NS}}}del":
            # Skip deleted content.
            continue
        if child.tag == f"{{{W_NS}}}r":
            yield child
        else:
            yield from iter_runs(child)


def inline_text(p, rels_map):
    parts = []
    for run in iter_runs(p):
        rpr = run.find("w:rPr", NS)
        bold = is_on(rpr.find("w:b", NS)) if rpr is not None else False
        italic = is_on(rpr.find("w:i", NS)) if rpr is not None else False
        text = run_text(run)
        if not text:
            continue
        if bold and italic:
            text = f"***{text}***"
        elif bold:
            text = f"**{text}**"
        elif italic:
            text = f"*{text}*"
        parts.append(text)
    text = "".join(parts)
    text = text.replace("\t", "    ")
    text = text.replace("\n", "<br>")
    return text


def paragraph_to_md(p, num_map, rels_map):
    text = inline_text(p, rels_map).strip()
    if not text:
        return "", False

    num_pr = p.find("w:pPr/w:numPr", NS)
    if num_pr is None:
        return text, False

    ilvl_el = num_pr.find("w:ilvl", NS)
    num_id_el = num_pr.find("w:numId", NS)
    ilvl = ilvl_el.get(f"{{{W_NS}}}val") if ilvl_el is not None else "0"
    num_id = num_id_el.get(f"{{{W_NS}}}val") if num_id_el is not None else "0"

    fmt = num_map.get((num_id, ilvl), "bullet")
    ordered = fmt in ORDERED_FMTS and fmt not in BULLET_FMTS
    prefix = "1. " if ordered else "- "
    try:
        indent = "  " * int(ilvl)
    except ValueError:
        indent = ""
    return f"{indent}{prefix}{text}", True


def cell_text(tc, rels_map):
    paras = []
    for p in tc.findall("w:p", NS):
        text = inline_text(p, rels_map).strip()
        if text:
            paras.append(text)
    return "<br>".join(paras)


def table_to_md(tbl, rels_map):
    rows = []
    for tr in tbl.findall("w:tr", NS):
        cells = [cell_text(tc, rels_map) for tc in tr.findall("w:tc", NS)]
        rows.append(cells)
    if not rows:
        return []
    col_count = max(len(r) for r in rows)
    # Normalize row lengths
    norm_rows = [r + [""] * (col_count - len(r)) for r in rows]
    def esc(cell):
        return (cell or "").replace("|", "\\|")
    lines = []
    header = "| " + " | ".join(esc(c) for c in norm_rows[0]) + " |"
    lines.append(header)
    sep = "| " + " | ".join(["---"] * col_count) + " |"
    lines.append(sep)
    for row in norm_rows[1:]:
        lines.append("| " + " | ".join(esc(c) for c in row) + " |")
    return lines


def docx_to_md(path, out_path):
    with zipfile.ZipFile(path) as zf:
        doc_root = read_xml(zf, "word/document.xml")
        numbering_root = read_xml(zf, "word/numbering.xml")
        rels_root = read_xml(zf, "word/_rels/document.xml.rels")

    if doc_root is None:
        raise RuntimeError(f"Missing word/document.xml in {path}")

    num_map = build_numbering_map(numbering_root)
    rels_map = build_rels_map(rels_root)

    body = doc_root.find("w:body", NS)
    if body is None:
        return ""

    lines = []
    prev_was_list = False
    for child in body:
        if child.tag == f"{{{W_NS}}}p":
            line, is_list = paragraph_to_md(child, num_map, rels_map)
            if not line:
                if prev_was_list:
                    lines.append("")
                    prev_was_list = False
                else:
                    lines.append("")
                continue
            if is_list:
                if not prev_was_list and lines and lines[-1] != "":
                    lines.append("")
                lines.append(line)
                prev_was_list = True
            else:
                if prev_was_list:
                    lines.append("")
                lines.append(line)
                lines.append("")
                prev_was_list = False
        elif child.tag == f"{{{W_NS}}}tbl":
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend(table_to_md(child, rels_map))
            lines.append("")
            prev_was_list = False

    # Clean up excessive blank lines (max 1 in a row)
    cleaned = []
    blank = False
    for line in lines:
        if line.strip() == "":
            if not blank:
                cleaned.append("")
            blank = True
        else:
            cleaned.append(line.rstrip())
            blank = False
    content = "\n".join(cleaned).strip() + "\n"
    out_path.write_text(content, encoding="utf-8")


def main(argv):
    if len(argv) < 2:
        print("Usage: docx_to_md.py <docx_or_dir> [<docx_or_dir> ...]")
        return 2
    paths = []
    for arg in argv[1:]:
        p = Path(arg)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.docx")))
        else:
            paths.append(p)
    if not paths:
        print("No .docx files found.")
        return 1
    for path in paths:
        out_path = path.with_suffix(".md")
        docx_to_md(path, out_path)
        print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
