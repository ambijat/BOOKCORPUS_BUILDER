"""Canonical project paths used by every command.

The defaults are anchored to the repository, never to the caller's working
directory. Every command still accepts explicit paths for external datasets.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_PDF_DIR = DATA_DIR / "input" / "pdfs"
OUTLINE_DIR = DATA_DIR / "work" / "outlines"
OUTPUT_DIR = DATA_DIR / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
RUN_HISTORY_DIR = OUTPUT_DIR / "run_history"
SECTION_DIR = OUTPUT_DIR / "sections"
JSONL_DIR = OUTPUT_DIR / "jsonl"
MANIFEST_DIR = OUTPUT_DIR / "manifests"
ANALYSIS_DIR = OUTPUT_DIR / "analysis"
DEBATE_SCRIPT = PROJECT_ROOT / "assets" / "text" / "debate_cast_script.txt"
AUDIO_DIR = OUTPUT_DIR / "audio"


def ensure_work_dirs() -> None:
    """Create writable work/output directories, but never fabricate inputs."""
    for directory in (
        OUTLINE_DIR,
        SECTION_DIR,
        JSONL_DIR,
        MANIFEST_DIR,
        ANALYSIS_DIR,
        AUDIO_DIR,
        RUNS_DIR,
        RUN_HISTORY_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
