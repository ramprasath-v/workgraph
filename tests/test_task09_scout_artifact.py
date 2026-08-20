import hashlib
import json
from pathlib import Path

from scout.schema import load_scout_handoff


REPO_ROOT = Path(__file__).resolve().parents[1]
SCOUT_PATH = (
    REPO_ROOT
    / "scout_handoffs"
    / "scout_ed6739707d4474f82577cd4d5da3c82b.json"
)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and ".pytest_cache" not in path.parts
        ):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_task09_scout_artifact_has_expected_provenance_and_metrics():
    handoff = load_scout_handoff(SCOUT_PATH)

    assert handoff.scout_handoff_id == "scout_ed6739707d4474f82577cd4d5da3c82b"
    assert handoff.task_id == "task09_role_changes"
    assert handoff.producer_provider == "vertex"
    assert handoff.producer_model == "gemini-2.5-flash"
    assert handoff.files_inspected == [
        "membership_registry.py",
        "role_index.py",
        "test_role_index.py",
    ]
    assert handoff.tool_calls == 5
    assert handoff.input_tokens == 9525
    assert handoff.output_tokens == 570
    assert handoff.total_tokens == 12188
    assert handoff.elapsed_seconds == 22.421151


def test_task09_scout_contains_no_historical_or_disallowed_material():
    data = json.loads(SCOUT_PATH.read_text(encoding="utf-8"))
    rendered = json.dumps(data, sort_keys=True).lower()

    for forbidden in (
        "task08",
        "catalog",
        "product",
        "task05",
        "identifier normalization",
        "qwen",
        "baseline",
        "transfer_6b80",
        "transfer_56c07",
        "analysis_contract",
        "relevant_source_files",
        "allowed_output_files",
        "--- a/",
        "+++ b/",
        "@@ -",
        "```",
    ):
        assert forbidden not in rendered


def test_task09_and_compact_scout_freezes_hold():
    assert _tree_hash(REPO_ROOT / "tasks" / "task09_role_changes") == (
        "c46bfd946da1242b031af87c3419686022ed43560d261bd15733a6ad7c33b437"
    )
    assert _tree_hash(REPO_ROOT / "compact_scouts") == (
        "4a338d750d9354e93dfc0b3c0c4a7c8345406cc87438793f0259504d223fcfd1"
    )
    task09_compact = []
    for path in (REPO_ROOT / "compact_scouts").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("task_id") == "task09_role_changes":
            task09_compact.append(path)
    assert task09_compact == []


def test_task09_scout_file_sha256_is_frozen():
    assert hashlib.sha256(SCOUT_PATH.read_bytes()).hexdigest() == (
        "ec38b8443bcc5eaaec4ef8b71c673b29e10a9280d68fe8a01f2967c245869791"
    )
