#!/usr/bin/env python3
"""
Jira WPLS-PA Skill — Unified CLI entrypoint.

Subcommands:
  fetch       Retrieve a single Jira issue by key
  search      Search issues via JQL
  comment     Add a comment to an issue
  transition  Transition an issue to a new status
  update      Update issue fields from a JSON file
  duplicate   Duplicate an issue hierarchy (parent → children → grandchildren)

Requires JIRA_URL and JIRA_PAT_TOKEN in environment or .env file.
"""

import argparse
import json
import os
import sys
import requests
import urllib3
from dotenv import load_dotenv

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env
load_dotenv()

# Remove proxy env vars so requests connects directly to internal hosts
for _pvar in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(_pvar, None)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_PAT_TOKEN = os.getenv("JIRA_PAT_TOKEN")


def _check_env():
    """Validate required environment variables."""
    if not JIRA_URL or not JIRA_PAT_TOKEN:
        print("❌ Missing environment variables: JIRA_URL and/or JIRA_PAT_TOKEN.")
        print("   Set them in a .env file or export them before running.")
        sys.exit(1)


def _headers():
    return {
        "Authorization": f"Bearer {JIRA_PAT_TOKEN}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# REST helpers
# ---------------------------------------------------------------------------

def api_get(path, params=None):
    """GET from Jira REST API."""
    resp = requests.get(f"{JIRA_URL}{path}", headers=_headers(), params=params, verify=False)
    resp.raise_for_status()
    return resp.json()


def api_post(path, payload):
    """POST to Jira REST API.  Returns (status_code, json_body)."""
    resp = requests.post(f"{JIRA_URL}{path}", headers=_headers(), json=payload, verify=False)
    return resp.status_code, resp.json() if resp.text else {}


def api_put(path, payload):
    """PUT to Jira REST API."""
    resp = requests.put(f"{JIRA_URL}{path}", headers=_headers(), json=payload, verify=False)
    return resp.status_code, resp.text


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

def cmd_fetch(args):
    """Retrieve a single Jira issue and print as JSON."""
    data = api_get(f"/rest/api/2/issue/{args.issue_key}")
    fields = data.get("fields", {})

    comments = fields.get("comment", {}).get("comments", [])
    last_comment = comments[-1]["body"] if comments else None

    result = {
        "key": data["key"],
        "summary": fields.get("summary"),
        "description": fields.get("description"),
        "status": (fields.get("status") or {}).get("name"),
        "reporter": (fields.get("reporter") or {}).get("displayName"),
        "last_comment": last_comment,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def cmd_search(args):
    """Search issues via JQL."""
    params = {"jql": args.jql, "maxResults": args.max_results, "fields": "key,summary,status"}
    data = api_get("/rest/api/2/search", params=params)
    issues = data.get("issues", [])
    print(f"✅ Found {len(issues)} issue(s).\n")
    for issue in issues:
        f = issue["fields"]
        status = (f.get("status") or {}).get("name", "")
        print(f"  {issue['key']:16s}  [{status}]  {f.get('summary', '')}")


# ---------------------------------------------------------------------------
# comment
# ---------------------------------------------------------------------------

def cmd_comment(args):
    """Add a comment to an issue."""
    code, body = api_post(f"/rest/api/2/issue/{args.issue_key}/comment", {"body": args.body})
    if code == 201:
        print(f"💬 Comment added to {args.issue_key}.")
    else:
        print(f"❌ Failed ({code}): {body}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------

def cmd_transition(args):
    """Transition an issue to a new status."""
    data = api_get(f"/rest/api/2/issue/{args.issue_key}/transitions")
    target = args.status.lower()
    transition_id = None
    for t in data.get("transitions", []):
        if t.get("to", {}).get("name", "").lower() == target:
            transition_id = t["id"]
            break
    if not transition_id:
        available = [t["to"]["name"] for t in data.get("transitions", [])]
        print(f"⚠️  Status '{args.status}' not available.  Options: {available}")
        sys.exit(1)
    code, _ = api_post(f"/rest/api/2/issue/{args.issue_key}/transitions", {"transition": {"id": transition_id}})
    if code in (200, 204):
        print(f"🔄 {args.issue_key} → '{args.status}'")
    else:
        print(f"❌ Transition failed ({code})")
        sys.exit(1)


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def cmd_update(args):
    """Update issue fields from a JSON file."""
    with open(args.json_file, "r", encoding="utf-8") as fh:
        fields = json.load(fh)
    code, text = api_put(f"/rest/api/2/issue/{args.issue_key}", {"fields": fields})
    if code in (200, 204):
        print(f"✅ {args.issue_key} updated.")
    else:
        print(f"❌ Update failed ({code}): {text}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# duplicate  (hierarchy duplicator)
# ---------------------------------------------------------------------------

# Global set to track custom fields that have been rejected by Jira
_REJECTED_FIELDS = set()


def _get_issues(jql):
    """Retrieve issues via JQL (up to 1000)."""
    params = {"jql": jql, "fields": ["*all"], "maxResults": 1000}
    try:
        data = api_get("/rest/api/2/search", params=params)
        return data.get("issues", [])
    except requests.exceptions.RequestException as e:
        print(f"  Failed to retrieve issues: {e}")
        return []


def _get_linked_issues(issue_key, link_type="Inclussion"):
    """Get issues linked with *link_type* (outward + inward)."""
    data = api_get(f"/rest/api/2/issue/{issue_key}")
    linked = []
    for link in data.get("fields", {}).get("issuelinks", []):
        if link["type"]["name"].lower() != link_type.lower():
            continue
        if "outwardIssue" in link:
            linked.append({"key": link["outwardIssue"]["key"], "direction": "outbound"})
        elif "inwardIssue" in link:
            linked.append({"key": link["inwardIssue"]["key"], "direction": "inbound"})
    return linked


def _get_subtasks(issue_key):
    """Return subtask keys for an issue."""
    data = api_get(f"/rest/api/2/issue/{issue_key}")
    return [{"key": s["key"]} for s in data.get("fields", {}).get("subtasks", [])]


def _get_user_accountid(username):
    """Resolve username → accountId."""
    try:
        users = api_get("/rest/api/2/user/search", params={"username": username})
        if users:
            return users[0].get("accountId") or users[0].get("name")
    except Exception:
        pass
    return None


def _update_reporter(issue_key, reporter_name):
    """Attempt to set reporter (Server name → Cloud accountId fallback)."""
    code, _ = api_put(f"/rest/api/2/issue/{issue_key}", {"fields": {"reporter": {"name": reporter_name}}})
    if code in (200, 204):
        print(f"   ✓ Reporter → {reporter_name}")
        return True
    account_id = _get_user_accountid(reporter_name)
    if account_id:
        code, _ = api_put(f"/rest/api/2/issue/{issue_key}", {"fields": {"reporter": {"accountId": account_id}}})
        if code in (200, 204):
            print(f"   ✓ Reporter → {reporter_name} (accountId)")
            return True
    print(f"   ⚠️  Could not update reporter")
    return False


def _convert_custom_field(field_value):
    """Simplify a custom field value for creation payloads."""
    if isinstance(field_value, dict):
        for key in ("value", "name", "id", "key"):
            if key in field_value:
                return {key: field_value[key]}
        return field_value
    if isinstance(field_value, list):
        converted = []
        for item in field_value:
            if isinstance(item, dict):
                for key in ("value", "name"):
                    if key in item:
                        converted.append({key: item[key]})
                        break
                else:
                    converted.append(item)
            else:
                converted.append(item)
        return converted
    return field_value


def _copy_custom_fields(source_fields, target, skip_fields):
    """Copy customfield_* entries from source into target dict."""
    for name, value in source_fields.items():
        if not name.startswith("customfield_") or value is None:
            continue
        if name in skip_fields or name in _REJECTED_FIELDS or name in target:
            continue
        try:
            target[name] = _convert_custom_field(value)
        except Exception:
            pass


def _create_with_retry(payload, reporter_to_set=None):
    """POST /rest/api/2/issue with up to 3 retry rounds removing rejected fields."""
    for attempt in range(3):
        code, body = api_post("/rest/api/2/issue", payload)
        if code in (200, 201):
            new_key = body["key"]
            if reporter_to_set:
                _update_reporter(new_key, reporter_to_set)
            return new_key
        errors = body.get("errors", {})
        if not errors:
            break
        problematic = list(errors.keys())
        _REJECTED_FIELDS.update(f for f in problematic if f.startswith("customfield_"))
        reporter_removed = "reporter" in problematic
        for f in problematic:
            payload["fields"].pop(f, None)
        if reporter_removed and reporter_to_set:
            # will set reporter post-creation
            pass
        print(f"   🔄 Retry #{attempt+1}: removed {problematic}")

    # Final fallback: minimal fields only
    minimal = {k: payload["fields"][k] for k in ("project", "summary", "issuetype") if k in payload["fields"]}
    for k in ("description", "labels"):
        if k in payload["fields"]:
            minimal[k] = payload["fields"][k]
    code, body = api_post("/rest/api/2/issue", {"fields": minimal})
    if code in (200, 201):
        new_key = body["key"]
        if reporter_to_set:
            _update_reporter(new_key, reporter_to_set)
        return new_key

    print(f"   ❌ Could not create issue after retries: {body}")
    return None


def _duplicate_issue(original, new_label, remove_label, project_key, overrides, reporter_name):
    """Duplicate a single issue with label swap and field overrides."""
    orig_key = original["key"]
    fields = original["fields"]
    proj = project_key or orig_key.split("-")[0]

    labels = list(fields.get("labels") or [])
    if remove_label:
        labels = [l for l in labels if l != remove_label]
    if new_label and new_label not in labels:
        labels.append(new_label)

    issue_data = {
        "fields": {
            "project": {"key": proj.upper()},
            "summary": fields["summary"],
            "description": f"Gold Copy source: {JIRA_URL}/browse/{orig_key}\n\n{fields.get('description', '')}",
            "issuetype": {"name": fields["issuetype"]["name"]},
            "labels": labels,
        }
    }

    # Standard field copies
    if fields.get("assignee"):
        a = fields["assignee"]
        issue_data["fields"]["assignee"] = {"name": a.get("name") or a.get("key")}
    if fields.get("duedate"):
        issue_data["fields"]["duedate"] = fields["duedate"]
    if fields.get("components"):
        issue_data["fields"]["components"] = [{"name": c["name"]} for c in fields["components"]]

    skip = set(overrides.keys())
    _copy_custom_fields(fields, issue_data["fields"], skip)

    # Apply overrides
    for fname, fval in overrides.items():
        if fname and fval is not None:
            issue_data["fields"][fname] = fval

    reporter_to_set = None
    if reporter_name:
        issue_data["fields"]["reporter"] = {"name": reporter_name}
        reporter_to_set = reporter_name

    return _create_with_retry(issue_data, reporter_to_set)


def _create_subtask(parent_key, grandchild_issue, new_label, overrides, reporter_name):
    """Create a subtask under parent_key from grandchild issue data."""
    fields = grandchild_issue["fields"]
    desc = fields.get("description", "")
    if isinstance(desc, dict):
        desc = str(desc)
    elif desc is None:
        desc = ""

    subtask_data = {
        "fields": {
            "project": {"key": parent_key.split("-")[0].upper()},
            "summary": fields["summary"],
            "issuetype": {"name": fields["issuetype"]["name"]},
            "parent": {"key": parent_key},
        }
    }
    if desc.strip():
        subtask_data["fields"]["description"] = desc
    if new_label:
        subtask_data["fields"]["labels"] = [new_label]

    skip = set(overrides.keys())
    _copy_custom_fields(fields, subtask_data["fields"], skip)

    for fname, fval in overrides.items():
        if fname and fval is not None:
            subtask_data["fields"][fname] = fval

    reporter_to_set = None
    if reporter_name:
        subtask_data["fields"]["reporter"] = {"name": reporter_name}
        reporter_to_set = reporter_name

    return _create_with_retry(subtask_data, reporter_to_set)


def _create_issue_link(outward_key, inward_key, link_type="Inclussion"):
    """Create a link between two issues."""
    payload = {
        "type": {"name": link_type},
        "outwardIssue": {"key": outward_key},
        "inwardIssue": {"key": inward_key},
    }
    code, _ = api_post("/rest/api/2/issueLink", payload)
    if code in (200, 201):
        print(f"   🔗 {outward_key} ─{link_type}─▸ {inward_key}")
    else:
        print(f"   ⚠️  Link failed ({code})")


def _parse_json_arg(value):
    """Parse a JSON string into a Python object.  Returns None on failure."""
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        # Treat as plain string value
        return {"value": value}


def cmd_duplicate(args):
    """Duplicate an issue hierarchy: parents → children → grandchildren."""
    overrides = {}
    if args.program_field and args.program_value:
        overrides[args.program_field] = _parse_json_arg(args.program_value)
    if args.silicon_field and args.silicon_value:
        overrides[args.silicon_field] = _parse_json_arg(args.silicon_value)

    print(f"\n{'='*70}")
    print(f"🔄 Jira Issue Duplicator with Hierarchy")
    print(f"{'='*70}\n")

    # Step 1 — Retrieve & duplicate parents
    parents = _get_issues(args.jql)
    if not parents:
        print("  No parent issues found.")
        return

    print(f"Found {len(parents)} parent issue(s)\n")
    mapping = {}  # original_key → new_key

    print(f"{'='*70}\nStep 1: Duplicating Parent Issues\n{'='*70}\n")
    for p in parents:
        pk = p["key"]
        print(f"📌 Parent: {pk}")
        nk = _duplicate_issue(p, args.new_label, args.remove_label, args.project, overrides, args.reporter)
        if nk:
            mapping[pk] = nk
            print(f"   ✅ Created: {nk}\n")
        else:
            print(f"   ❌ Failed\n")

    # Step 2 — Children (linked issues)
    print(f"{'='*70}\nStep 2: Duplicating Children (linked issues)\n{'='*70}\n")
    all_children = {}
    for pk in list(mapping.keys()):
        linked = _get_linked_issues(pk, args.link_type)
        if not linked:
            print(f"📌 {pk}: no children\n")
            continue
        print(f"📌 {pk}: {len(linked)} child(ren)")
        all_children[pk] = []
        for lnk in linked:
            ck = lnk["key"]
            if ck not in mapping:
                child_issues = _get_issues(f"key = {ck}")
                if not child_issues:
                    continue
                nk = _duplicate_issue(child_issues[0], args.new_label, args.remove_label, args.project, overrides, args.reporter)
                if nk:
                    mapping[ck] = nk
                    all_children[pk].append({"original": ck, "duplicate": nk})
                    print(f"   ✅ {ck} → {nk}")
            else:
                all_children[pk].append({"original": ck, "duplicate": mapping[ck]})
        print()

    # Step 3 — Grandchildren (subtasks)
    print(f"{'='*70}\nStep 3: Duplicating Grandchildren (subtasks)\n{'='*70}\n")
    total_grandchildren = 0
    for pk, children in all_children.items():
        for child in children:
            ck = child["original"]
            subtasks = _get_subtasks(ck)
            if not subtasks:
                continue
            print(f"📌 {ck}: {len(subtasks)} subtask(s)")
            for st in subtasks:
                gk = st["key"]
                if gk not in mapping:
                    gc_issues = _get_issues(f"key = {gk}")
                    if not gc_issues:
                        continue
                    dup_child = mapping[ck]
                    nk = _create_subtask(dup_child, gc_issues[0], args.new_label, overrides, args.reporter)
                    if nk:
                        mapping[gk] = nk
                        total_grandchildren += 1
                        print(f"   ✅ {gk} → {nk} (under {dup_child})")
            print()

    # Step 4 — Create links
    print(f"{'='*70}\nStep 4: Creating Links\n{'='*70}\n")
    for pk, children in all_children.items():
        dup_parent = mapping[pk]
        for child in children:
            _create_issue_link(child["duplicate"], dup_parent, args.link_type)
        print()

    # Summary
    print(f"{'='*70}")
    print(f"✅ Duplication Complete!")
    print(f"{'='*70}\n")
    print(f"📊 Summary:")
    print(f"   Parents:       {len([k for k in mapping if k in [p['key'] for p in parents]])}")
    print(f"   Children:      {sum(len(c) for c in all_children.values())}")
    print(f"   Grandchildren: {total_grandchildren}")
    print(f"   Total:         {len(mapping)}\n")
    print(f"📋 Mapping:")
    for orig, dup in mapping.items():
        print(f"   {orig} → {dup}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="jira_wpls_pa",
        description="Jira WPLS-PA Skill — issue CRUD and hierarchy duplicator.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    p = sub.add_parser("fetch", help="Retrieve a single issue by key")
    p.add_argument("issue_key", help="Issue key (e.g. PLC-978)")

    # search
    p = sub.add_parser("search", help="Search issues via JQL")
    p.add_argument("jql", help="JQL query string")
    p.add_argument("--max-results", type=int, default=50, help="Max results (default 50)")

    # comment
    p = sub.add_parser("comment", help="Add a comment to an issue")
    p.add_argument("issue_key", help="Issue key")
    p.add_argument("body", help="Comment text")

    # transition
    p = sub.add_parser("transition", help="Transition issue to a new status")
    p.add_argument("issue_key", help="Issue key")
    p.add_argument("status", help="Target status name")

    # update
    p = sub.add_parser("update", help="Update issue fields from a JSON file")
    p.add_argument("issue_key", help="Issue key")
    p.add_argument("json_file", help="Path to JSON file with field updates")

    # duplicate
    p = sub.add_parser("duplicate", help="Duplicate issue hierarchy (parent→children→grandchildren)")
    p.add_argument("jql", help="JQL to find parent issues (e.g. 'key in (PLC-978)')")
    p.add_argument("--new-label", required=True, help="Label to add to duplicated issues")
    p.add_argument("--remove-label", default=None, help="Label to remove from duplicated issues")
    p.add_argument("--project", default=None, help="Override target project key")
    p.add_argument("--link-type", default="Inclussion", help="Link type name (default: Inclussion)")
    p.add_argument("--program-field", default=None, help="Custom field ID for Program (e.g. customfield_23600)")
    p.add_argument("--program-value", default=None, help='Program value as JSON (e.g. \'{"value":"2025"}\')')
    p.add_argument("--silicon-field", default=None, help="Custom field ID for Silicon (e.g. customfield_10238)")
    p.add_argument("--silicon-value", default=None, help='Silicon value as JSON (e.g. \'[{"value":"Whale Peak 2"}]\')')
    p.add_argument("--reporter", default=None, help="Reporter username (e.g. omelnik)")

    return parser


def main():
    _check_env()
    parser = build_parser()
    args = parser.parse_args()
    {
        "fetch": cmd_fetch,
        "search": cmd_search,
        "comment": cmd_comment,
        "transition": cmd_transition,
        "update": cmd_update,
        "duplicate": cmd_duplicate,
    }[args.command](args)


if __name__ == "__main__":
    main()
