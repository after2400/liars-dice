from game.components.isolation.env import scrub_environment


def test_scrubs_exact_denylist_and_patterns():
    env = {
        "GH_TOKEN": "x",
        "LEADERBOARD_PAT": "y",
        "GITHUB_TOKEN": "z",
        "MY_API_KEY": "k",
        "db_password": "p",
        "SOME_SECRET": "s",
        "PATH": "/usr/bin",
        "HOME": "/home/u",
        "N_GAMES": "1000",
    }
    removed = scrub_environment(env)
    assert "GH_TOKEN" not in env and "LEADERBOARD_PAT" not in env
    assert "MY_API_KEY" not in env and "db_password" not in env
    assert "SOME_SECRET" not in env and "GITHUB_TOKEN" not in env
    # Non-secrets survive:
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/u"
    assert env["N_GAMES"] == "1000"
    assert removed == sorted(
        ["GH_TOKEN", "GITHUB_TOKEN", "LEADERBOARD_PAT", "MY_API_KEY", "SOME_SECRET", "db_password"]
    )
