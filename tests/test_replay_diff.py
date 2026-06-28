def _write_lb(path, players_data: dict):
    import yaml

    path.write_text(yaml.safe_dump({"players": players_data}))


def test_write_diff_report_creates_file(tmp_path):
    from game.simulation.quarter import write_diff_report

    original = {
        "Alice": {
            "tier": "CH",
            "display_name": "Alice",
            "tier_stats": {"CH": {"wins": 40, "games": 100}},
        },
        "Bob": {
            "tier": "L1",
            "display_name": "Bob",
            "tier_stats": {"L1": {"wins": 30, "games": 100}},
        },
    }
    replay_lb = tmp_path / "lb.yaml"
    _write_lb(
        replay_lb,
        {
            "Alice": {
                "tier": "PRM",
                "display_name": "Alice",
                "tier_stats": {"PRM": {"wins": 55, "games": 100}},
            },
            "Bob": {
                "tier": "CH",
                "display_name": "Bob",
                "tier_stats": {"CH": {"wins": 35, "games": 100}},
            },
        },
    )
    out = tmp_path / "diff.md"
    write_diff_report(original, str(replay_lb), out)

    text = out.read_text()
    assert "Alice" in text
    assert "Bob" in text
    assert "CH" in text
    assert "PRM" in text


def test_write_diff_report_contains_delta(tmp_path):
    from game.simulation.quarter import write_diff_report

    original = {
        "Alice": {
            "tier": "CH",
            "display_name": "Alice",
            "tier_stats": {"CH": {"wins": 40, "games": 100}},
        },
    }
    replay_lb = tmp_path / "lb.yaml"
    _write_lb(
        replay_lb,
        {
            "Alice": {
                "tier": "CH",
                "display_name": "Alice",
                "tier_stats": {"CH": {"wins": 50, "games": 100}},
            },
        },
    )
    out = tmp_path / "diff.md"
    write_diff_report(original, str(replay_lb), out)

    text = out.read_text()
    assert "+10" in text or "10.0" in text
