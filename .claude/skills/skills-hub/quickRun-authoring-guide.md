# Quick Run Authoring Guide

Add a `quickRun.json` file to your skill folder to expose one-click actions in the Skills Hub tree view.

## Getting started

1. Create `quickRun.json` in your skill's root folder (next to `config.json` / `SKILL.md`)
2. Add the schema reference for editor auto-completion:

```json
{
  "$schema": "../skills-hub/quickRun.schema.json",
  "actions": []
}
```

3. Define one or more actions (see examples below)
4. Reload the Skills Hub tree — your actions appear as child nodes under the skill

## Two action modes

| Mode | When to use | Required field |
|------|-------------|----------------|
| **Chat** | The action is conversational — Copilot interprets the prompt and calls skill tools | `promptTemplate` |
| **Terminal** | The action runs a script directly — no LLM interpretation needed | `run.command` |

Every action must have **exactly one** of these. The extension auto-detects the mode from which field is present.

## Chat action example

A chat action injects a prompt into Copilot Chat. The agent then executes it using the skill's MCP tools.

```json
{
  "$schema": "../skills-hub/quickRun.schema.json",
  "actions": [
    {
      "id": "convert-doc",
      "label": "Convert document to markdown",
      "description": "Convert a Word/PDF document using Doc2Md",
      "inputs": [
        {
          "key": "inputPath",
          "prompt": "Document path",
          "type": "path",
          "chooser": "file",
          "chooserMode": "open",
          "required": true,
          "placeholder": "C:\\docs\\spec.docx"
        },
        {
          "key": "outputPath",
          "prompt": "Output path",
          "type": "path",
          "chooser": "file",
          "chooserMode": "save",
          "required": true,
          "placeholder": "C:\\docs\\spec.md"
        }
      ],
      "promptTemplate": "convert {inputPath} to markdown and save to {outputPath}"
    }
  ]
}
```

## Terminal action example

A terminal action runs a command directly (or routes it through agent chat, depending on the user's execution mode preference).

```json
{
  "$schema": "../skills-hub/quickRun.schema.json",
  "actions": [
    {
      "id": "display",
      "label": "Display wiki page",
      "description": "Run read_wiki.py and print markdown to terminal",
      "inputs": [
        {
          "key": "input",
          "prompt": "Wiki URL or page ID",
          "required": true,
          "placeholder": "https://wiki.example.com/pages/12345"
        }
      ],
      "run": {
        "type": "terminal",
        "command": "{pythonExecutable}",
        "argsTemplate": ["read_wiki.py", "{input}"],
        "cwd": "{skillPath}"
      }
    }
  ]
}
```

## Field reference

### Action fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | **Yes** | Unique ID within the skill. Letters, digits, hyphens, underscores only. |
| `label` | string | **Yes** | Display name shown in the tree and form. |
| `description` | string | No | Tooltip / subtitle text. |
| `promptTemplate` | string | Chat actions | Prompt with `{placeholder}` substitution. |
| `run` | object | Terminal actions | Terminal execution config (see below). |
| `inputs` | array | No | Input fields shown in the form. |

### Run config fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `run.type` | `"terminal"` | No | Execution type. Currently only `"terminal"` is supported. When the `run` block is present, always set `"type": "terminal"` explicitly. |
| `run.command` | string | **Yes** | Executable path. Supports `{placeholders}`. |
| `run.argsTemplate` | string[] | No | Command arguments as an array. Each element supports `{placeholders}`. |
| `run.cwd` | string | No | Working directory. Supports `{placeholders}`. Defaults to `{skillPath}` if omitted. |

### Optional template segments

Templates also support optional segments using square brackets: `[ ... ]`.

- A segment is included only when **all** placeholders inside it have non-empty values.
- If any placeholder inside is empty, the entire segment is removed.
- This works in `promptTemplate`, `run.command`, `run.argsTemplate`, and `run.cwd`.

Examples:

- `search wiki for {query} [in space {space}]`
  - with `space=cheetah` → `search wiki for power in space cheetah`
  - with empty `space` → `search wiki for power`
- `run CQL: {cql} [limit {limit}]`

### Input fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key` | string | — | **Required.** Unique key referenced as `{key}` in templates. |
| `prompt` | string | — | **Required.** Label shown next to the input. |
| `type` | string | `"text"` | One of: `text`, `multiline`, `choice`, `file`, `folder`, `fileOrFolder`, `path`. |
| `required` | boolean | `false` | Whether the field must be filled before running. |
| `readonly` | boolean | `false` | Whether the field is read-only. When `true`, the input is non-editable and the Browse button is hidden for path inputs. |
| `placeholder` | string | — | Hint text in the empty field. |
| `default` | string | — | Pre-filled default value. |
| `choices` | array | — | For `choice` type. Array of strings or `{label, value}` objects. |
| `chooser` | string | — | For `path` type: `"file"`, `"folder"`, or `"fileOrFolder"`. |
| `chooserMode` | string | `"open"` | For `path` type: `"open"` or `"save"`. |
| `multiple` | boolean | `false` | Allow selecting multiple files/folders (for `file`, `folder`, `fileOrFolder`, and `path` types with a browse picker). |
| `filters` | object | — | File type filters for the native picker. Keys are labels, values are arrays of extensions (without dots). Example: `{"PDF Files": ["pdf"]}`. |

## Built-in placeholders

These are injected automatically by the extension — you don't need to define inputs for them:

| Placeholder | Description |
|-------------|-------------|
| `{pythonExecutable}` | Resolved Python interpreter path (respects `SKILLS_HUB_PYTHON_ENV_HOME` and virtual environments). |
| `{skillPath}` | Absolute path to the skill's folder on disk. |
| `{workspaceRoot}` | Absolute path to the VS Code workspace root folder. |

## Tips

- **Start with chat mode.** It's simpler (just a prompt template) and lets the agent handle edge cases.
- **Use terminal mode** when you need deterministic execution — exact command, no LLM interpretation.
- **Keep prompts specific.** Vague prompts like "process the file" lead to inconsistent results. Say exactly what the agent should do.
- **Use optional segments** for truly optional text: `... [in space {space}]`.
- **Use `path` type with `chooser`** for file/folder inputs — it gives users a native OS picker button.
- **Test your JSON** by opening it in VS Code with the `$schema` reference. Red squiggles = errors.
- **One action is fine.** You don't need multiple actions. Start with the most common workflow.

## Validation rules

The extension validates your `quickRun.json` at load time:

1. `id` and `label` are required on every action
2. Chat actions must have a non-empty `promptTemplate`
3. Terminal actions must have a non-empty `run.command`
4. Every `{placeholder}` in a template must have a matching input `key` (or be a built-in placeholder)
5. Every `required` input must be filled before the action runs