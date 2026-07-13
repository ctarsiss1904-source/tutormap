import sys

from generator.builder import Builder


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    builder = Builder(filepath)
    builder.build()


if __name__ == "__main__":
    main()
