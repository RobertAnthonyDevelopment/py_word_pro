import json
import os
import tempfile
from collections.abc import Callable


def normalize_output_path(path: str | None, default_extension: str = "") -> str:
    target = str(path or "").strip()
    if not target:
        raise ValueError("No output file selected.")

    ext = str(default_extension or "").strip()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    if ext and not os.path.splitext(target)[1]:
        target = f"{target}{ext}"
    return target


def atomic_write_file(
    path: str | None,
    writer: Callable[[str], None],
    *,
    suffix: str | None = None,
    default_extension: str = "",
) -> str:
    target_path = normalize_output_path(path, default_extension=default_extension)
    output_dir = os.path.dirname(os.path.abspath(target_path)) or os.getcwd()
    os.makedirs(output_dir, exist_ok=True)

    tmp_suffix = suffix or os.path.splitext(target_path)[1] or ".tmp"
    fd, tmp_path = tempfile.mkstemp(prefix=".pyword-", suffix=tmp_suffix, dir=output_dir)
    os.close(fd)
    try:
        writer(tmp_path)
        os.replace(tmp_path, target_path)
        return target_path
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def atomic_write_text(
    path: str | None,
    content: str,
    *,
    default_extension: str = "",
    encoding: str = "utf-8",
    newline: str = "",
) -> str:
    def _write(tmp_path: str):
        with open(tmp_path, "w", encoding=encoding, newline=newline) as handle:
            handle.write(content)

    return atomic_write_file(path, _write, default_extension=default_extension)


def atomic_write_json(
    path: str | None,
    payload: dict,
    *,
    default_extension: str = ".json",
    ensure_ascii: bool = False,
    indent: int = 2,
) -> str:
    def _write(tmp_path: str):
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=ensure_ascii, indent=indent)

    return atomic_write_file(path, _write, default_extension=default_extension, suffix=".json")
