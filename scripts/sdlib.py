#!/usr/bin/env python3
"""sdlib — shared helpers for skill-doctor (stdlib only).

Houses the ground-truth mechanics (see ../references/mechanics.md):
  * frontmatter parsing (minimal YAML subset)
  * skill discovery across editable roots (personal + project)
  * exact injected-text replication (name + description + when_to_use, cap 1536)
  * token estimation (offline heuristic; tokenizer-independent relative % is what matters)
  * word tokenization + jaccard similarity (for collision shortlisting)
  * reading the authoritative `skill_listing` attachment from live transcripts
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# Per-skill combined (description + when_to_use) injection cap — verified mechanic.
LISTING_CAP_CHARS = 1536
# Offline token heuristic. ~4 chars/token for English. Opus 4.7+ tokenizer runs ~30% higher;
# absolute token figures are estimates, but relative % savings are tokenizer-independent.
DEFAULT_CHARS_PER_TOKEN = 4.0

# Claude Code's default skill-listing budget is ~1% of the context window
# (~2,000 tokens on a 200k window). Past it, descriptions are shortened/dropped.
DEFAULT_SKILL_BUDGET_TOKENS = 2000

# Target size for a single skill's injected description when compressing.
COMPRESS_TARGET_TOKENS = 75


def cost_grade(tokens: int) -> str:
    """A-F grade for a single skill's per-turn token cost (cheaper = better)."""
    if tokens <= 50:
        return "A"
    if tokens <= 100:
        return "B"
    if tokens <= 150:
        return "C"
    if tokens <= 250:
        return "D"
    return "F"

# Clearly-deprecated model identifiers worth flagging in skill bodies.
STALE_MODEL_PATTERNS = [
    r"\bclaude-instant(?:-v?\d[\d.]*)?\b",
    r"\bclaude-1(?:\.\d+)?\b",
    r"\bclaude-2(?:\.\d+)?\b",
    r"\bclaude-v1\b",
    r"\bclaude-v2\b",
    r"\btext-davinci-\d+\b",
    r"\bcode-davinci-\d+\b",
    r"\bgpt-3\.5-turbo-0301\b",
    r"\bgpt-4-32k\b",
    r"\bgpt-4-0314\b",
]
_STALE_RE = re.compile("|".join(STALE_MODEL_PATTERNS), re.IGNORECASE)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "this",
    "that", "is", "are", "be", "use", "used", "using", "when", "you", "your", "it",
    "as", "by", "at", "from", "into", "any", "all", "not", "do", "does", "can",
    "skill", "claude", "code", "task", "tasks", "user", "users", "also", "via",
}


# --------------------------------------------------------------------------- #
# Frontmatter
# --------------------------------------------------------------------------- #
def parse_frontmatter(text: str) -> dict:
    """Parse a leading `---` YAML frontmatter block.

    Handles plain scalars, single/double-quoted strings, and block scalars
    (`key: |` / `key: >`). Returns lowercased keys plus `_body` (post-frontmatter).
    Booleans -> Python bool. Unknown / malformed -> best effort, never raises.
    """
    out: dict = {"_body": text}
    if not text.startswith("---"):
        return out
    # Split the first fenced block (tolerate CRLF and EOF without trailing newline).
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)(.*)$", text, re.DOTALL)
    if not m:
        return out
    block, body = m.group(1), m.group(2)
    out["_body"] = body

    lines = block.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        km = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", raw)
        if not km:
            continue
        key = km.group(1).strip().lower()
        val = km.group(2).strip()
        # Block scalar.
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            collected = []
            # Consume more-indented lines.
            base_indent = None
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    collected.append("")
                    i += 1
                    continue
                indent = len(nxt) - len(nxt.lstrip())
                if base_indent is None:
                    base_indent = indent
                if indent < base_indent:
                    break
                collected.append(nxt[base_indent:])
                i += 1
            joiner = " " if val.startswith(">") else "\n"
            out[key] = joiner.join(collected).strip()
            continue
        if val == "":
            # Empty value after `key:` => implicit multi-line plain scalar
            # (indented continuation lines) or a nested mapping. Fold the
            # indented continuation as text. This is the style Anthropic's own
            # skills use for `description:` — must be handled or cost is wrong.
            collected = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    break
                if len(nxt) - len(nxt.lstrip()) == 0:  # back to column 0 => next key
                    break
                collected.append(nxt.strip())
                i += 1
            out[key] = " ".join(collected).strip()
            continue
        out[key] = _coerce_scalar(val)
    return out


def _coerce_scalar(val: str):
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    low = val.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    return val


def set_frontmatter_field(text: str, key: str, value: str) -> str:
    """Return text with frontmatter `key` set to `value` as a single double-quoted
    scalar. Replaces the key's full span (single-line, quoted, block scalar, or
    empty+indented-continuation), preserving all other keys. Creates frontmatter
    if absent. Newlines/tabs in value are collapsed to spaces; quotes escaped."""
    clean = " ".join(str(value).split())
    escaped = clean.replace("\\", "\\\\").replace('"', '\\"')
    new_line = f'{key}: "{escaped}"'

    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)(.*)$", text, re.DOTALL)
    if not m:
        return f"---\n{new_line}\n---\n\n{text}"
    block, body = m.group(1), m.group(2)
    lines = block.split("\n")

    out = []
    i = 0
    replaced = False
    key_re = re.compile(rf"^{re.escape(key)}\s*:\s*(.*)$")
    while i < len(lines):
        km = key_re.match(lines[i])
        if not km:
            out.append(lines[i])
            i += 1
            continue
        # Found the key — consume its full value span.
        val = km.group(1).strip()
        i += 1
        if val in ("|", ">", "|-", ">-", "|+", ">+") or val == "":
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "" or (len(nxt) - len(nxt.lstrip())) == 0:
                    break
                i += 1
        out.append(new_line)
        replaced = True
    if not replaced:
        out.insert(0, new_line)
    return f"---\n" + "\n".join(out) + "\n---\n" + body


def as_bool(val, default=False) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "yes", "1")


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #
def claude_home() -> Path:
    env = os.environ.get("CLAUDE_HOME")
    if env:
        return Path(env)
    return Path.home() / ".claude"


def default_roots(cwd: str | None = None) -> list[tuple[Path, str]]:
    """Editable skill roots: personal + project. (Plugin/bundled skills are not
    user-editable; they're handled via the authoritative listing, not disk walks.)"""
    roots: list[tuple[Path, str]] = []
    personal = claude_home() / "skills"
    roots.append((personal, "personal"))
    base = Path(cwd) if cwd else Path.cwd()
    roots.append((base / ".claude" / "skills", "project"))
    return roots


def discover_skills(roots: list[tuple[Path, str]]) -> list[dict]:
    """Return one record per `<root>/<name>/SKILL.md`. Directory name is the
    canonical id (slash-command name); frontmatter `name` is display only."""
    found: dict[str, dict] = {}
    # Precedence: personal overrides project overrides bundled (first wins here
    # because we iterate roots in precedence order).
    order = {"enterprise": 0, "personal": 1, "project": 2, "plugin": 3, "bundled": 4}
    for root, level in roots:
        if not root.exists():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            name = skill_md.parent.name
            try:
                text = skill_md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = parse_frontmatter(text)
            try:
                mtime = skill_md.stat().st_mtime
            except OSError:
                mtime = 0.0
            rec = _build_record(name, skill_md, level, fm, mtime)
            prev = found.get(name)
            if prev is None or order.get(level, 9) < order.get(prev["level"], 9):
                found[name] = rec
    return list(found.values())


def _build_record(name: str, path: Path, level: str, fm: dict, mtime: float = 0.0) -> dict:
    desc = str(fm.get("description") or "")
    when = str(fm.get("when_to_use") or "")
    disabled = as_bool(fm.get("disable-model-invocation"), False)
    user_inv = as_bool(fm.get("user-invocable"), True)
    # `paths`-scoped skills auto-load only when matching files are in play, so
    # their description is NOT part of the always-on per-turn tax.
    conditional = bool(str(fm.get("paths") or "").strip())
    always_on = not disabled and not conditional
    injected = injected_text(name, desc, when) if always_on else ""
    body = fm.get("_body") or ""
    return {
        "name": name,
        "display_name": fm.get("name") or name,
        "path": str(path),
        "level": level,
        "description": desc,
        "when_to_use": when,
        "disabled": disabled,            # disable-model-invocation: true -> cost 0
        "conditional": conditional,      # paths-scoped -> cost only when files match
        "user_invocable": user_inv,
        "mtime": mtime,
        "desc_chars": len(desc) + len(when),
        "injected_chars": len(injected),
        "body_chars": len(body),          # on-invoke cost (loaded only when the skill fires)
        "stale": stale_findings(body),
    }


# --------------------------------------------------------------------------- #
# Cost
# --------------------------------------------------------------------------- #
def injected_text(name: str, description: str, when_to_use: str = "") -> str:
    """Replicate the per-skill listing line that is injected every turn.

    Observed format: `- {name}: {description}` with when_to_use appended; the
    combined description+when_to_use is capped at 1536 chars.
    """
    combined = description
    if when_to_use:
        combined = (combined + " " + when_to_use).strip()
    if len(combined) > LISTING_CAP_CHARS:
        combined = combined[:LISTING_CAP_CHARS]
    return f"- {name}: {combined}"


def est_tokens(text: str, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> int:
    if not text:
        return 0
    return int(round(len(text) / chars_per_token))


def count_tokens_exact(text: str, model: str = "claude-opus-4-8",
                       api_key: str | None = None, timeout: float = 20.0):
    """Exact token count via Anthropic's count_tokens endpoint. Returns an int,
    or None if no API key is available or the request fails (caller falls back to
    the offline estimate). Uses stdlib urllib only — no SDK dependency."""
    import json as _json
    import urllib.request

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not text:
        return None
    payload = _json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": text}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read()).get("input_tokens")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Staleness
# --------------------------------------------------------------------------- #
def stale_findings(body: str) -> list[str]:
    if not body:
        return []
    hits = sorted({m.group(0) for m in _STALE_RE.finditer(body)})
    return hits


# --------------------------------------------------------------------------- #
# Similarity (collision shortlisting)
# --------------------------------------------------------------------------- #
def tokenize_words(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def overlap_coefficient(a: set[str], b: set[str]) -> float:
    """Szymkiewicz-Simpson overlap = |a∩b| / min(|a|,|b|).

    Better than Jaccard for trigger-collision detection: a short, focused skill
    whose keywords are a subset of a broader skill's still scores high, even
    though Jaccard is dragged down by the size difference.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# --------------------------------------------------------------------------- #
# Authoritative skill_listing from transcripts
# --------------------------------------------------------------------------- #
def parse_listing_content(content: str) -> dict[str, str]:
    """Split a `skill_listing.content` blob into {name: description}.

    Lines look like `- name: description...`. Continuation lines (rare) are
    appended to the previous entry.
    """
    out: dict[str, str] = {}
    last = None
    for line in content.split("\n"):
        m = re.match(r"^- ([A-Za-z0-9:_-]+):\s?(.*)$", line)
        if m:
            last = m.group(1)
            out[last] = m.group(2)
        elif last is not None and line.strip():
            out[last] += " " + line.strip()
    return out


def latest_skill_listing(projects_dir: Path | None = None) -> dict | None:
    """Return the most recent `skill_listing` attachment (by file mtime then
    max skillCount) found under the Claude projects dir, or None."""
    projects_dir = projects_dir or (claude_home() / "projects")
    if not projects_dir.exists():
        return None
    candidates = sorted(
        projects_dir.rglob("*.jsonl"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    # Return the listing from the newest file that has a non-empty one. Within a
    # file, prefer the largest skillCount (a file mixes the main-session listing
    # with smaller subagent listings). Skipping empty (skillCount<=0) listings
    # avoids letting an aborted session win, while staying current rather than
    # grabbing a larger but stale listing from another project.
    for f in candidates[:200]:
        file_best = None
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"skill_listing"' not in line:
                        continue
                    try:
                        att = json.loads(line).get("attachment", {})
                    except json.JSONDecodeError:
                        continue
                    if att.get("type") == "skill_listing" and att.get("skillCount", 0) > 0:
                        if file_best is None or att["skillCount"] > file_best["skillCount"]:
                            file_best = att
        except OSError:
            continue
        if file_best is not None:
            return file_best
    return None
