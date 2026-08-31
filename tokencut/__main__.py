"""Enable `python -m tokencut <command>` (mirrors `python -m tokencut.cli`)."""
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
