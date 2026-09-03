import datetime as dt

import pytest

from duty_roster.config import load_config
from duty_roster.sample import build_sample
from duty_roster.workbook import (
    apply_tint,
    classify_fill_rgb,
    detect_year_month,
    is_red,
    read_schedule,
)

COLORS = {
    "yellow_hue": [38, 70],
    "yellow_min_saturation": 0.35,
    "yellow_min_value": 0.60,
    "red_min_r": 140,
    "red_max_g": 110,
    "red_max_b": 110,
}


@pytest.mark.parametrize(
    ("rgb", "expected"),
    [
        ((255, 255, 0), "yellow"),      # 濃い黄色 → 待機不可
        ((255, 230, 153), "yellow"),    # 明るめの黄色
        ((132, 226, 145), "other"),     # 薄い黄緑 → 無視
        ((191, 191, 191), "other"),     # グレー → 無視
        ((242, 207, 238), "other"),     # 薄紫 → 無視
        ((255, 255, 255), "none"),
        (None, "none"),
    ],
)
def test_classify_fill(rgb, expected):
    assert classify_fill_rgb(rgb, COLORS) == expected


def test_is_red():
    assert is_red((255, 0, 0), COLORS)
    assert not is_red((0, 112, 192), COLORS)   # 青
    assert not is_red((0, 0, 0), COLORS)
    assert not is_red(None, COLORS)


def test_apply_tint_lightens_and_darkens():
    assert apply_tint((25, 107, 36), 0.6) == (132, 226, 145)
    assert apply_tint((255, 255, 255), -0.25) == (191, 191, 191)


def test_read_sample_schedule(tmp_path):
    path = build_sample(tmp_path / "sample.xlsx", 2026, 8)
    assert detect_year_month(path) == (2026, 8)

    cfg = load_config("config/roster.example.yaml")
    schedule = read_schedule(path, 2026, 8, cfg)
    assert schedule.names_in_sheet == cfg.member_names
    # 日曜は全員「公」（黒字）
    assert schedule.day_cells("担当A", dt.date(2026, 8, 2)).texts() == ["公"]
    assert not schedule.day_cells("担当A", dt.date(2026, 8, 2)).red
