from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedCodeBlock:
    message_index: int
    block_index: int
    role: str
    fence_language: str | None
    language: str
    language_source: str
    functions: list[str]
    classes: list[str]
    imports: list[str]
    code: str
    code_hash: str
    lines: int


_FENCE_PATTERN = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def extract_code_blocks(*, message_text: str, message_index: int, role: str) -> list[ExtractedCodeBlock]:
    """Extract fenced code blocks from message content.

    This matches the behavior of `/api/conversation/{id}/code`.
    """
    blocks: list[ExtractedCodeBlock] = []
    matches = _FENCE_PATTERN.findall(message_text)
    for block_index, (language, code) in enumerate(matches):
        fence_language = language.strip() if isinstance(language, str) else ""
        cleaned = (code or "").strip()
        if not cleaned:
            continue

        if fence_language:
            resolved_language = fence_language
            language_source = "fence"
            fence_value: str | None = fence_language
        else:
            resolved_language = _detect_language(cleaned)
            language_source = "detected"
            fence_value = None

        functions, classes, imports = _extract_symbols(cleaned, resolved_language)

        code_hash = hashlib.sha256(cleaned.encode("utf-8", errors="strict")).hexdigest()
        blocks.append(
            ExtractedCodeBlock(
                message_index=message_index,
                block_index=block_index,
                role=role,
                fence_language=fence_value,
                language=resolved_language or "plaintext",
                language_source=language_source,
                functions=functions,
                classes=classes,
                imports=imports,
                code=cleaned,
                code_hash=code_hash,
                lines=len(cleaned.splitlines()) or 1,
            )
        )

    return blocks


def _detect_language(code: str) -> str:
    """Detect programming language from code content."""
    code_lower = code.lower().strip()

    if any(kw in code_lower for kw in ["select ", "insert ", "update ", "delete ", "create table"]):
        return "sql"

    if any(kw in code_lower for kw in ["def ", "import ", "from ", "class ", "if __name__"]):
        return "python"

    if any(kw in code_lower for kw in ["function ", "const ", "let ", "var ", "=>", "console.log"]):
        if "interface " in code_lower or (": " in code and "type " in code_lower):
            return "typescript"
        return "javascript"

    if code.startswith("#!") or any(kw in code_lower for kw in ["#!/bin/", "echo ", "export ", "${"]):
        return "bash"

    if code.strip().startswith("{") and ":" in code:
        import json

        try:
            json.loads(code)
            return "json"
        except json.JSONDecodeError:
            pass

    if "<" in code and ">" in code and any(tag in code_lower for tag in ["<div", "<html", "<body", "<p>"]):
        return "html"

    if "{" in code and "}" in code and ":" in code and ";" in code:
        return "css"

    if any(kw in code_lower for kw in ["package ", "func ", "import ("]):
        return "go"

    if any(kw in code_lower for kw in ["fn ", "let mut", "impl ", "use "]):
        return "rust"

    if any(kw in code_lower for kw in ["public class ", "private class ", "system.out.println", "public static void"]):
        return "java"

    if any(kw in code_lower for kw in ["#include", "std::", "int main("]):
        return "cpp"

    return "plaintext"


def _extract_symbols(code: str, language: str) -> tuple[list[str], list[str], list[str]]:
    """Extract simple symbol metadata from code.

    If tree-sitter is available (optional), use it to improve accuracy and then
    merge with regex extraction to catch common patterns (e.g., JS arrow funcs).
    """
    lang = (language or "plaintext").lower()

    # Optional tree-sitter path.
    ts = _extract_symbols_tree_sitter(code, lang)
    if ts is not None:
        ts_functions, ts_classes, ts_imports = ts
        if lang == "python":
            rx_functions, rx_classes, rx_imports = _extract_python_symbols(code)
        elif lang in ("javascript", "typescript"):
            rx_functions, rx_classes, rx_imports = _extract_js_symbols(code)
        else:
            rx_functions, rx_classes, rx_imports = ([], [], [])

        return (
            _dedupe_preserve_order([*ts_functions, *rx_functions]),
            _dedupe_preserve_order([*ts_classes, *rx_classes]),
            _dedupe_preserve_order([*ts_imports, *rx_imports]),
        )

    if lang == "python":
        return _extract_python_symbols(code)
    if lang in ("javascript", "typescript"):
        return _extract_js_symbols(code)

    return [], [], []


def _extract_symbols_tree_sitter(
    code: str, language: str
) -> tuple[list[str], list[str], list[str]] | None:
    """Best-effort symbol extraction using tree-sitter.

    Returns None if tree-sitter isn't available.
    """

    try:
        from tree_sitter_languages import get_parser
    except Exception:
        return None

    lang = (language or "plaintext").lower()
    if lang not in ("python", "javascript", "typescript"):
        return ([], [], [])

    try:
        parser = get_parser(lang)
    except Exception:
        return ([], [], [])

    code_bytes = code.encode("utf-8", errors="strict")
    try:
        tree = parser.parse(code_bytes)
    except Exception:
        return ([], [], [])

    if lang == "python":
        return _extract_python_symbols_tree_sitter(tree.root_node, code_bytes)
    return _extract_js_symbols_tree_sitter(tree.root_node, code_bytes)


def _node_text(node, code_bytes: bytes) -> str:
    return code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="strict")


def _walk_tree(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        # Reverse to preserve left-to-right order.
        children = getattr(node, "children", None) or []
        for child in reversed(children):
            stack.append(child)


def _extract_python_symbols_tree_sitter(root, code_bytes: bytes) -> tuple[list[str], list[str], list[str]]:
    functions: list[str] = []
    classes_raw: list[str] = []
    imports: list[str] = []

    for node in _walk_tree(root):
        if node.type == "function_definition":
            name = node.child_by_field_name("name")
            if name is not None:
                functions.append(_node_text(name, code_bytes))
        elif node.type == "class_definition":
            name = node.child_by_field_name("name")
            if name is not None:
                classes_raw.append(_node_text(name, code_bytes))
        elif node.type == "import_statement":
            # import a, b.c as d
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(_node_text(child, code_bytes))
        elif node.type == "import_from_statement":
            # from a.b import c
            module = node.child_by_field_name("module_name")
            if module is None:
                for child in node.children:
                    if child.type == "dotted_name":
                        module = child
                        break
            if module is not None:
                imports.append(_node_text(module, code_bytes))

    return (
        _dedupe_preserve_order(functions),
        _dedupe_preserve_order(classes_raw),
        _dedupe_preserve_order(imports),
    )


def _extract_js_symbols_tree_sitter(root, code_bytes: bytes) -> tuple[list[str], list[str], list[str]]:
    functions: list[str] = []
    classes_raw: list[str] = []
    imports: list[str] = []

    for node in _walk_tree(root):
        if node.type == "function_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                functions.append(_node_text(name, code_bytes))
        elif node.type == "class_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                classes_raw.append(_node_text(name, code_bytes))
        elif node.type == "import_statement":
            # import ... from "module"
            source = node.child_by_field_name("source")
            if source is not None:
                value = _node_text(source, code_bytes)
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                if value:
                    imports.append(value)

    return (
        _dedupe_preserve_order(functions),
        _dedupe_preserve_order(classes_raw),
        _dedupe_preserve_order(imports),
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_python_symbols(code: str) -> tuple[list[str], list[str], list[str]]:
    functions = re.findall(r"(?m)^\s*def\s+([A-Za-z_]\w*)\s*\(", code)
    classes_raw = re.findall(r"(?m)^\s*class\s+([A-Za-z_]\w*)\s*(?:\(|:)", code)

    imports: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m_from = re.match(r"^from\s+([A-Za-z0-9_\.]+)\s+import\s+", stripped)
        if m_from:
            imports.append(m_from.group(1))
            continue

        m_import = re.match(r"^import\s+(.+)$", stripped)
        if m_import:
            remainder = m_import.group(1)
            # Handle: import os, sys as s
            parts = [p.strip() for p in remainder.split(",") if p.strip()]
            for part in parts:
                module = part.split()[0]
                if module:
                    imports.append(module)

    return (
        _dedupe_preserve_order(functions),
        _dedupe_preserve_order(classes_raw),
        _dedupe_preserve_order(imports),
    )


def _extract_js_symbols(code: str) -> tuple[list[str], list[str], list[str]]:
    functions: list[str] = []
    functions.extend(re.findall(r"(?m)^\s*(?:export\s+)?function\s+([A-Za-z_]\w*)\s*\(", code))
    functions.extend(
        re.findall(
            r"(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:\(|function\s*\()",
            code,
        )
    )

    classes_raw = re.findall(r"(?m)^\s*(?:export\s+)?class\s+([A-Za-z_]\w*)\b", code)

    imports: list[str] = []
    imports.extend(re.findall(r"(?m)^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", code))
    imports.extend(re.findall(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", code))

    return (
        _dedupe_preserve_order(functions),
        _dedupe_preserve_order(classes_raw),
        _dedupe_preserve_order(imports),
    )
