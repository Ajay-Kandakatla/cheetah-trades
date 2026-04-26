# Spec-Driven Development with Spec Kit

This project uses [GitHub spec-kit](https://github.com/github/spec-kit) for
feature specs. The toolkit is installed locally (the upstream releases are
empty as of v0.8.1, so we vendored the templates + scripts directly from
the repo at install time).

## Workflow

Use these slash commands inside Claude Code, in order:

| Slash command | What it does |
|---|---|
| `/constitution` | Update the principles in `.specify/memory/constitution.md`. The constitution rules every other artifact must respect. |
| `/specify <description>` | Create a new feature spec under `specs/<NNN-name>/spec.md`. Asks clarifying questions about *what* + *why*, never *how*. |
| `/clarify` | Reconcile ambiguities in the spec. Run before `/plan` for non-trivial features. |
| `/plan` | Generate an implementation plan (`plan.md`) with technical context, data model, contracts, and a quickstart. |
| `/tasks` | Break the plan into a numbered, dependency-ordered task list (`tasks.md`). |
| `/analyze` | Cross-check the spec, plan, and tasks for consistency before implementing. |
| `/implement` | Execute the task list. |
| `/checklist` | Generate quality / acceptance checklists for the feature. |

## Files

- `.specify/memory/constitution.md` — non-negotiable project principles
  (cache strategy, free-tier first, two-tier scan architecture, etc.)
- `.specify/templates/*-template.md` — boilerplate that `/specify`,
  `/plan`, etc. fill in.
- `.specify/scripts/bash/*.sh` — helpers invoked by the slash commands
  (path resolution, branch checks, JSON output for command parsing).
- `.claude/commands/*.md` — slash-command bodies the Claude Code agent
  reads to execute each step.

## Conventions

- Each feature lives on its own git branch named like `NNN-short-name`
  (e.g. `042-dual-momentum`). Branch + spec dir share the slug.
- Specs are committed alongside code in the same PR, never after.
- The constitution wins disputes between specs, code, and SPECS.md.
- SPECS.md remains the canonical *system* documentation; spec-kit
  artifacts under `specs/` are *feature* documentation. They don't
  overlap — when a feature lands, distill it into SPECS.md and the
  spec stays as historical record.

## Override the local install

If GitHub spec-kit publishes proper release assets again, you can
re-init via `uvx --from specify-cli specify init --here --ai claude
--script sh --force`. The vendored copies under `.specify/` and
`.claude/commands/` will be overwritten — make sure `constitution.md`
is committed first.
