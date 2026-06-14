export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // 0 = off, 1 = warn, 2 = error  |  "always" / "never"
    "scope-enum": [
      2,
      "always",
      [
        "config", // commitlint, ruff, pre-commit config
        "workflows", // .github/workflows/
        "game", // core game engine (game/)
        // "players" scope removed — use `player:` type for all player additions/updates
        "leaderboard", // leaderboard schema and data
        "scripts", // .github/scripts/
        "tests", // test-only changes
        "specs", // docs/specs/ design docs
        "plans", // docs/plans/ implementation plans
      ],
    ],
    "scope-empty": [0, "never"], // off — player: commits legitimately have no scope
    "type-enum": [
      2,
      "always",
      [
        // conventional commits standard types
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
        // add custom types below
        "player", // adding or updating a player strategy (players/); ignored by semantic-release
        "doh", // escape hatch — never bumps version, never appears in changelog
      ],
    ],
  },
};
