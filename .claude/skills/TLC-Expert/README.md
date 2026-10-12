# TLC Expert Skill

This is the local Skills Hub companion for the VS Code **TLC Expert** agent.
It provides an on-demand, read-only workflow for analyzing Wi-Fi TLC / Rate
Scale Manager behavior and comparing firmware intent with the TLC simulator.

## Contents

- `SKILL.md` — skill contract, trigger phrases, workflow, source order, and examples.
- `config.json` — Skills Hub metadata and version.

## Relationship to the custom agent

The custom agent lives at `.github/agents/TLC Expert.agent.md` and provides the
conversation persona and tool restrictions. This skill provides reusable
workflow guidance and can later be distributed through the central Skills Hub.

The package currently has no Python entrypoint or external dependencies. It is
therefore cross-platform and can run with the Skills Hub's non-Python defaults.

## Local testing

Open the workspace in VS Code, select **TLC Expert** from the agent picker, and
use one of the examples in `SKILL.md`. The skill should guide the analysis using
`TLC_Hierarchy.md`, `tlcsim/`, `PERModel/`, and `Results/`.

## Future central-hub publication

Before publication, confirm the repository destination, install the package
through Skills Hub Manager, increment the semantic version, and validate any
ChAI Vector Store or Jira integration against released sources.
