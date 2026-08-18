from harness.trajectory import build_trajectory, trajectory_diagnostics


def test_trajectory_uses_executed_actions_without_file_contents():
    secret_source = "API_SECRET = 'must-not-be-persisted'\n" * 100
    history = (
        {
            "action": {"action": "read_file", "path": "app.py"},
            "output": secret_source,
        },
        {
            "action": {
                "action": "write_file",
                "path": "app.py",
                "content": secret_source,
            },
            "output": {"path": "app.py", "bytes_written": len(secret_source)},
        },
        {
            "action": {"action": "run_tests"},
            "output": {
                "returncode": 1,
                "stdout": "1 passed, 3 failed in 0.1s",
                "stderr": "",
            },
        },
    )

    trajectory = build_trajectory(history)

    assert [entry["action"] for entry in trajectory] == [
        "read_file",
        "write_file",
        "run_tests",
    ]
    assert trajectory[0]["target"] == "app.py"
    assert trajectory[2]["outcome"] == "1 passed / 3 failed"
    assert "must-not-be-persisted" not in str(trajectory)


def test_repetition_and_action_diagnostics():
    trajectory = build_trajectory(
        [
            {"action": {"action": "read_file", "path": "app.py"}, "output": "x"},
            {"action": {"action": "read_file", "path": "app.py"}, "output": "x"},
            {"action": {"action": "read_file", "path": "app.py"}, "output": "x"},
            {"action": {"action": "write_file", "path": "app.py", "content": "x"}, "output": {}},
            {"action": {"action": "run_tests"}, "output": {"returncode": 0, "stdout": "1 passed", "stderr": ""}},
            {"action": {"action": "run_tests"}, "output": {"returncode": 0, "stdout": "1 passed", "stderr": ""}},
        ]
    )

    diagnostics = trajectory_diagnostics(trajectory)

    assert diagnostics == {
        "unique_actions": 3,
        "repeated_identical_actions": 3,
        "test_runs": 2,
        "file_reads": 3,
        "file_writes": 1,
        "most_repeated_action": {
            "action": "read_file",
            "target": "app.py",
            "count": 3,
        },
    }
