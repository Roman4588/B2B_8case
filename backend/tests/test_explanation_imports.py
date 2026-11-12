"""The API lexical explanation must not load a second ML runtime."""
import subprocess
import sys
from pathlib import Path


def test_lexical_explanation_does_not_import_model_dependencies():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from app.explanations import matched_terms; "
         "assert matched_terms('disk full and the cpu', 'Disk full CPU') == ['cpu', 'disk', 'full']; "
         "assert 'sklearn' not in sys.modules, 'lexical explanation loaded sklearn'; "
         "assert 'scipy' not in sys.modules"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
