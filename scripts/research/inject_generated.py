"""Injiser innholdet i docs/research/_generated/*.md i kilde-doc-filer.

Søker etter blokker på formen

    <!-- BEGIN GENERATED: <navn> -->
    ... innhold som overskrives ...
    <!-- END GENERATED -->

i alle docs/research/*.md, og bytter ut innholdet med fila
docs/research/_generated/<navn>.md. Blokkmarkørene beholdes.

Idempotent: kjøres på nytt uten endring hvis _generated-fila ikke har endret seg.
Brukes av `just verify-all`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
RESEARCH_DIR: Final[Path] = ROOT / "docs" / "research"
GENERATED_DIR: Final[Path] = RESEARCH_DIR / "_generated"

# Blokkmarkørene. (?ms) = multiline + dotall.
# body fanger alt mellom BEGIN-linjen og END-linjen, eksklusiv markørlinjene.
BLOCK_RE: Final[re.Pattern] = re.compile(
    r"(?ms)(?P<begin><!-- BEGIN GENERATED: (?P<name>[\w\-]+) -->)\n"
    r"(?P<body>.*?)"
    r"(?P<end><!-- END GENERATED -->)"
)


def inject_one(md_path: Path) -> list[str]:
    """Oppdater alle blokker i én Markdown-fil. Returner liste over endrede block-navn."""
    text = md_path.read_text()
    changed: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        gen_file = GENERATED_DIR / f"{name}.md"
        if not gen_file.exists():
            print(f"  ! {md_path.name}: mangler {gen_file.relative_to(ROOT)}", file=sys.stderr)
            return match.group(0)
        new_body = gen_file.read_text().rstrip("\n") + "\n"
        old_body = match.group("body").rstrip("\n") + "\n" if match.group("body").strip() else ""
        if old_body.strip() != new_body.strip():
            changed.append(name)
        return match.group("begin") + "\n" + new_body + match.group("end")

    new_text = BLOCK_RE.sub(replace, text)
    if new_text != text:
        md_path.write_text(new_text)
    return changed


def main() -> int:
    if not GENERATED_DIR.exists():
        print(f"Ingen {GENERATED_DIR.relative_to(ROOT)}/-mappe — har du kjørt verify-scriptene?",
              file=sys.stderr)
        return 1

    total_changed = 0
    for md in sorted(RESEARCH_DIR.glob("*.md")):
        if md.name.startswith("_"):
            continue
        changed = inject_one(md)
        if changed:
            print(f"  ↻ {md.relative_to(ROOT)}: {', '.join(changed)}")
            total_changed += len(changed)

    if total_changed == 0:
        print("Ingen GENERATED-blokker endret — alle docs er allerede synkende.")
    else:
        print(f"Oppdaterte {total_changed} blokk(er).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
