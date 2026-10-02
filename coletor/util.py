# -*- coding: utf-8 -*-
"""Log e leitura/gravação de CSV."""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def gravar_csv(caminho: Path, campos: list[str], linhas: list[dict]) -> None:
    """Grava em UTF-8 com quebras LF, via arquivo temporário + rename (atômico)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    os.replace(tmp, caminho)
