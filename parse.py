#!/usr/bin/env python3
"""Parse MIT Science Bowl round PDFs into structured JSON.

One-shot: `python parse.py` reads pdfs/*.pdf -> data/questions.json.
Keeps only Chemistry / Biology / Math (David's subjects).

ponytail: pdftotext loses superscripts/fractions (16^16 -> "1616"); the
questions' own "(read: ...)" glosses recover the meaning, so we accept it.
Upgrade path if math notation matters: re-extract math rounds with pymupdf
span font-sizes to detect superscripts.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "pdfs"
OUT = ROOT / "data" / "questions.json"

KEEP = {"MATH", "CHEMISTRY", "BIOLOGY"}
# all categories, so we correctly detect question boundaries before filtering
CATEGORIES = ["EARTH AND SPACE", "GENERAL SCIENCE", "BIOLOGY", "CHEMISTRY",
              "PHYSICS", "MATH", "ENERGY"]
CAT_ALT = "|".join(CATEGORIES)

# N) CATEGORY [– | -] (Multiple Choice|Short Answer) rest...
Q_START = re.compile(
    rf"^\s*(\d+)\)\s*({CAT_ALT})\s*[–\-]?\s*(Multiple Choice|Short Answer)\b(.*)$"
)
CHOICE = re.compile(r"^\s*([WXYZ])\)\s*(.*)$")
ANSWER = re.compile(r"^\s*ANSWER:\s*(.*)$", re.I)
TOSSUP = re.compile(r"TOSS\s*-?\s*UP", re.I)
BONUS = re.compile(r"^\s*BONUS\s*$", re.I)
FOOTER = re.compile(r"(Page\s+\d+\s*$|MIT Science Bowl.*Round)", re.I)
YEAR = re.compile(r"(20\d\d)\s+MIT Science Bowl")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_pdf(path: Path):
    txt = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                         capture_output=True, text=True).stdout
    year_m = YEAR.search(txt)
    year = year_m.group(1) if year_m else re.search(r"(20\d\d)", path.name).group(1)
    rnd_m = re.search(r"Round[_ ]?(\d+)", path.name)
    rnd = int(rnd_m.group(1)) if rnd_m else 0

    lines = txt.splitlines()
    kind = "tossup"
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if BONUS.match(line):
            kind = "bonus"; i += 1; continue
        if TOSSUP.search(line) and len(line.strip()) < 20:
            kind = "tossup"; i += 1; continue
        m = Q_START.match(line)
        if not m:
            i += 1; continue

        num, cat, qtype, first = m.groups()
        qlines = [first]
        choices = {}
        answer = None
        i += 1
        # consume until ANSWER
        while i < len(lines):
            ln = lines[i]
            if FOOTER.search(ln) or not ln.strip():
                i += 1; continue
            am = ANSWER.match(ln)
            if am:
                answer = am.group(1)
                i += 1
                # answer may wrap to next non-empty, non-structural line
                while i < len(lines):
                    nx = lines[i]
                    if (not nx.strip() or FOOTER.search(nx) or BONUS.match(nx)
                            or TOSSUP.search(nx) or Q_START.match(nx)):
                        break
                    answer += " " + nx.strip()
                    i += 1
                break
            cm = CHOICE.match(ln)
            if cm:
                choices[cm.group(1)] = clean(cm.group(2))
                i += 1; continue
            # another question started without an answer (malformed) -> bail
            if Q_START.match(ln) or BONUS.match(ln) or TOSSUP.search(ln):
                break
            qlines.append(ln)
            i += 1

        if cat not in KEEP or answer is None:
            continue
        qtext = clean(" ".join(qlines))
        visual = bool(re.search(r"\bis visual\b|shown in the (image|figure)|"
                                r"in the (image|figure|diagram)|the following (image|figure|graph)",
                                qtext, re.I))
        out.append({
            "id": f"{year}-r{rnd}-{kind[0]}{num}",
            "year": int(year),
            "round": rnd,
            "category": cat.title() if cat != "MATH" else "Math",
            "kind": kind,
            "qtype": "mc" if qtype == "Multiple Choice" else "sa",
            "question": qtext,
            "choices": choices,
            "answer": clean(answer),
            "visual": visual,
        })
    return out


def main():
    all_q = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        qs = parse_pdf(pdf)
        all_q.extend(qs)
        print(f"{pdf.name}: {len(qs)} kept", file=sys.stderr)
    # dedup exact repeats and disambiguate id collisions (pdftotext can double-parse
    # a question, and multi-part "visual bonus" blocks can mis-detect kind -> same id)
    seen, deduped = {}, []
    for q in all_q:
        qid = q["id"]
        if qid not in seen:
            seen[qid] = q["question"]; deduped.append(q)
        elif q["question"] == seen[qid]:
            continue  # exact duplicate
        else:
            k = 2
            while f"{qid}x{k}" in seen:
                k += 1
            q["id"] = f"{qid}x{k}"; seen[q["id"]] = q["question"]; deduped.append(q)
    all_q = deduped

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(all_q, ensure_ascii=False, indent=1))
    from collections import Counter
    by = Counter(q["category"] for q in all_q)
    print(f"\nTOTAL: {len(all_q)}  {dict(by)}", file=sys.stderr)


if __name__ == "__main__":
    main()
