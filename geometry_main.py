"""Geometry check (standalone): puts the sample frames of all fracture surfaces (Fatigue_crack_labeler)
and all sections (Pore_Detection) of every ID side by side in absolute units (µm) and relative
(xi, zeta), with the deviations and the error of the crack positions – the q fitter works in
relative coordinates, so the geometries of an ID must match. Explanation: GEOMETRIE.md.
All settings: config.yaml (input, geometry). Start: .venv\Scripts\python geometry_main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from q_fitter.data import load_config
from q_fitter.geometry import load_geometry
from q_fitter.geometry_view import GeometryWindow


def main() -> int:
    config = load_config()
    geometries = load_geometry(config)
    app = QApplication(sys.argv)
    window = GeometryWindow(geometries, config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
