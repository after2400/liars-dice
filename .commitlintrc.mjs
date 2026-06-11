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
        "players", // player files (players/)
        "leaderboard", // leaderboard schema and data
        "scripts", // .github/scripts/
        "tests", // test-only changes
        "specs", // docs/specs/ design docs
        "plans", // docs/plans/ implementation plans
      ],
    ],
    "scope-empty": [1, "never"], // warn if no scope provided
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
      ],
    ],
  },
};
