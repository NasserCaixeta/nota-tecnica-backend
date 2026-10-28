import os
import subprocess
import sys
from pathlib import Path


def test_application_can_start_in_a_fresh_interpreter():
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app; assert app.title"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "APP_ENV": "test"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
