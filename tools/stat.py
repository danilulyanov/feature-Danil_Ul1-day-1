import os
import sys

EXCLUDE_DIRS = {"__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", ".git"}
ROOTS = ["bot", "alembic", "tools", "tests"]


def collect_files() -> list[str]:
    files: list[str] = []
    for root in ROOTS:
        if not os.path.exists(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for name in filenames:
                if name.endswith(".py"):
                    files.append(os.path.join(dirpath, name))
    if os.path.isfile("main.py"):
        files.append("main.py")
    return files


def main():
    files = collect_files()
    if not files:
        print("0 lines in 0 py-files")
        return

    total_lines = 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for _ in fh:
                    total_lines += 1
        except Exception:
            continue

    print(f"{total_lines} lines in {len(files)} py-files")


if __name__ == "__main__":
    sys.exit(main())
