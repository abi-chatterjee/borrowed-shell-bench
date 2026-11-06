# Agent skills

`borrowed-shell/` is an agent skill (a `SKILL.md` plus reference files) that teaches coding agents such as Claude Code to build or retrofit a desktop app with the Borrowed Shell pattern: a pure Python or Node.js package, the OS web view as its window, and a one-line installer that assembles the native shell on the user's machine.

| File | Loaded when |
|---|---|
| `borrowed-shell/SKILL.md` | the agent decides the skill applies: fit check, build order, hard rules, checklist |
| `references/runtime.md` | building the loopback server, window, logging and Windows preflight |
| `references/macos-shell.md` | building the `.app` bundle |
| `references/windows-shell.md` | building the Start-menu shortcut |
| `references/installer.md` | writing `install.sh` / `install.ps1`, update and uninstall |

## Install

Claude Code, for all your projects:

```sh
git clone --depth 1 https://github.com/abi-chatterjee/borrowed-shell-bench /tmp/borrowed-shell-bench
mkdir -p ~/.claude/skills
cp -R /tmp/borrowed-shell-bench/skills/borrowed-shell ~/.claude/skills/
```

For one project only, copy the folder to `<project>/.claude/skills/borrowed-shell` and commit it.

Other agents that read `SKILL.md` folders can use the same directory. For agents without skill support, point them at `skills/borrowed-shell/SKILL.md` and say "follow this".

## Use

Ask for it directly, for example: "Turn this Flask app into a desktop app using the borrowed-shell skill", or "Add a Borrowed Shell installer and macOS app bundle to this Node project". The skill starts with a fit check and stops if the pattern does not suit the app.

The working code the skill is distilled from is in `../bshell/py` and `../bshell/node`.
