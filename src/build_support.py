from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_MODULE_PACKAGES = ("PIL", "lxml", "PyInstaller")
MACH_O_SUFFIXES = (".so", ".dylib")
MACH_O_MAGICS = (
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
)


@dataclass(frozen=True)
class BinaryArchIssue:
    path: str
    actual_arches: tuple[str, ...]
    missing_arches: tuple[str, ...]


def required_architectures(target_arch: str | None) -> tuple[str, ...]:
    normalized = (target_arch or "").strip()
    if not normalized:
        return ()
    if normalized == "universal2":
        return ("arm64", "x86_64")
    return (normalized,)


def parse_architecture_output(output: str) -> tuple[str, ...]:
    return tuple(part for part in output.strip().split() if part)


def _resolve_package_root(package_name: str) -> Path | None:
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        return None
    if spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations))).resolve()
    if spec.origin:
        return Path(spec.origin).resolve().parent
    return None


def is_mach_o_binary(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix in MACH_O_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACH_O_MAGICS
    except OSError:
        return False


def iter_binary_candidates(module_packages: Sequence[str] = DEFAULT_MODULE_PACKAGES) -> tuple[Path, ...]:
    paths: dict[str, Path] = {}

    def add(path: Path | str | None) -> None:
        if path is None:
            return
        resolved = Path(path).resolve()
        if not resolved.exists():
            return
        if resolved.is_file() and is_mach_o_binary(resolved):
            paths[str(resolved)] = resolved

    add(sys.executable)

    destshared = sysconfig.get_config_var("DESTSHARED")
    if destshared:
        for candidate in sorted(Path(destshared).glob("*")):
            if candidate.is_file() and candidate.suffix in MACH_O_SUFFIXES:
                add(candidate)

    for package_name in module_packages:
        package_root = _resolve_package_root(package_name)
        if package_root is None or not package_root.exists():
            continue
        for candidate in sorted(package_root.rglob("*")):
            if is_mach_o_binary(candidate):
                add(candidate)

    return tuple(paths.values())


def query_architectures(path: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["lipo", "-archs", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ()
    return parse_architecture_output(result.stdout)


def find_incompatible_binaries(
    paths: Iterable[Path],
    required_arches: Sequence[str],
) -> tuple[BinaryArchIssue, ...]:
    required = tuple(dict.fromkeys(required_arches))
    issues: list[BinaryArchIssue] = []
    for path in paths:
        actual = query_architectures(path)
        missing = tuple(arch for arch in required if arch not in actual)
        if missing:
            issues.append(
                BinaryArchIssue(
                    path=str(path),
                    actual_arches=tuple(actual),
                    missing_arches=missing,
                )
            )
    return tuple(issues)


def build_failure_message(
    target_arch: str,
    module_packages: Sequence[str],
    issues: Sequence[BinaryArchIssue],
) -> str:
    lines = [
        f"Target architecture preflight failed for '{target_arch}'.",
        "The active Python runtime, installed binary wheels, or PyInstaller bootloaders do not match the requested build target.",
        f"Checked module packages: {', '.join(module_packages)}",
        "Examples of incompatible binaries:",
    ]
    for issue in issues[:10]:
        actual = " ".join(issue.actual_arches) if issue.actual_arches else "unreadable"
        missing = " ".join(issue.missing_arches)
        lines.append(f"  - {issue.path} (actual: {actual}; missing: {missing})")
    if len(issues) > 10:
        lines.append(f"  ... and {len(issues) - 10} more")
    lines.extend(
        [
            "Use a Python installation and wheels that match the target architecture.",
            "For universal2 builds, both 'arm64' and 'x86_64' must be present in every checked binary.",
        ]
    )
    return "\n".join(lines)


def run_preflight(
    target_arch: str | None,
    module_packages: Sequence[str] = DEFAULT_MODULE_PACKAGES,
) -> tuple[bool, str]:
    required = required_architectures(target_arch)
    if not required:
        return True, ""
    if sys.platform != "darwin":
        return False, "macOS target builds require running the preflight on macOS."
    if shutil.which("lipo") is None:
        return False, "The 'lipo' tool is required to verify macOS binary architectures."

    paths = iter_binary_candidates(module_packages)
    issues = find_incompatible_binaries(paths, required)
    if issues:
        return False, build_failure_message(target_arch or "", module_packages, issues)
    return True, ""


def _parse_module_packages(raw: str) -> tuple[str, ...]:
    packages = tuple(part.strip() for part in raw.split(",") if part.strip())
    return packages or DEFAULT_MODULE_PACKAGES


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate macOS binary architectures for PyInstaller packaging.")
    parser.add_argument("--target-arch", default="", help="Requested target architecture (e.g. arm64, x86_64, universal2).")
    parser.add_argument(
        "--module-packages",
        default=",".join(DEFAULT_MODULE_PACKAGES),
        help="Comma-separated package names whose binary extensions should be checked.",
    )
    args = parser.parse_args(argv)

    ok, message = run_preflight(
        args.target_arch.strip(),
        _parse_module_packages(args.module_packages),
    )
    if ok:
        if args.target_arch.strip():
            print(f"Target architecture preflight passed for '{args.target_arch.strip()}'.")
        return 0
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
