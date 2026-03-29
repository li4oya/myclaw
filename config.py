import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

PACKAGE_DIR = Path(__file__).resolve().parent
WORKDIR = PACKAGE_DIR.parent

STATE_DIR = WORKDIR / ".myclaw"
PLANS_DIR = STATE_DIR / "plans"
TASKS_DIR = STATE_DIR / "tasks"
TRANSCRIPTS_DIR = STATE_DIR / "transcripts"
EVOLUTION_DIR = STATE_DIR / "evolution"

SKILL_SOURCE_DIR = WORKDIR / "skill_for_claw"
SKILLS_DIR = PACKAGE_DIR / "skills"

MODEL = os.environ["MODEL_ID"]
CLIENT = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))

MAX_TOOL_OUTPUT = 50000
DEFAULT_COMMAND_TIMEOUT = 120
BACKGROUND_COMMAND_TIMEOUT = 300
AUTO_COMPACT_THRESHOLD = 50000
KEEP_RECENT_TOOL_RESULTS = 3
MAX_SUBAGENT_TURNS = 24
MAX_REPAIR_ITERATIONS = 5
MAX_PARALLEL_SUBAGENTS = 4
SAME_FAILURE_THRESHOLD = 2


def ensure_runtime_dirs():
    for directory in (STATE_DIR, PLANS_DIR, TASKS_DIR, TRANSCRIPTS_DIR, EVOLUTION_DIR, SKILLS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
