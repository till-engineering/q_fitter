"""Command line: python main.py - all settings come from config.yaml.

    python main.py            run (read -> pore models -> stress -> fits -> ergebnisse/)
    python main.py methods    list all available methods
"""

import sys

from q_fitter.core.pipeline import run
from q_fitter.core.registry import available


def main() -> int:
    if sys.argv[1:] == ["methods"]:
        for kind, methods in available().items():
            print(kind)
            for name, description in methods:
                print(f"  {name:18s} {description}")
        return 0
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
