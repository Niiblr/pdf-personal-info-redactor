#!/usr/bin/env python3
"""
PDF PII Redactor
────────────────
Two redaction modes, usable together or separately:

  1. EXACT MATCH (--pii / pii.txt)
     Searches every page for the strings you provide and redacts every
     occurrence. Fast, precise, no AI needed.

  2. AI HEADER SCAN (--ai)
     Asks Ollama to identify PII in the top portion of page 1.
     Useful for catching things you forgot to list.

Both modes can run in the same pass.

Requirements:
  pip install pymupdf ollama

Usage examples:
  # Exact strings only (no AI)
  python redact.py --pii "John Smith" "123 Main Street" "SW1A 1AA"

  # Read strings from pii.txt (one per line)  ← recommended for bulk use
  python redact.py

  # AI scan only (no predefined strings)
  python redact.py --ai --no-pii-file

  # Both together
  python redact.py --ai

  # Different model, scan more of the page for AI mode
  python redact.py --ai --model llama3.2 --fraction 0.45
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    sys.exit("❌  PyMuPDF not found. Run: pip install pymupdf")

# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_MODEL   = "llama3.2"
INPUT_DIR       = Path("./input")
OUTPUT_DIR      = Path("./output")
PII_FILE        = Path("./pii.txt")   # one string per line, UTF-8
HEADER_FRACTION = 0.30                # for AI mode: top 30% of page 1

# ── Exact-string redaction ─────────────────────────────────────────────────────

def load_pii_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]

def redact_exact(doc: fitz.Document, terms: list[str]) -> int:
    """
    Search every page for each term and add a redaction annotation.
    Returns total number of hits across all pages.
    """
    if not terms:
        return 0

    total = 0
    for page in doc:
        hits_this_page = 0
        for term in terms:
            rects = page.search_for(term, quads=False)
            for rect in rects:
                expanded = rect + (-1, -1, 1, 1)
                page.add_redact_annot(expanded, fill=(1, 1, 1))
                hits_this_page += 1
                total += 1
        if hits_this_page:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    return total

# ── AI header scan ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a PII detection system for financial documents.
You will receive a list of text blocks extracted from a document header.
Your job: identify which blocks contain personal information such as:
  - Full name or partial name
  - Street address, city, state, zip / postcode
  - Account holder identifier
  - Customer / client reference
  - Email address or phone number

Respond ONLY with a valid JSON array of the integer indices that contain PII.
Examples:  [0, 2]   [1]   []
Do not include any explanation, markdown, or extra text.\
"""

def get_header_blocks(page: fitz.Page, fraction: float) -> list[tuple]:
    clip = fitz.Rect(0, 0, page.rect.width, page.rect.height * fraction)
    raw  = page.get_text("blocks", clip=clip, sort=True)
    return [
        (fitz.Rect(b[:4]), b[4].strip())
        for b in raw
        if b[6] == 0 and b[4].strip()
    ]

def identify_pii_ai(blocks: list[tuple], model: str) -> list[int]:
    try:
        import ollama
    except ImportError:
        sys.exit("❌  ollama not found. Run: pip install ollama")

    if not blocks:
        return []

    payload = [{"index": i, "text": text} for i, (_, text) in enumerate(blocks)]

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(payload, ensure_ascii=False)},
            ],
            options={"temperature": 0},
        )
    except Exception as e:
        print(f"    ⚠  Ollama error: {e}")
        return []

    raw = response["message"]["content"].strip()
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end <= start:
        print(f"    ⚠  Could not parse model response: {raw[:120]}")
        return []

    try:
        indices = json.loads(raw[start:end])
        return [i for i in indices if isinstance(i, int) and 0 <= i < len(blocks)]
    except json.JSONDecodeError as e:
        print(f"    ⚠  JSON parse error ({e}): {raw[start:end][:120]}")
        return []

def redact_ai(doc: fitz.Document, model: str, fraction: float) -> int:
    page   = doc[0]
    blocks = get_header_blocks(page, fraction)

    if not blocks:
        print(f"  AI scan: no text blocks in top {int(fraction*100)}% — skipping")
        return 0

    print(f"  AI scan: {len(blocks)} block(s) in header, asking {model}…")
    pii_indices = identify_pii_ai(blocks, model)

    if not pii_indices:
        print("  AI scan: no additional PII detected")
        return 0

    print(f"  AI scan: redacting {len(pii_indices)} block(s)")
    for idx in pii_indices:
        rect, text = blocks[idx]
        print(f"    → \"{text[:60]}\"")
        expanded = rect + (-1, -1, 1, 1)
        page.add_redact_annot(expanded, fill=(1, 1, 1))

    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    return len(pii_indices)

# ── PDF processing ─────────────────────────────────────────────────────────────

def process_pdf(src: Path, dst: Path, terms: list[str], use_ai: bool,
                model: str, fraction: float) -> bool:
    try:
        doc = fitz.open(src)
    except Exception as e:
        print(f"  ❌  Could not open: {e}")
        return False

    total = 0

    # ── Mode 1: exact string matching ──────────────────────────────────────────
    if terms:
        hits = redact_exact(doc, terms)
        if hits:
            print(f"  Exact match: {hits} occurrence(s) redacted across all pages")
        else:
            print("  Exact match: no occurrences found")
        total += hits

    # ── Mode 2: AI header scan ─────────────────────────────────────────────────
    if use_ai:
        hits = redact_ai(doc, model, fraction)
        total += hits

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc.save(str(dst), garbage=4, deflate=True, clean=True)
    except Exception as e:
        print(f"  ❌  Save failed: {e}")
        doc.close()
        return False

    doc.close()
    print(f"  ✅  Saved → {dst}  ({total} redaction(s) total)")
    return True

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Bulk PDF PII redactor — exact match and/or AI header scan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python redact.py                              # reads pii.txt automatically
  python redact.py --pii "Jane Doe" "45 Oak Ln"
  python redact.py --ai                         # AI on top of pii.txt
  python redact.py --ai --no-pii-file           # AI only, ignore pii.txt
  python redact.py --pii "Jane Doe" --ai        # both: specific strings + AI
""")
    parser.add_argument("--pii",        nargs="+", metavar="STRING",
                        help="One or more strings to redact (exact match, all pages)")
    parser.add_argument("--ai",         action="store_true",
                        help="Also run AI detection on the page-1 header")
    parser.add_argument("--no-pii-file", action="store_true",
                        help="Ignore pii.txt even if it exists")
    parser.add_argument("--model",      default=DEFAULT_MODEL,
                        help="Ollama model for AI mode (default: llama3.2)")
    parser.add_argument("--fraction",   default=HEADER_FRACTION, type=float,
                        help="Page fraction for AI header scan (default: 0.30)")
    parser.add_argument("--input",      default=str(INPUT_DIR))
    parser.add_argument("--output",     default=str(OUTPUT_DIR))
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build list of exact terms
    terms = list(args.pii) if args.pii else []
    if not args.no_pii_file:
        file_terms = load_pii_file(PII_FILE)
        if file_terms:
            terms = list(dict.fromkeys(terms + file_terms))  # deduplicate, preserve order

    if not terms and not args.ai:
        print("Nothing to do — provide --pii strings, a pii.txt file, or use --ai")
        print("Run with --help for usage examples.")
        sys.exit(1)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}/")
        return

    # Summary
    print(f"Input  : {input_dir.resolve()}")
    print(f"Output : {output_dir.resolve()}")
    print(f"Files  : {len(pdfs)}")
    if terms:
        print(f"Strings: {len(terms)} term(s) to redact")
        for t in terms:
            print(f"  • {t}")
    if args.ai:
        print(f"AI scan: enabled ({args.model}, top {int(args.fraction*100)}% of page 1)")
    print("─" * 60)

    ok = fail = 0
    for pdf in pdfs:
        print(f"\n📄  {pdf.name}")
        out = output_dir / pdf.name
        if process_pdf(pdf, out, terms, args.ai, args.model, args.fraction):
            ok += 1
        else:
            fail += 1

    print("\n" + "─" * 60)
    print(f"Done — {ok} succeeded, {fail} failed.")

if __name__ == "__main__":
    main()