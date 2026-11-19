"""Pruebas iniciales del repositorio, NO del rendimiento ni correctitud de SAD."""

from inspect import signature
from pathlib import Path
import json

from src.stereo.sad import compute_sad


ROOT = Path(__file__).resolve().parents[1]


def test_contract_signature():
    assert list(signature(compute_sad).parameters) == [
        "left_gray", "right_gray", "window_size", "d_min", "d_max"
    ]


def test_experiment_example_is_valid_json():
    cfg = json.loads((ROOT / "configs" / "experimento.example.json").read_text(encoding="utf-8"))
    assert cfg["repetitions"] >= 5
    assert len(cfg["resolutions"]) >= 2
    assert all(k > 0 and k % 2 == 1 for k in cfg["window_sizes"])
    assert len(cfg["d_max_values"]) >= 2


def test_project_has_three_architectures():
    for module in [
        "src/stereo/sad.py",
        "src/parallel/multiprocess.py",
        "src/distributed/master.py",
        "src/distributed/worker.py",
    ]:
        assert (ROOT / module).is_file()
