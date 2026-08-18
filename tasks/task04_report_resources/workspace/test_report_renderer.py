import json

from report_renderer import render_report
from report_renderer.loader import load_render_defaults


def test_bundled_defaults_load_from_workspace_directory():
    defaults = load_render_defaults()
    assert defaults["heading_marker"] == "##"
    assert defaults["status_labels"]["complete"] == "Complete"


def test_default_rendering_after_working_directory_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert render_report("Operations", "complete") == (
        "## Operations\nStatus: Complete\nWorkGraph Report"
    )


def test_default_rendering_from_second_unrelated_directory(tmp_path, monkeypatch):
    unrelated = tmp_path / "jobs" / "daily"
    unrelated.mkdir(parents=True)
    monkeypatch.chdir(unrelated)
    assert render_report("Daily Check") == (
        "## Daily Check\nStatus: Draft\nWorkGraph Report"
    )


def test_explicit_resource_directory_remains_supported(tmp_path, monkeypatch):
    custom_resources = tmp_path / "custom-report-style"
    custom_resources.mkdir()
    (custom_resources / "defaults.json").write_text(
        json.dumps(
            {
                "heading_marker": "**",
                "status_labels": {"approved": "Approved"},
                "footer": "Custom Footer",
            }
        ),
        encoding="utf-8",
    )
    launch_directory = tmp_path / "launch"
    launch_directory.mkdir()
    monkeypatch.chdir(launch_directory)

    assert render_report("Decision", "approved", custom_resources) == (
        "** Decision\nStatus: Approved\nCustom Footer"
    )


def test_existing_default_report_output_is_preserved():
    assert render_report("Quarterly Review") == (
        "## Quarterly Review\nStatus: Draft\nWorkGraph Report"
    )
