"""
Extract real MCP tool definitions from cloned server repositories.

Tiers:
  1. Python AST  - literal Tool(...) calls; simple enums; Pydantic models
  2. TS literal  - JSON-like Tool object literals (slack, google-maps, ...)
  3. TS zod      - limited zod -> JSON Schema conversion (github, memory, ...)

Every extracted tool records provenance: repo URL, commit hash, license,
server name, source file, and extraction method. Unsupported constructs are
flagged in the report and the tool is skipped (never silently mistranslated).

Usage (from project root):
  python scripts/extract_real_mcp_tools.py
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_RAW = (
    PROJECT_ROOT
    / "data"
    / "independent_benchmark"
    / "raw"
    / "real_mcp_tools_raw.json"
)
OUTPUT_REPORT = (
    PROJECT_ROOT
    / "data"
    / "independent_benchmark"
    / "reports"
    / "extraction_report.json"
)

DEFAULT_CLONE_ROOT = Path.home() / "AppData/Local/Temp/opencode"

REPOS = {
    "servers": {
        "url": "https://github.com/modelcontextprotocol/servers",
        "license": "MIT/Apache-2.0",
        "dir": "mcp-servers",
    },
    "servers-archived": {
        "url": "https://github.com/modelcontextprotocol/servers-archived",
        "license": "MIT/Apache-2.0",
        "dir": "mcp-servers-archived",
    },
}

# server -> (repo key, relative path, tier)
SERVER_TARGETS = [
    # Tier 1: Python
    ("sqlite", "servers-archived", "src/sqlite", "python"),
    ("sentry", "servers-archived", "src/sentry", "python"),
    ("time", "servers", "src/time", "python"),
    ("git-archived", "servers-archived", "src/git", "python"),
    ("fetch", "servers", "src/fetch", "python"),
    # Tier 2: TypeScript literal
    ("slack", "servers-archived", "src/slack", "ts_literal"),
    ("google-maps", "servers-archived", "src/google-maps", "ts_literal"),
    ("puppeteer", "servers-archived", "src/puppeteer", "ts_literal"),
    ("brave-search", "servers-archived", "src/brave-search", "ts_literal"),
    ("postgres", "servers-archived", "src/postgres", "ts_literal"),
    ("aws-kb", "servers-archived", "src/aws-kb-retrieval-server", "ts_literal"),
    ("everart", "servers-archived", "src/everart", "ts_literal"),
    ("gdrive", "servers-archived", "src/gdrive", "ts_literal"),
    ("redis", "servers-archived", "src/redis", "ts_literal"),
    # Tier 3: TypeScript zod
    ("github", "servers-archived", "src/github", "ts_zod"),
    ("gitlab", "servers-archived", "src/gitlab", "ts_zod"),
    ("memory", "servers", "src/memory", "ts_zod"),
    ("everything", "servers", "src/everything", "ts_zod"),
    ("sequentialthinking", "servers", "src/sequentialthinking", "ts_zod"),
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def get_commit(repo_dir):
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def make_record(tool_name, description, input_schema, server, repo_key,
                commit, method, source_file):
    return {
        "name": tool_name,
        "description": description,
        "inputSchema": input_schema,
        "server": server,
        "source_repo": REPOS[repo_key]["url"],
        "commit": commit,
        "license": REPOS[repo_key]["license"],
        "extraction_method": method,
        "source_file": source_file,
    }


# ---------------------------------------------------------------------------
# Tier 1: Python AST extraction
# ---------------------------------------------------------------------------

def py_type_to_json(node):
    """Map a Python type annotation to a JSON schema fragment."""
    if isinstance(node, ast.Name):
        mapping = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "bool": {"type": "boolean"},
            "dict": {"type": "object"},
            "Path": {"type": "string"},
            "Any": {},
        }
        return dict(mapping.get(node.id, {"type": "string"}))

    if isinstance(node, ast.Constant) and node.value is None:
        return {}

    if isinstance(node, ast.Subscript):
        base = node.value
        base_name = base.id if isinstance(base, ast.Name) else ""
        inner = node.slice

        if base_name in ("list", "List", "Sequence"):
            return {"type": "array", "items": py_type_to_json(inner)}

        if base_name in ("dict", "Dict"):
            return {"type": "object"}

        if base_name in ("Optional",):
            return py_type_to_json(inner)

        if base_name in ("Literal",):
            values = [
                elt.value
                for elt in inner.elts
                if isinstance(elt, ast.Constant)
            ]
            return {"type": "string", "enum": values}

        if base_name in ("Union",):
            options = [py_type_to_json(elt) for elt in inner.elts]
            non_null = [o for o in options if o.get("type") != "null"]
            if len(non_null) == 1:
                return non_null[0]
            return {"anyOf": non_null}

    return {"type": "string"}


def build_python_symbols(module_ast):
    """Collect simple str enums and Pydantic models from a module."""
    enums = {}   # "Class.ATTR" -> value
    models = {}  # class name -> {field: schema fragment}

    for node in ast.walk(module_ast):
        if not isinstance(node, ast.ClassDef):
            continue

        is_enum = any(
            (isinstance(base, ast.Name) and base.id == "Enum")
            or (isinstance(base, ast.Attribute) and base.attr == "Enum")
            for base in node.bases
        )

        is_model = any(
            (isinstance(base, ast.Name) and base.id.endswith("BaseModel"))
            or (isinstance(base, ast.Attribute)
                and base.attr.endswith("BaseModel"))
            for base in node.bases
        )

        if is_enum:
            for item in node.body:
                if isinstance(item, ast.Assign):
                    target = item.targets[0]
                    if (isinstance(target, ast.Name)
                            and isinstance(item.value, ast.Constant)
                            and isinstance(item.value.value, str)):
                        enums[f"{node.name}.{target.id}"] = item.value.value

        if is_model:
            fields = {}
            for item in node.body:
                if not isinstance(item, ast.AnnAssign):
                    continue
                if not isinstance(item.target, ast.Name):
                    continue

                field_name = item.target.id
                frag = py_type_to_json(item.annotation)

                description = None
                default = item.value

                if isinstance(item.value, ast.Call):
                    # Field(..., description="...")
                    for kw in item.value.keywords:
                        if (kw.arg == "description"
                                and isinstance(kw.value, ast.Constant)):
                            description = kw.value.value
                    # required unless Field has non-ellipsis default
                    has_default = any(
                        kw.arg not in (None, "description", "title",
                                       "examples", "deprecated")
                        for kw in item.value.keywords
                    )
                    ellipsis_only = (
                        item.value.args
                        and isinstance(item.value.args[0], ast.Constant)
                        and item.value.args[0].value is Ellipsis
                    )
                    required = ellipsis_only or not has_default
                elif default is None:
                    required = True
                else:
                    required = False

                if description:
                    frag = dict(frag)
                    frag["description"] = description

                fields[field_name] = {"schema": frag, "required": required}

            models[node.name] = fields

    return enums, models


def resolve_python_name(expr, enums, module_name):
    """Resolve Tool name expressions (constants, enums, enum .value)."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value

    if isinstance(expr, ast.Attribute):
        # X.Y or X.Y.value
        if isinstance(expr.value, ast.Attribute) and expr.attr == "value":
            key = f"{expr.value.value.id}.{expr.value.attr}"
            return enums.get(key)
        key = f"{getattr(expr.value, 'id', '')}.{expr.attr}"
        return enums.get(key)

    return None


def safe_literal_eval(node):
    """literal_eval with f-string support (descriptions only)."""
    if isinstance(node, ast.Dict):
        return {
            safe_literal_eval(k): safe_literal_eval(v)
            for k, v in zip(node.keys, node.values)
        }
    if isinstance(node, ast.List):
        return [safe_literal_eval(elt) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(safe_literal_eval(elt) for elt in node.elts)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                expr = value.value
                if isinstance(expr, ast.Name):
                    parts.append("{%s}" % expr.id)
                elif isinstance(expr, ast.Attribute):
                    parts.append("{%s}" % expr.attr)
                else:
                    parts.append("{...}")
        return "".join(parts)
    raise ValueError("unsupported literal node")


def resolve_input_schema(expr, models):
    """Resolve inputSchema expressions to a JSON schema dict."""
    if isinstance(expr, ast.Dict):
        try:
            return safe_literal_eval(expr)
        except ValueError:
            return None

    if isinstance(expr, ast.Call):
        # Model.model_json_schema() or Model.schema()
        func = expr.func
        if isinstance(func, ast.Attribute):
            model_name = getattr(func.value, "id", None)
            if model_name in models:
                fields = models[model_name]
                properties = {
                    name: frag["schema"]
                    for name, frag in fields.items()
                }
                required = [
                    name
                    for name, frag in fields.items()
                    if frag["required"]
                ]
                schema = {
                    "type": "object",
                    "properties": properties,
                }
                if required:
                    schema["required"] = required
                return schema

    return None


def extract_python_server(server_dir, server_name, repo_key, commit):
    tools = []
    flags = []

    all_enums = {}
    all_models = {}

    py_files = sorted(server_dir.rglob("*.py"))

    parsed = []
    for path in py_files:
        if "test" in path.name or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            flags.append({
                "server": server_name,
                "file": str(path),
                "reason": f"SyntaxError: {exc}",
            })
            continue
        parsed.append((path, tree))
        enums, models = build_python_symbols(tree)
        all_enums.update(enums)
        all_models.update(models)

    for path, tree in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func = node.func
            is_tool = (
                (isinstance(func, ast.Name) and func.id == "Tool")
                or (isinstance(func, ast.Attribute) and func.attr == "Tool")
            )
            if not is_tool:
                continue

            kwargs = {
                kw.arg: kw.value
                for kw in node.keywords
                if kw.arg
            }

            name = resolve_python_name(
                kwargs.get("name"), all_enums, path.stem
            )
            description_node = kwargs.get("description")
            description = (
                description_node.value
                if isinstance(description_node, ast.Constant)
                and isinstance(description_node.value, str)
                else None
            )

            if "name" not in kwargs or name is None:
                flags.append({
                    "server": server_name,
                    "file": str(path),
                    "reason": "Tool name could not be resolved statically.",
                })
                continue

            if "description" not in kwargs:
                flags.append({
                    "server": server_name,
                    "file": str(path),
                    "reason": f"Tool {name!r} has no description keyword.",
                })
                continue

            if description is None:
                flags.append({
                    "server": server_name,
                    "file": str(path),
                    "reason": f"Tool {name!r} description is not a string literal.",
                })
                continue

            schema = resolve_input_schema(
                kwargs.get("inputSchema"), all_models
            )

            if schema is None:
                flags.append({
                    "server": server_name,
                    "file": str(path),
                    "reason": (
                        f"Tool {name!r} inputSchema uses an unsupported "
                        "expression."
                    ),
                })
                continue

            tools.append(make_record(
                name, description, schema,
                server_name, repo_key, commit,
                "python_ast",
                str(path.relative_to(server_dir)),
            ))

    return tools, flags


# ---------------------------------------------------------------------------
# Tier 2: TypeScript literal extraction
# ---------------------------------------------------------------------------

def strip_ts_comments(text):
    """Remove // and /* */ comments, preserving string contents."""
    out = []
    i = 0
    n = len(text)
    in_str = None

    while i < n:
        ch = text[i]

        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue

        if ch in ('"', "'", "`"):
            in_str = ch
            out.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def find_matching_brace(text, start):
    """Given index of '{', return index of matching '}' or -1."""
    depth = 0
    in_str = None
    i = start

    while i < len(text):
        ch = text[i]

        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue

        if ch in ('"', "'", "`"):
            in_str = ch
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return -1


def ts_object_to_json(obj_text):
    """
    Convert a TS object literal (JSON-compatible subset) to a dict.

    Char-scanner based: quotes unquoted keys, converts single-quoted
    strings, strips trailing commas. Raises ValueError on templates,
    zod expressions, or other unsupported constructs.
    """
    text = strip_ts_comments(obj_text)

    out = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch == "`":
            raise ValueError("template literal")

        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
            continue

        if ch == "'":
            j = i + 1
            buf = []
            while j < n:
                if text[j] == "\\":
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if text[j] == "'":
                    break
                buf.append(text[j])
                j += 1
            out.append(json.dumps("".join(buf)))
            i = j + 1
            continue

        if ch in "([{":
            # Quote bare identifier keys when this brace opens a mapping.
            if ch == "{":
                k = i + 1
                while k < n and text[k] in " \t\n\r,":
                    if text[k] == ",":
                        break
                    k += 1
                m = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", text[k:])
                if m and k + len(m.group()) < n:
                    after = text[k + len(m.group()):].lstrip()
                    if after.startswith(":"):
                        out.append('{"')
                        out.append(m.group())
                        out.append('"')
                        i = k + len(m.group())
                        continue
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\n\r":
                j += 1
            if j < n and text[j] in "}]":
                i = j  # trailing comma: drop it, land on closer
                continue
            out.append(ch)
            i += 1
            continue

        if re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", ch):
            m = re.match(r"[A-Za-z_$][A-Za-z0-9_$]*", text[i:])
            word = m.group()
            rest = text[i + len(word):].lstrip()
            if rest.startswith(":"):
                out.append(json.dumps(word))
                i += len(word) + (len(text[i + len(word):]) - len(rest))
                continue
            out.append(word)
            i += len(word)
            continue

        if re.match(r"[A-Za-z_$]", ch):
            raise ValueError(f"unexpected identifier-like text: {ch!r}")

        out.append(ch)
        i += 1

    result = "".join(out)

    if re.search(r"\bz\.", result) or re.search(r"jsonSchema2020", result):
        raise ValueError("zod expression inside schema")

    return json.loads(result)


def top_level_keys(obj_text):
    """Names of keys directly inside the outermost object literal."""
    keys = []
    depth = 0
    in_str = None
    i = 0
    n = len(obj_text)

    # First key: identifier immediately after the opening brace (if any).
    m0 = re.match(
        r"\s*\{\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*:", obj_text
    )
    if m0:
        keys.append(m0.group(1))

    while i < n:
        ch = obj_text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 1:
            m = re.match(
                r"\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*:", obj_text[i + 1:]
            )
            if m:
                keys.append(m.group(1))
        i += 1

    return keys


TS_STRING_DESC_RE = re.compile(
    r'[\'"]?description[\'"]?\s*:\s*'
    r'(?P<value>'
    r'"(?:[^"\\]|\\.)*"'
    r"|(?:'(?:[^'\\]|\\.)*'\s*\+?\s*)+"
    r'|`(?:[^`\\]|\\.)*`'
    r')',
)


def extract_ts_description(body):
    """Extract a description supporting quotes, + concat, and templates."""
    m = TS_STRING_DESC_RE.search(body)
    if not m:
        return None

    value = m.group("value").strip()

    if value.startswith("`"):
        inner = value[1:-1]
        if "${" in inner:
            return None
        return inner

    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]

    # Single-quoted concatenation: 'a' + 'b'
    parts = re.findall(r"'((?:[^'\\]|\\.)*)'", value)
    return "".join(p.replace("\\'", "'") for p in parts)


def extract_ts_literal_server(server_dir, server_name, repo_key, commit):
    """
    Extract tools from JSON-like Tool literals:
      const xTool: Tool = { name, description, inputSchema: {...} }
      tools: [ { name, description, inputSchema: {...} }, ... ]
    """
    tools = []
    flags = []
    seen_names = set()

    ts_files = sorted(server_dir.rglob("*.ts"))

    for path in ts_files:
        if "test" in path.name or "tests" in path.parts:
            continue

        raw = path.read_text(encoding="utf-8")
        text = strip_ts_comments(raw)
        rel = str(path.relative_to(server_dir))

        # Find every object literal that contains name+description+inputSchema.
        for match in re.finditer(r"\{", text):
            start = match.start()
            end = find_matching_brace(text, start)
            if end == -1:
                continue

            body = text[start:end + 1]
            keys = top_level_keys(body)

            if not {"name", "description", "inputSchema"}.issubset(keys):
                continue

            # Avoid re-processing nested objects: only accept if the
            # inputSchema key sits at the outermost level of this body.
            name_m = re.search(
                r'[\'"]?name[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', body
            )
            if not name_m:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": "Tool name is not a string literal.",
                })
                continue

            tool_name = name_m.group(1)

            description = extract_ts_description(body)
            if description is None:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": f"Tool {tool_name!r} description not extractable.",
                })
                continue

            schema_start = body.find("inputSchema")
            brace_rel = body.find("{", schema_start)
            if brace_rel == -1:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": f"Tool {tool_name!r} inputSchema not an object literal.",
                })
                continue

            schema_end = find_matching_brace(body, brace_rel)
            if schema_end == -1:
                continue

            schema_text = body[brace_rel:schema_end + 1]

            if re.search(r"\bz\.", schema_text):
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": (
                        f"Tool {tool_name!r} inputSchema contains zod "
                        "expressions (handled by ts_zod tier if targeted)."
                    ),
                })
                continue

            try:
                schema = ts_object_to_json(schema_text)
            except (ValueError, json.JSONDecodeError) as exc:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": (
                        f"Tool {tool_name!r} schema conversion failed: {exc}"
                    ),
                })
                continue

            if tool_name in seen_names:
                continue
            seen_names.add(tool_name)

            tools.append(make_record(
                tool_name, description, schema,
                server_name, repo_key, commit,
                "ts_literal",
                rel,
            ))

    return tools, flags


# ---------------------------------------------------------------------------
# Tier 3: TypeScript zod conversion (limited subset)
# ---------------------------------------------------------------------------

ZOD_TOKEN_RE = re.compile(
    r"""
    (?P<num>-?\d+(?:\.\d+)?)
  | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<ident>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<punct>[^\w\s"'])
  | (?P<ws>\s+)
    """,
    re.VERBOSE,
)


class ZodParser:
    """Recursive-descent parser for the supported zod subset."""

    def __init__(self, text, symbols, flags, context):
        self.tokens = []
        pos = 0
        while pos < len(text):
            m = ZOD_TOKEN_RE.match(text, pos)
            if not m:
                raise ValueError(
                    f"unexpected character {text[pos]!r} at {pos}"
                )
            pos = m.end()
            if m.lastgroup == "ws":
                continue
            self.tokens.append((m.lastgroup, m.group(), m.start()))
        self.i = 0
        self.symbols = symbols
        self.flags = flags
        self.context = context

    def peek(self):
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        return (None, None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, value):
        kind, text, pos = self.next()
        if text != value:
            raise ValueError(f"expected {value!r}, got {text!r}")
        return text

    def parse_expr(self):
        """Parse an expression, returning (schema_or_list, optional)."""
        kind, text, _ = self.peek()

        if kind == "str":
            self.next()
            value = (
                json.loads(text) if text.startswith('"') else text.strip("'")
            )
            return value, False

        if kind == "num":
            self.next()
            return float(text), False

        if kind == "ident" and text in ("true", "false", "null"):
            self.next()
            return {"true": True, "false": False, "null": None}[text], False

        if kind == "punct" and text == "[":
            return self.parse_array_literal(), False

        if kind == "ident" and text == "z":
            return self.parse_z_call()

        if kind == "ident":
            return self.parse_symbol_ref()

        if kind == "punct" and text == "{":
            return self.parse_object_literal()

        raise ValueError(f"unsupported expression start: {text!r}")

    def unwrap(self, value):
        if isinstance(value, tuple):
            return value
        return value, False

    def parse_z_call(self):
        self.expect("z")
        path = []
        while True:
            kind, text, _ = self.next()
            if kind == "punct" and text == ".":
                k2, name, _ = self.next()
                if k2 != "ident":
                    raise ValueError("expected member after z.")
                path.append(name)
                k3, nxt, _ = self.peek()
                if k3 == "punct" and nxt == "(":
                    self.next()
                    args = self.parse_args()
                    node = self.apply_z_fn(path, args)
                    return self.apply_methods(*node)
                continue
            if kind == "punct" and text == "(":
                args = self.parse_args()
                node = self.apply_z_fn(path, args)
                return self.apply_methods(*node)
            raise ValueError(f"unexpected token in z path: {text!r}")

    def parse_args(self):
        args = []
        kind, text, _ = self.peek()
        if kind == "punct" and text == ")":
            self.next()
            return args
        while True:
            kind, text, _ = self.peek()
            if kind == "punct" and text == ")":
                self.next()  # trailing comma before )
                return args
            args.append(self.parse_expr())
            kind, text, _ = self.next()
            if kind == "punct" and text == ")":
                return args
            if not (kind == "punct" and text == ","):
                raise ValueError(f"expected , or ), got {text!r}")

    def parse_array_literal(self):
        self.expect("[")
        items = []
        kind, text, _ = self.peek()
        if kind == "punct" and text == "]":
            self.next()
            return items
        while True:
            kind, text, _ = self.peek()
            if kind == "punct" and text == "]":
                self.next()  # trailing comma before ]
                break
            items.append(self.parse_expr())
            kind, text, _ = self.next()
            if kind == "punct" and text == "]":
                return items
            if not (kind == "punct" and text == ","):
                raise ValueError(f"expected , or ], got {text!r}")
        return items

    def parse_object_literal(self):
        self.expect("{")
        props = {}
        required = []

        kind, text, _ = self.peek()
        if kind == "punct" and text == "}":
            self.next()
        else:
            while True:
                kind, text, _ = self.peek()
                if kind == "punct" and text == "}":
                    self.next()  # trailing comma before }
                    break

                # Spread: ...Name or ...Name.shape
                if kind == "punct" and text == ".":
                    for _ in range(3):
                        self.expect(".")
                    k, spread_name, _ = self.next()
                    if k != "ident":
                        raise ValueError("bad spread expression")
                    # Optional .shape / .extend member
                    while True:
                        k1, t1, _ = self.peek()
                        if k1 == "punct" and t1 == ".":
                            save = self.i
                            self.next()
                            k2, member, _ = self.next()
                            if member != "shape":
                                self.i = save
                                break
                        else:
                            break
                    entry = self.resolve_name(spread_name)
                    if entry is None:
                        raise ValueError(
                            f"unresolved spread symbol {spread_name!r}"
                        )
                    spread_schema, _ = self.unwrap(entry)
                    spread_required = set(
                        spread_schema.get("required", [])
                    )
                    for pname, pschema in (
                        spread_schema.get("properties", {}).items()
                    ):
                        if pname not in props:
                            props[pname] = pschema
                            if pname in spread_required:
                                required.append(pname)
                    k, text, _ = self.next()
                    if k == "punct" and text == "}":
                        break
                    if not (k == "punct" and text == ","):
                        raise ValueError(
                            f"expected , or }} after spread, got {text!r}"
                        )
                    continue

                k, key, _ = self.next()
                if k not in ("ident", "str"):
                    raise ValueError(f"bad object key: {key!r}")
                if k == "str":
                    key = (
                        json.loads(key)
                        if key.startswith('"')
                        else key.strip("'")
                    )
                self.expect(":")
                value, optional = self.parse_expr()
                props[key] = value
                if not optional:
                    required.append(key)
                k, text, _ = self.next()
                if k == "punct" and text == "}":
                    break
                if not (k == "punct" and text == ","):
                    raise ValueError(f"expected , or }}, got {text!r}")

        schema = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        return schema, False

    def resolve_name(self, name):
        """Resolve a possibly namespaced identifier (files.Schema)."""
        if name in self.symbols:
            return self.symbols[name]
        if "." in name:
            last = name.rsplit(".", 1)[-1]
            if last in self.symbols:
                return self.symbols[last]
        return None

    def parse_symbol_ref(self):
        kind, name, pos = self.next()

        # Consume dotted path components that are not method calls
        # (e.g. files.CreateIssueSchema vs Schema.optional()).
        while True:
            k1, t1, _ = self.peek()
            if not (k1 == "punct" and t1 == "."):
                break
            save = self.i
            self.next()
            k2, part, _ = self.peek()
            if k2 != "ident":
                self.i = save
                break
            after_kind, after_text, _ = (
                self.tokens[self.i + 1]
                if self.i + 1 < len(self.tokens)
                else (None, None, None)
            )
            if after_kind == "punct" and after_text == "(":
                self.i = save
                break
            self.next()
            name = f"{name}.{part}"

        entry = self.resolve_name(name)
        if entry is None:
            raise ValueError(f"unresolved symbol {name!r}")
        schema, optional = self.unwrap(entry)

        # Method / member chain on the resolved schema.
        while True:
            k, text, _ = self.peek()
            if not (k == "punct" and text == "."):
                break
            self.next()
            k2, member, _ = self.next()

            if member == "shape":
                if schema.get("type") != "object":
                    raise ValueError(f"{name}.shape is not an object schema")
                continue

            if member == "extend":
                self.expect("(")
                arg, _ = self.parse_expr()
                self.expect(")")
                merged = dict(schema)
                base_props = dict(schema.get("properties", {}))
                base_props.update(arg.get("properties", {}))
                merged["properties"] = base_props
                base_req = set(schema.get("required", []))
                base_req.update(arg.get("required", []))
                if base_req:
                    merged["required"] = sorted(base_req)
                schema = merged
                continue

            if member == "int":
                self._skip_parens()
                if schema.get("type") == "number":
                    schema = dict(schema)
                    schema["type"] = "integer"
                continue

            if member in ("url", "email", "uuid", "datetime"):
                self._skip_parens()
                schema = dict(schema)
                schema["format"] = {
                    "url": "uri",
                    "email": "email",
                    "uuid": "uuid",
                    "datetime": "date-time",
                }[member]
                continue

            if member in ("min", "max", "length", "regex", "trim", "tap"):
                self._skip_parens()
                continue

            if member == "optional":
                self._skip_parens()
                optional = True
                continue

            if member in ("nullable", "catchall"):
                self._skip_parens()
                continue

            if member == "describe":
                desc = self._read_string_arg()
                if desc is not None:
                    schema = dict(schema)
                    schema["description"] = desc
                continue

            if member in ("default", "refine", "transform", "prefault"):
                self._skip_parens()
                continue

            if member == "or":
                self.expect("(")
                other, _ = self.parse_expr()
                self.expect(")")
                schema = {"anyOf": [schema, other]}
                continue

            raise ValueError(f"unsupported member access .{member}")

        return schema, optional

    def apply_z_fn(self, path, args):
        fn = ".".join(path)

        if fn == "string":
            return {"type": "string"}, False
        if fn == "url":
            return {"type": "string", "format": "uri"}, False
        if fn == "email":
            return {"type": "string", "format": "email"}, False
        if fn == "uuid":
            return {"type": "string", "format": "uuid"}, False
        if fn == "datetime":
            return {"type": "string", "format": "date-time"}, False
        if fn == "number":
            return {"type": "number"}, False
        if fn == "boolean":
            return {"type": "boolean"}, False
        if fn in ("any", "unknown"):
            return {}, False
        if fn == "null":
            return {"type": "null"}, False
        if fn == "literal":
            arg = args[0] if args else (None, False)
            value = arg[0] if isinstance(arg, tuple) else arg
            if isinstance(value, str):
                return {"const": value}, False
            return {}, False

        if fn == "enum":
            arg = args[0] if args else (None, False)
            values_raw = arg[0] if isinstance(arg, tuple) else arg
            if isinstance(values_raw, list):
                values = [
                    v[0] if isinstance(v, tuple) else v
                    for v in values_raw
                ]
                return {"type": "string", "enum": values}, False
            raise ValueError("z.enum argument is not an array literal")

        if fn == "coerce.number":
            return {"type": "number"}, False
        if fn == "coerce.string":
            return {"type": "string"}, False
        if fn == "coerce.boolean":
            return {"type": "boolean"}, False

        if fn == "array":
            inner = args[0] if args else ({}, False)
            item_schema, _ = self.unwrap(inner)
            return {"type": "array", "items": item_schema}, False

        if fn == "object":
            inner = args[0] if args else None
            if inner is None:
                return {"type": "object", "properties": {}}, False
            return self.unwrap(inner)

        if fn == "optional":
            inner = args[0] if args else ({}, False)
            schema, _ = self.unwrap(inner)
            return schema, True

        if fn == "record":
            inner = args[0] if args else ({}, False)
            value_schema, _ = self.unwrap(inner)
            return {
                "type": "object",
                "additionalProperties": value_schema,
            }, False

        if fn == "union":
            options = []
            for arg in args:
                schema, _ = self.unwrap(arg)
                options.append(schema)
            return {"anyOf": options}, False

        self.flags.append({
            "server": self.context,
            "file": "",
            "reason": f"unsupported zod function z.{fn}",
        })
        raise ValueError(f"unsupported zod function z.{fn}")

    def apply_methods(self, schema, optional=False):
        while True:
            kind, text, _ = self.peek()
            if not (kind == "punct" and text == "."):
                return schema, optional
            self.next()
            k, name, _ = self.next()

            if name == "optional":
                optional = True
                self._skip_parens()
            elif name == "nullable":
                self._skip_parens()
            elif name == "describe":
                desc = self._read_string_arg()
                if desc is not None:
                    schema = dict(schema)
                    schema["description"] = desc
            elif name in ("default", "refine", "transform", "prefault"):
                self._skip_parens()
            elif name == "int":
                self._skip_parens()
                if schema.get("type") == "number":
                    schema = dict(schema)
                    schema["type"] = "integer"
            elif name in ("url", "email", "uuid", "datetime"):
                self._skip_parens()
                schema = dict(schema)
                schema["format"] = {
                    "url": "uri",
                    "email": "email",
                    "uuid": "uuid",
                    "datetime": "date-time",
                }[name]
            elif name in ("min", "max", "length", "regex"):
                self._skip_parens()
            elif name == "catchall":
                self._skip_parens()
            elif name == "or":
                self.expect("(")
                other, _ = self.parse_expr()
                self.expect(")")
                schema = {"anyOf": [schema, other]}
            else:
                raise ValueError(f"unsupported method .{name}")

    def _read_string_arg(self):
        """Consume a parenthesized argument list; return first string."""
        self.expect("(")
        first_str = None
        depth = 1
        while depth > 0:
            kind, text, _ = self.next()
            if kind is None:
                raise ValueError("unterminated method arguments")
            if text == "(":
                depth += 1
            elif text == ")":
                depth -= 1
            elif kind == "str" and first_str is None and depth == 1:
                first_str = (
                    json.loads(text)
                    if text.startswith('"')
                    else text.strip("'")
                )
        return first_str

    def _skip_parens(self):
        kind, text, _ = self.peek()
        if kind == "punct" and text == "(":
            depth = 0
            while True:
                k, t, _ = self.next()
                if t == "(":
                    depth += 1
                elif t == ")":
                    depth -= 1
                    if depth == 0:
                        return


def collect_zod_symbols(texts):
    """Collect `const Name = <zod expression>` definitions (deferred parse)."""
    raw = {}

    for text in texts:
        clean = strip_ts_comments(text)
        for m in re.finditer(
            r"(?:export\s+)?const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*",
            clean,
        ):
            name = m.group(1)
            start = m.end()
            # capture expression until a top-level semicolon or newline
            # followed by export/const/end — brace-aware scan to ';'
            depth = 0
            in_str = None
            i = start
            while i < len(clean):
                ch = clean[i]
                if in_str:
                    if ch == "\\":
                        i += 2
                        continue
                    if ch == in_str:
                        in_str = None
                    i += 1
                    continue
                if ch in ('"', "'", "`"):
                    in_str = ch
                    i += 1
                    continue
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == ";" and depth == 0:
                    break
                elif ch == "\n" and depth == 0:
                    # allow continuation if next non-ws is an operator
                    rest = clean[i + 1:i + 20].lstrip()
                    if not rest.startswith((".", "+", "?", ")", ",", "|")):
                        break
                i += 1
            raw[name] = clean[start:i].strip()

    return raw


def parse_zod_symbol(name, raw_symbols, parsed_cache, symbols, flags,
                     context, resolving=None):
    """Lazily parse a zod symbol into a (schema, optional) entry."""
    if name in parsed_cache:
        return parsed_cache[name]

    resolving = resolving or set()
    if name in resolving:
        raise ValueError(f"circular zod reference at {name!r}")
    resolving.add(name)

    expr_text = raw_symbols.get(name)
    if expr_text is None:
        raise ValueError(f"undefined symbol {name!r}")

    # Pre-register for mutual recursion; parse now.
    parser = ZodParser(expr_text, symbols, flags, context)

    if expr_text.startswith("z.object") or ".object(" in expr_text[:20]:
        result = parser.parse_expr()
    elif expr_text.startswith("z."):
        result = parser.parse_expr()
    else:
        # Bare object literal (raw shape)
        result = parser.parse_expr()

    parsed_cache[name] = result
    resolving.discard(name)
    return result


def convert_enum_args(parser, args):
    pass  # enum handled inline via raw capture below


def extract_zod_server(server_dir, server_name, repo_key, commit):
    tools = []
    flags = []

    ts_files = [
        p for p in sorted(server_dir.rglob("*.ts"))
        if "test" not in p.name and "tests" not in p.parts
    ]

    texts = [p.read_text(encoding="utf-8") for p in ts_files]
    raw_symbols = collect_zod_symbols(texts)

    symbols = {}
    parsed_cache = {}

    # Scalar string consts (e.g. const RESOURCE_TYPE_TEXT = "Text" as const)
    # so z.literal(SYMBOL) references resolve.
    for name, expr in raw_symbols.items():
        if expr and expr[0] in "\"'":
            q = expr[0]
            end = expr.find(q, 1)
            if end > 0:
                symbols[name] = (expr[1:end], False)

    # First pass: parse every zod-looking symbol eagerly so references
    # resolve. Handles multiline chains like `z\n  .coerce\n  .boolean()`.
    for name in list(raw_symbols):
        expr = raw_symbols[name]
        if not re.match(r"^z\b", expr):
            continue
        try:
            result = parse_zod_symbol(
                name, raw_symbols, parsed_cache, symbols, flags, server_name
            )
            symbols[name] = result
        except ValueError as exc:
            flags.append({
                "server": server_name,
                "file": "",
                "reason": f"zod symbol {name!r} not parsed: {exc}",
            })

    # Second pass: resolve alias symbols (X = Y.extend({...}), X = Y).
    for _ in range(5):
        progressed = False
        for name in list(raw_symbols):
            if name in symbols:
                continue
            expr = raw_symbols[name]
            if expr.startswith("{") or re.match(r"^z\b", expr):
                continue
            if not re.match(r"^[A-Za-z_$][\w$]", expr):
                continue
            if any(tok in expr for tok in ("function", "=>", "if ", "return")):
                continue
            try:
                parser = ZodParser(
                    expr, symbols, flags, server_name
                )
                result = parser.parse_expr()
                symbols[name] = result
                parsed_cache[name] = result
                progressed = True
            except ValueError:
                continue
        if not progressed:
            break

    # Lazy-parse bare object-literal symbols on first reference.
    def ensure_symbol(name):
        if name in symbols:
            return symbols[name]
        expr = raw_symbols.get(name)
        if expr is None:
            return None
        if not (expr.startswith("{") or re.match(r"^z\b", expr)):
            return None
        result = parse_zod_symbol(
            name, raw_symbols, parsed_cache, symbols, flags, server_name
        )
        symbols[name] = result
        return result

    # Object-literal configs: { description, inputSchema: ... }
    for path, raw in zip(ts_files, texts):
        rel = str(path.relative_to(server_dir))
        clean = strip_ts_comments(raw)
        clean_by_index = clean

        for match in re.finditer(r"\{", clean):
            start = match.start()
            end = find_matching_brace(clean, start)
            if end == -1:
                continue
            body = clean[start:end + 1]
            keys = top_level_keys(body)

            tool_name = None
            description = None

            if {"name", "description", "inputSchema"}.issubset(keys):
                name_m = re.search(
                    r'[\'"]?name[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', body
                )
                if not name_m:
                    # name might be an identifier: const name = "..."
                    name_m = re.search(
                        r'[\'"]?name[\'"]?\s*:\s*([A-Za-z_$][\w$]*)', body
                    )
                    if name_m:
                        sym = raw_symbols.get(name_m.group(1), "")
                        lit = re.match(r'^"([^"]+)"', sym)
                        if lit:
                            tool_name = lit.group(1)
                else:
                    tool_name = name_m.group(1)

                description = extract_ts_description(body)

            if tool_name is None or description is None:
                continue

            schema_m = re.search(
                r'[\'"]?inputSchema[\'"]?\s*:\s*', body
            )
            if not schema_m:
                continue

            schema_text = body[schema_m.end():].strip()
            schema = None

            try:
                if re.match(r"^zodToJsonSchema\s*\(", schema_text):
                    inner = re.match(
                        r"^zodToJsonSchema\s*\(\s*"
                        r"([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)",
                        schema_text,
                    )
                    if inner:
                        sym = inner.group(1)
                        last = sym.rsplit(".", 1)[-1]
                        entry = (
                            symbols.get(sym)
                            or symbols.get(last)
                            or parse_zod_symbol(
                                last, raw_symbols, parsed_cache,
                                symbols, flags, server_name,
                            )
                        )
                        schema, _ = (
                            entry if isinstance(entry, tuple)
                            else (entry, False)
                        )
                elif re.match(r"^[A-Za-z_$][\w$]*\.shape\s*$", schema_text.strip()):
                    sym = schema_text.strip().split(".")[0]
                    entry = symbols.get(sym)
                    if entry and isinstance(entry, tuple):
                        schema = entry[0]
                    elif entry:
                        schema = entry
                elif re.match(r"^z\b", schema_text):
                    parser = ZodParser(
                        schema_text, symbols, flags, server_name
                    )
                    parsed = parser.parse_expr()
                    schema = (
                        parsed[0] if isinstance(parsed, tuple) else parsed
                    )
                elif re.match(r"^[A-Za-z_$][\w$]*", schema_text):
                    sym = re.match(
                        r"^([A-Za-z_$][\w$]*)", schema_text
                    ).group(1)
                    entry = symbols.get(sym) or parse_zod_symbol(
                        sym, raw_symbols, parsed_cache, symbols,
                        flags, server_name,
                    )
                    schema = entry[0] if isinstance(entry, tuple) else entry
                elif schema_text.startswith("{"):
                    # raw shape or z.object literal
                    brace_end = find_matching_brace(schema_text, 0)
                    fragment = schema_text[:brace_end + 1]
                    parser = ZodParser(
                        fragment, symbols, flags, server_name
                    )
                    parsed = parser.parse_expr()
                    schema = (
                        parsed[0] if isinstance(parsed, tuple) else parsed
                    )
            except ValueError as exc:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": (
                        f"Tool {tool_name!r} inputSchema conversion "
                        f"failed: {exc}"
                    ),
                })
                continue

            if schema is None:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": f"Tool {tool_name!r} inputSchema unresolved.",
                })
                continue

            tools.append(make_record(
                tool_name, description, schema,
                server_name, repo_key, commit,
                "ts_zod",
                rel,
            ))

    # registerTool("name", { description, inputSchema }, handler)
    for path, raw in zip(ts_files, texts):
        rel = str(path.relative_to(server_dir))
        clean = strip_ts_comments(raw)

        for m in re.finditer(
            r'registerTool\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*', clean
        ):
            tool_name = m.group(1)
            start = m.end()
            if start >= len(clean) or clean[start] != "{":
                continue
            end = find_matching_brace(clean, start)
            if end == -1:
                continue
            body = clean[start:end + 1]

            description = extract_ts_description(body)
            if description is None:
                continue

            schema_m = re.search(
                r'[\'"]?inputSchema[\'"]?\s*:\s*', body
            )
            if not schema_m:
                continue

            schema_text = body[schema_m.end():].strip()
            try:
                brace_end = find_matching_brace(schema_text, 0)
                fragment = schema_text[:brace_end + 1]
                parser = ZodParser(fragment, symbols, flags, server_name)
                parsed = parser.parse_expr()
                schema = parsed[0] if isinstance(parsed, tuple) else parsed
            except ValueError as exc:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": (
                        f"Tool {tool_name!r} inputSchema conversion "
                        f"failed: {exc}"
                    ),
                })
                continue

            tools.append(make_record(
                tool_name, description, schema,
                server_name, repo_key, commit,
                "ts_zod",
                rel,
            ))

    # registerTool(nameIdent, configIdent, handler)  (everything pattern)
    for path, raw in zip(ts_files, texts):
        rel = str(path.relative_to(server_dir))
        clean = strip_ts_comments(raw)

        file_consts = {}
        for cm in re.finditer(
            r'(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*'
            r'["\']([^"\']+)["\']\s*;?',
            clean,
        ):
            file_consts[cm.group(1)] = cm.group(2)

        # File-local object-literal consts (config objects).
        file_obj_consts = {}
        for om in re.finditer(
            r"(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*",
            clean,
        ):
            cname = om.group(1)
            cstart = om.end()
            if cstart < len(clean) and clean[cstart] == "{":
                cend = find_matching_brace(clean, cstart)
                if cend != -1:
                    file_obj_consts[cname] = clean[cstart:cend + 1]

        for m in re.finditer(
            r"registerTool\s*\(\s*([A-Za-z_$][\w$]*)\s*,\s*"
            r"([A-Za-z_$][\w$]*)\s*[,)]",
            clean,
        ):
            name_sym, config_sym = m.group(1), m.group(2)
            tool_name = file_consts.get(name_sym)
            if not tool_name:
                lit = re.match(
                    r'^"([^"]+)"', raw_symbols.get(name_sym, "")
                )
                tool_name = lit.group(1) if lit else None
            if not tool_name:
                continue

            config_expr = file_obj_consts.get(config_sym)
            if not config_expr:
                candidate = raw_symbols.get(config_sym)
                if candidate and candidate.startswith("{"):
                    config_expr = candidate
            if not config_expr:
                continue

            description = extract_ts_description(config_expr)
            if description is None:
                continue

            schema_m = re.search(
                r'[\'"]?inputSchema[\'"]?\s*:\s*', config_expr
            )
            if not schema_m:
                continue

            schema_text = config_expr[schema_m.end():].strip()
            schema = None
            try:
                if re.match(r"^[A-Za-z_$][\w$]*", schema_text):
                    sym = re.match(
                        r"^([A-Za-z_$][\w$]*)", schema_text
                    ).group(1)
                    entry = symbols.get(sym) or parse_zod_symbol(
                        sym, raw_symbols, parsed_cache, symbols,
                        flags, server_name,
                    )
                    schema = entry[0] if isinstance(entry, tuple) else entry
                else:
                    brace_end = find_matching_brace(schema_text, 0)
                    fragment = schema_text[:brace_end + 1]
                    parser = ZodParser(
                        fragment, symbols, flags, server_name
                    )
                    parsed = parser.parse_expr()
                    schema = (
                        parsed[0] if isinstance(parsed, tuple) else parsed
                    )
            except ValueError as exc:
                flags.append({
                    "server": server_name,
                    "file": rel,
                    "reason": (
                        f"Tool {tool_name!r} inputSchema conversion "
                        f"failed: {exc}"
                    ),
                })
                continue

            tools.append(make_record(
                tool_name, description, schema,
                server_name, repo_key, commit,
                "ts_zod",
                rel,
            ))

    # Deduplicate by name (keep first).
    seen = set()
    unique = []
    for tool in tools:
        if tool["name"] in seen:
            continue
        seen.add(tool["name"])
        unique.append(tool)

    return unique, flags


# ---------------------------------------------------------------------------
# Validation and output
# ---------------------------------------------------------------------------

def validate_tools(tools):
    errors = []
    seen = {}

    for tool in tools:
        name = tool.get("name")
        if not name or not isinstance(name, str):
            errors.append("Tool with missing/invalid name.")
            continue

        key = (tool.get("server"), name)
        if key in seen:
            errors.append(
                f"Duplicate tool name {name!r} in server "
                f"{tool.get('server')!r}."
            )
        seen[key] = tool

        if not tool.get("description"):
            errors.append(f"{name}: missing description.")

        schema = tool.get("inputSchema")
        if not isinstance(schema, dict):
            errors.append(f"{name}: inputSchema is not an object.")
            continue

        if schema.get("type") not in (None, "object"):
            errors.append(f"{name}: inputSchema type is not object.")

        props = schema.get("properties", {})
        if not isinstance(props, dict):
            errors.append(f"{name}: properties is not an object.")

        required = schema.get("required", [])
        if required and isinstance(required, list):
            unknown = set(required) - set(props)
            if unknown:
                errors.append(
                    f"{name}: required fields missing from properties: "
                    f"{sorted(unknown)}"
                )

    return errors


# ---------------------------------------------------------------------------
# Output safety: never destroy an existing dataset after a failed extraction
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_BLOCKED = 2


def check_output_safety(tools, missing_directories):
    """
    Return an error message when output files must NOT be written.

    Output is blocked when:
    - any expected source server directory is missing, or
    - the extraction produced zero tools.

    Returns None when it is safe to write.
    """
    if missing_directories:
        listed = ", ".join(sorted(missing_directories))
        return (
            "EXTRACTION BLOCKED: source server directories are missing: "
            f"{listed}. Existing output files were NOT modified."
        )

    if not tools:
        return (
            "EXTRACTION BLOCKED: zero tools were extracted. "
            "Existing output files were NOT modified."
        )

    return None


def write_json_atomic(path, payload):
    """
    Write JSON through a temporary file and atomically replace `path`.

    The destination is only ever touched by `os.replace`, so an
    interrupted write can never leave a truncated output file.
    The temporary file is created in the same directory (same
    filesystem) and is removed if writing fails.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_name(path.name + ".tmp")

    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clone-root",
        type=Path,
        default=DEFAULT_CLONE_ROOT,
        help="Directory containing cloned repos.",
    )
    args = parser.parse_args(argv)

    tools = []
    all_flags = []
    server_stats = []
    missing_directories = []

    for server_name, repo_key, rel_path, tier in SERVER_TARGETS:
        repo_dir = args.clone_root / REPOS[repo_key]["dir"]
        server_dir = repo_dir / rel_path

        if not server_dir.exists():
            all_flags.append({
                "server": server_name,
                "file": rel_path,
                "reason": "server directory not found",
            })
            missing_directories.append(f"{server_name} ({rel_path})")
            print(f"{server_name:20s} SKIPPED (directory not found)")
            continue

        commit = get_commit(repo_dir)

        if tier == "python":
            extracted, flags = extract_python_server(
                server_dir, server_name, repo_key, commit
            )
        elif tier == "ts_literal":
            extracted, flags = extract_ts_literal_server(
                server_dir, server_name, repo_key, commit
            )
        elif tier == "ts_zod":
            extracted, flags = extract_zod_server(
                server_dir, server_name, repo_key, commit
            )
        else:
            continue

        tools.extend(extracted)
        all_flags.extend(flags)
        server_stats.append({
            "server": server_name,
            "tier": tier,
            "tools": len(extracted),
            "flags": len(flags),
            "commit": commit,
        })

        print(
            f"{server_name:20s} tier={tier:10s} "
            f"tools={len(extracted):3d} flags={len(flags)}"
        )

    validation_errors = validate_tools(tools)

    # Safety gate: refuse to touch existing outputs after a failed extraction.
    safety_error = check_output_safety(tools, missing_directories)
    if safety_error is not None:
        print("\n" + "=" * 55)
        print(safety_error)
        print("=" * 55)
        if missing_directories:
            print(f"Missing directories: {len(missing_directories)}")
        return EXIT_BLOCKED

    OUTPUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    write_json_atomic(
        OUTPUT_RAW, {"tools": tools, "count": len(tools)}
    )

    report = {
        "total_tools": len(tools),
        "server_stats": server_stats,
        "validation_errors": validation_errors,
        "extraction_flags": all_flags,
    }

    write_json_atomic(OUTPUT_REPORT, report)

    print("\n" + "=" * 55)
    print("EXTRACTION SUMMARY")
    print("=" * 55)
    print(f"Total tools extracted: {len(tools)}")
    print(f"Validation errors:     {len(validation_errors)}")
    print(f"Extraction flags:      {len(all_flags)}")
    print(f"\nRaw data:\n  {OUTPUT_RAW}")
    print(f"Report:\n  {OUTPUT_REPORT}")

    if validation_errors:
        print("\nValidation errors:")
        for err in validation_errors[:20]:
            print(f"  - {err}")

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
