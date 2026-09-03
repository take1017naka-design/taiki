import pytest

from duty_roster.config import ConfigError, load_config, normalize_code, normalize_name

EXAMPLE = "config/roster.example.yaml"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("￣／公", "―/公"),
        ("ＭＥ", "ME"),
        ("ｶﾃ", "カテ"),
        ("有／公", "有/公"),
        ("　公　", "公"),
        ("Ｏ", "O"),
        (None, ""),
    ],
)
def test_normalize_code(raw, expected):
    assert normalize_code(raw) == expected


def test_normalize_name_drops_spaces():
    assert normalize_name("担当A　太郎") == "担当A太郎"


def test_example_config_loads():
    cfg = load_config(EXAMPLE)
    assert len(cfg.members) == 8
    assert cfg.backup_anchor == "担当A"
    assert cfg.weekend_pool == ["担当B", "担当C", "担当D", "担当E", "担当F"]
    assert sum(cfg.quota(31).values()) == 31
    assert cfg.code_aliases["一/公"] == "―/公"


def test_output_path_uses_config(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(
        "members: [A, B]\n"
        "quota_by_month_length:\n  28: {A: 14, B: 14}\n"
        'output: {directory: "%s", filename: "roster-{year}-{month:02d}.xlsx"}\n'
        % tmp_path.as_posix(),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.output_path(2026, 9) == (tmp_path / "roster-2026-09.xlsx").resolve()


def test_output_path_default(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(
        "members: [A, B]\nquota_by_month_length:\n  28: {A: 14, B: 14}\n", encoding="utf-8"
    )
    cfg = load_config(path)
    assert cfg.output_path(2026, 9).name == "待機表_202609.xlsx"


def test_quota_must_sum_to_month_length(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "members: [A, B]\nquota_by_month_length:\n  31: {A: 10, B: 10}\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="合計"):
        load_config(path)


def test_unknown_name_in_roles_is_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "members: [A, B]\n"
        "quota_by_month_length:\n  28: {A: 14, B: 14}\n"
        "roles:\n  backup_anchor: Z\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="未登録"):
        load_config(path)
