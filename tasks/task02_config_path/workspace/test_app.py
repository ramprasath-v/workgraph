import json

from app import load_settings, retry_limit, service_label


def test_default_settings_load_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings()
    assert settings["service_name"] == "experience-lab"
    assert settings["features"]["audit_log"] is True


def test_service_label_is_stable_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert service_label() == "experience-lab:benchmark"


def test_retry_limit_is_available_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert retry_limit() == 3


def test_explicit_configuration_path_is_preserved(tmp_path):
    custom = tmp_path / "custom-settings.json"
    custom.write_text(
        json.dumps(
            {
                "service_name": "custom",
                "environment": "test",
                "retry_limit": 1,
            }
        ),
        encoding="utf-8",
    )
    assert load_settings(custom)["service_name"] == "custom"
