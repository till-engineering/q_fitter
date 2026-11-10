"""q fitter: shows the critical pores (Pareto of A g^q) of every section of every ID with one q
slider for all; the crack origins of the Fatigue_crack_labeler are drawn on the samples.
All settings: config.yaml. Start: .venv\\Scripts\\python main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from q_fitter.data import load_all, load_config
from q_fitter.window import Window


def main() -> int:
    config = load_config()
    samples = load_all(config)
    app = QApplication(sys.argv)
    window = Window(samples, config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
