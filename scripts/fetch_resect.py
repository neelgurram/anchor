"""Download only the MRI <-> pre-resection-ultrasound landmark files from RESECT.

RESECT (Xiao et al., Med Phys 2017; DOI 10.11582/2017.00004; CC BY 4.0) is hosted on
the Sigma2 NIRD archive. Every file can be fetched on its own, so we pull the table of
contents, keep the `CaseN-MRI-beforeUS.tag` files (about 1 KB each), and skip the 3.3 GB
of image volumes.

Run:  python scripts/fetch_resect.py
"""
import pathlib
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://data.archive.sigma2.no/dataset/5686d8fa-2003-4837-8e66-8e887fabe21e/download/"
TOC = BASE + "table_of_contents_10.11582_2017.00004.csv"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "resect"
PATTERN = re.compile(r"(Case(\d+))-MRI-beforeUS\.tag$")


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "anchor-hackathon-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    toc = get(TOC).decode("utf-8", errors="replace")
    paths = []
    for line in toc.splitlines():
        for field in line.split("|"):
            field = field.strip()
            if PATTERN.search(field) and "__MACOSX" not in field:
                paths.append(field)
    # Prefer the MINC copy, fall back to NIFTI; one file per case.
    by_case = {}
    for p in sorted(paths, key=lambda s: ("NIFTI" in s, s)):
        case = PATTERN.search(p).group(1)
        by_case.setdefault(case, p)
    print(f"found {len(by_case)} cases with MRI-beforeUS landmarks")
    for case, rel in sorted(by_case.items(), key=lambda kv: int(kv[0][4:])):
        dest = OUT / f"{case}-MRI-beforeUS.tag"
        if dest.exists():
            continue
        data = get(BASE + urllib.parse.quote(rel.lstrip("/")))
        if not data.startswith(b"MNI Tag Point File"):
            print(f"  {case}: unexpected content, skipped")
            continue
        dest.write_bytes(data)
        print(f"  {case}: {len(data)} bytes  <- {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
