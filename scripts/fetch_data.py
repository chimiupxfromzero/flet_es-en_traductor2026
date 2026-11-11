#!/usr/bin/env python3
"""Download the raw sources used to build the offline assets.

Sources and licenses:
  * FreeDict+WikDict eng-spa (CC BY-SA 3.0) - https://freedict.org/
  * Tatoeba spa/eng sentence exports and spa-eng links (CC BY 2.0 FR)
    - https://tatoeba.org/

Usage:
  python3 scripts/fetch_data.py --dest /tmp/tdata
  python3 scripts/build_assets.py --freedict /tmp/tdata/eng-spa/eng-spa.tei \\
      --tatoeba /tmp/tdata
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import urllib.request
from pathlib import Path

FREEDICT_VERSION = "2025.11.23"
FREEDICT_URL = (
    "https://download.freedict.org/dictionaries/eng-spa/"
    f"{FREEDICT_VERSION}/freedict-eng-spa-{FREEDICT_VERSION}.src.tar.xz"
)

TATOEBA_URLS = {
    "spa_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/spa/spa_sentences.tsv.bz2",
    "eng_sentences.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2",
    "spa-eng_links.tsv.bz2": "https://downloads.tatoeba.org/exports/per_language/spa/spa-eng_links.tsv.bz2",
}


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ya existe: {dest}")
        return
    print(f"  descargando {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as handle:
        total = int(response.headers.get("content-length") or 0)
        read = 0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            handle.write(chunk)
            read += len(chunk)
            if total:
                print(f"\r    {read * 100 // total:3d}%", end="", flush=True)
    print()
    tmp.replace(dest)


def extract_tei(archive: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:xz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".tei"):
                continue
            source = tar.extractfile(member)
            if source is None:
                continue
            target = out_dir / Path(member.name).name
            target.write_bytes(source.read())
            print(f"  extraído: {target}")
            return target
    raise SystemExit(f"No se encontró ningún .tei dentro de {archive}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default="/tmp/tdata", help="Directorio de descarga")
    args = parser.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    print("FreeDict+WikDict eng-spa:")
    archive = dest / "eng-spa.tar.xz"
    download(FREEDICT_URL, archive)
    tei = extract_tei(archive, dest / "eng-spa")

    print("Tatoeba:")
    for name, url in TATOEBA_URLS.items():
        download(url, dest / name)

    print("\nListo. Ahora genera los assets con:")
    print(
        f"  python3 scripts/build_assets.py --freedict {tei} --tatoeba {dest}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
