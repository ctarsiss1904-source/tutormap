import sys
from pathlib import Path

sys.path = [path for path in sys.path if ".vercel_python_packages" not in path]

from generator.builder import Builder


def main():
    project_root = Path(__file__).resolve().parent
    filepath = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else None
    if filepath and not filepath.is_absolute():
        filepath = project_root / filepath

    builder = Builder(filepath=filepath, project_root=project_root)
    builder.build()


if __name__ == "__main__":
    main()
