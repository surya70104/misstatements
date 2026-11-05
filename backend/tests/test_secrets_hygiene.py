"""No secret can reach the repository through the files it tracks (architecture D5)."""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def test_env_example_holds_only_placeholders() -> None:
    text = (BACKEND / ".env.example").read_text(encoding="utf-8")
    urls = re.findall(r"postgresql\+psycopg://\S+", text)
    assert len(urls) == 4, urls
    for url in urls:
        password = re.search(r"://[^:/]+:([^@]+)@", url)
        assert password is not None, url
        assert password.group(1) == "CHANGE_ME", url
    # Every credential placeholder in the file, database or service, is the placeholder.
    for line in text.splitlines():
        if "CREDENTIAL=" in line:
            assert line.rstrip().endswith("=CHANGE_ME"), line


def test_env_example_names_only_this_modules_databases_and_roles() -> None:
    text = (BACKEND / ".env.example").read_text(encoding="utf-8")
    for other in ("oak_spine", "oak_binder", "oak_owner", "oak_app", "oak_binder_"):
        assert not re.search(rf"\b{other}\b", text), other


def test_git_ignores_every_env_file_but_the_example() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored
    assert ".env.*" in ignored
    assert "!.env.example" in ignored
    assert not (BACKEND / ".env").exists() or ".env" in ignored
