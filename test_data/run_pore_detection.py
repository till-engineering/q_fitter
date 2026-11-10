r"""Creates the test input: runs Pore_Detection (its config.yaml) on test_data/source_images/<ID>/
and writes the results to input/pores/. Run with the Python of Pore_Detection:
    E:\Arbeit\Pore_Detection\.venv\Scripts\python test_data\run_pore_detection.py
"""
import sys
from pathlib import Path

PORE_DETECTION = Path(r"E:\Arbeit\Pore_Detection")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(PORE_DETECTION))
from pore_detection import load_config, run  # noqa: E402

config = load_config()
for folder in sorted((HERE / "source_images").iterdir()):
    result = run(config, input_path=folder, output_dir=HERE.parent / "input" / "pores")
    print(folder.name, result.succeeded, "ok", result.failed, "failed", [e.message for e in result.errors])
