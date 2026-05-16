"""
Remove generated files from _report_tests without touching test source files.

Usage:
    python clean_report_tests.py
"""

from __future__ import annotations

from pathlib import Path
import stat
import shutil


REPORT_TESTS_DIR = Path(__file__).resolve().parent / "_report_tests"
GENERATED_FILE_PATTERNS = (
    "*.log",
    "expanded_run.out",
    "expanded_run.err",
    "*.txt",
)
GENERATED_DIR_NAMES = ("__pycache__",)


def main() -> None:
    removed_files = 0
    removed_dirs = 0

    if not REPORT_TESTS_DIR.exists():
        print(f"No cleanup needed: {REPORT_TESTS_DIR} does not exist.")
        return

    for pattern in GENERATED_FILE_PATTERNS:
        for path in REPORT_TESTS_DIR.glob(pattern):
            if path.is_file():
                path.unlink()
                removed_files += 1
                print(f"removed file: {path.relative_to(REPORT_TESTS_DIR.parent)}")

    for dir_name in GENERATED_DIR_NAMES:
        path = REPORT_TESTS_DIR / dir_name
        if path.is_dir():
            try:
                make_tree_writable(path)
                shutil.rmtree(path)
            except OSError as exc:
                print(
                    "could not remove directory "
                    f"{path.relative_to(REPORT_TESTS_DIR.parent)}: {exc}"
                )
            else:
                removed_dirs += 1
                print(f"removed directory: {path.relative_to(REPORT_TESTS_DIR.parent)}")

    print(f"cleanup complete: {removed_files} files, {removed_dirs} directories removed.")


def make_tree_writable(path: Path) -> None:
    for child in path.rglob("*"):
        child.chmod(stat.S_IWRITE)
    path.chmod(stat.S_IWRITE)


if __name__ == "__main__":
    main()
