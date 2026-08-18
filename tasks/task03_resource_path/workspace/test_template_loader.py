from template_loader import load_template, template_category, template_name


def test_template_loads_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    template = load_template()
    assert template["name"] == "weekly-summary"
    assert template["fields"] == ["title", "owner", "status"]


def test_template_name_is_stable_outside_project_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert template_name() == "weekly-summary"


def test_template_category_is_stable_outside_project_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert template_category() == "report"


def test_bundled_template_has_required_fields():
    assert set(load_template()["fields"]) == {"title", "owner", "status"}
