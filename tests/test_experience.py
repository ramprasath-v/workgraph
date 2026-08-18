import json
from pathlib import Path

from experience.capture import capture_experience, compare_workspaces
from experience.schema import ExperienceRecord, Verification, load_experience


def _workspace_pair(tmp_path: Path) -> tuple[Path, Path]:
    pristine = tmp_path / "pristine"
    active = tmp_path / "active"
    pristine.mkdir()
    active.mkdir()
    return pristine, active


def test_changed_file_detection_and_unified_diff(tmp_path: Path):
    pristine, active = _workspace_pair(tmp_path)
    (pristine / "calculator.py").write_text(
        "def divide(a, b):\n    return a * b\n", encoding="utf-8"
    )
    (active / "calculator.py").write_text(
        "def divide(a, b):\n    return a / b\n", encoding="utf-8"
    )

    changed, patch = compare_workspaces(pristine, active)

    assert changed == ["calculator.py"]
    assert "--- a/calculator.py" in patch
    assert "+++ b/calculator.py" in patch
    assert "-    return a * b" in patch
    assert "+    return a / b" in patch


def test_cache_and_temporary_files_are_ignored(tmp_path: Path):
    pristine, active = _workspace_pair(tmp_path)
    (pristine / "same.py").write_text("same\n", encoding="utf-8")
    (active / "same.py").write_text("same\n", encoding="utf-8")
    (active / "__pycache__").mkdir()
    (active / "__pycache__" / "same.cpython.pyc").write_bytes(b"noise")
    (active / ".pytest_cache").mkdir()
    (active / ".pytest_cache" / "state").write_text("noise", encoding="utf-8")
    (active / "scratch.tmp").write_text("noise", encoding="utf-8")
    (active / "editor.py~").write_text("noise", encoding="utf-8")

    assert compare_workspaces(pristine, active) == ([], "")


def test_experience_json_serialization(tmp_path: Path):
    record = ExperienceRecord(
        experience_id="exp_test",
        task_id="task01_exact",
        producer_model="mock",
        problem="Fix division",
        environment={"language": "python"},
        files_changed=["calculator.py"],
        patch="--- a/calculator.py\n+++ b/calculator.py\n",
        verification=Verification(command=["pytest", "-q"], passed=3, failed=0),
        successful=True,
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        created_at="2026-01-01T00:00:00+00:00",
    )

    output = record.write_json(tmp_path)

    assert json.loads(output.read_text(encoding="utf-8")) == record.to_dict()
    assert output.name == "exp_test.json"
    assert load_experience(output) == record


def test_experience_loading_errors_are_clear(tmp_path: Path):
    missing = tmp_path / "missing.json"
    try:
        load_experience(missing)
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("missing experience was accepted")

    malformed = tmp_path / "malformed.json"
    malformed.write_text("not json", encoding="utf-8")
    try:
        load_experience(malformed)
    except ValueError as exc:
        assert "unable to load experience" in str(exc)
    else:
        raise AssertionError("malformed experience was accepted")


def test_successful_experience_capture(tmp_path: Path):
    pristine, active = _workspace_pair(tmp_path)
    (pristine / "code.py").write_text("value = 1\n", encoding="utf-8")
    (active / "code.py").write_text("value = 2\n", encoding="utf-8")

    captured = capture_experience(
        pristine_workspace=pristine,
        active_workspace=active,
        task_id="task",
        producer_model="mock",
        problem="Fix value",
        environment={"language": "python"},
        verification_command=["pytest", "-q"],
        passed=1,
        failed=0,
        successful=True,
        experiences_dir=tmp_path / "experiences",
        created_at="2026-01-01T00:00:00+00:00",
        experience_id="exp_fixed",
    )

    assert captured is not None
    record, output = captured
    assert record.files_changed == ["code.py"]
    assert record.verification.passed == 1
    assert output.exists()


def test_failed_capture_creates_no_experience(tmp_path: Path):
    pristine, active = _workspace_pair(tmp_path)
    experiences = tmp_path / "experiences"

    captured = capture_experience(
        pristine_workspace=pristine,
        active_workspace=active,
        task_id="task",
        producer_model="mock",
        problem="Still broken",
        environment={"language": "python"},
        verification_command=["pytest", "-q"],
        passed=0,
        failed=1,
        successful=False,
        experiences_dir=experiences,
    )

    assert captured is None
    assert not experiences.exists()
