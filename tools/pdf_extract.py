import sys

if len(sys.argv) > 2:
    sys.stdout = open(sys.argv[2], "w", encoding="utf-8")

try:
    import pdfplumber
    with pdfplumber.open(sys.argv[1]) as pdf:
        print(f"### pages={len(pdf.pages)}")
        for i, page in enumerate(pdf.pages, 1):
            print(f"\n===== PAGE {i} =====")
            print(page.extract_text() or "(no text)")
            for t in page.extract_tables():
                print("--- table ---")
                for row in t:
                    print(" | ".join("" if c is None else str(c).replace("\n", " ") for c in row))
except Exception as e:
    print("pdfplumber failed:", type(e).__name__, e)
    from pypdf import PdfReader
    r = PdfReader(sys.argv[1])
    for i, page in enumerate(r.pages, 1):
        print(f"\n===== PAGE {i} =====")
        print(page.extract_text())
