"""Tests for searchat.core.code_extractor."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from searchat.core.code_extractor import (
    extract_code_blocks,
    _detect_language,
    _extract_python_symbols,
    _extract_js_symbols,
    _extract_symbols,
    _extract_symbols_tree_sitter,
    _node_text,
    _walk_tree,
    _dedupe_preserve_order,
)


class TestExtractCodeBlocks:
    """Tests for extract_code_blocks."""

    def test_single_fenced_block(self):
        text = "Here is code:\n```python\ndef hello():\n    pass\n```\nDone."
        blocks = extract_code_blocks(message_text=text, message_index=0, role="assistant")
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert blocks[0].language_source == "fence"
        assert blocks[0].fence_language == "python"
        assert "def hello" in blocks[0].code

    def test_multiple_blocks(self):
        text = "```python\nx = 1\n```\nand\n```javascript\nlet y = 2;\n```"
        blocks = extract_code_blocks(message_text=text, message_index=0, role="assistant")
        assert len(blocks) == 2
        assert blocks[0].language == "python"
        assert blocks[1].language == "javascript"

    def test_unfenced_block_uses_detection(self):
        text = "```\ndef greet():\n    print('hi')\n```"
        blocks = extract_code_blocks(message_text=text, message_index=0, role="assistant")
        assert len(blocks) == 1
        assert blocks[0].language_source == "detected"
        assert blocks[0].fence_language is None
        assert blocks[0].language == "python"

    def test_empty_code_block_skipped(self):
        text = "```python\n\n```"
        blocks = extract_code_blocks(message_text=text, message_index=0, role="assistant")
        assert len(blocks) == 0

    def test_block_metadata(self):
        text = "```python\nclass Foo:\n    pass\n```"
        blocks = extract_code_blocks(message_text=text, message_index=3, role="user")
        assert len(blocks) == 1
        assert blocks[0].message_index == 3
        assert blocks[0].block_index == 0
        assert blocks[0].role == "user"
        assert blocks[0].lines >= 2
        assert len(blocks[0].code_hash) == 64

    def test_no_code_blocks(self):
        text = "Just plain text without any code blocks."
        blocks = extract_code_blocks(message_text=text, message_index=0, role="user")
        assert blocks == []

    def test_symbols_extracted(self):
        text = "```python\nimport os\nfrom pathlib import Path\n\ndef greet(name):\n    pass\n\nclass Animal:\n    pass\n```"
        blocks = extract_code_blocks(message_text=text, message_index=0, role="assistant")
        assert len(blocks) == 1
        block = blocks[0]
        assert "greet" in block.functions
        assert "Animal" in block.classes
        assert "os" in block.imports or "pathlib" in block.imports


class TestDetectLanguage:
    """Tests for _detect_language."""

    def test_sql(self):
        assert _detect_language("SELECT * FROM users") == "sql"
        assert _detect_language("INSERT INTO table") == "sql"
        assert _detect_language("CREATE TABLE foo (id int)") == "sql"

    def test_python(self):
        assert _detect_language("def greet():\n    pass") == "python"
        assert _detect_language("import os\nfrom pathlib import Path") == "python"
        assert _detect_language("class Foo:\n    pass") == "python"
        assert _detect_language('if __name__ == "__main__":') == "python"

    def test_javascript(self):
        assert _detect_language("function greet() {}") == "javascript"
        assert _detect_language("const x = 1;") == "javascript"
        assert _detect_language("console.log('hi')") == "javascript"
        assert _detect_language("let x = () => {}") == "javascript"

    def test_typescript(self):
        assert _detect_language("const x = 1;\ninterface Foo {\n  bar: string;\n}") == "typescript"

    def test_bash(self):
        assert _detect_language("#!/bin/bash\necho hello") == "bash"
        assert _detect_language("export PATH=/usr/bin") == "bash"
        assert _detect_language("echo ${HOME}/data") == "bash"

    def test_json(self):
        assert _detect_language('{"key": "value"}') == "json"

    def test_html(self):
        assert _detect_language("<html><body><div>hi</div></body></html>") == "html"

    def test_css(self):
        assert _detect_language("body { color: red; }") == "css"

    def test_go(self):
        assert _detect_language("package main\nfunc main() {}") == "go"

    def test_rust(self):
        # Use `fn ` which triggers Rust without hitting JS `let ` first
        assert _detect_language("fn main() {\n    println!(\"hello\");\n}") == "rust"

    def test_java(self):
        # `System.out.println` triggers Java without `class ` triggering Python first
        assert _detect_language('System.out.println("hello");') == "java"

    def test_cpp(self):
        assert _detect_language("#include <iostream>\nint main() {}") == "cpp"

    def test_plaintext_fallback(self):
        assert _detect_language("Just some random text here.") == "plaintext"


class TestExtractPythonSymbols:
    """Tests for _extract_python_symbols."""

    def test_functions_and_classes(self):
        code = "def greet():\n    pass\n\nclass Animal:\n    def speak(self):\n        pass"
        functions, classes, imports = _extract_python_symbols(code)
        assert "greet" in functions
        assert "speak" in functions
        assert "Animal" in classes

    def test_imports(self):
        code = "import os\nimport sys\nfrom pathlib import Path\nfrom collections import defaultdict"
        _, _, imports = _extract_python_symbols(code)
        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "collections" in imports

    def test_import_as(self):
        code = "import numpy as np, pandas as pd"
        _, _, imports = _extract_python_symbols(code)
        assert "numpy" in imports
        assert "pandas" in imports

    def test_comments_skipped(self):
        code = "# import os\ndef real_func():\n    pass"
        functions, _, imports = _extract_python_symbols(code)
        assert "real_func" in functions
        assert "os" not in imports


class TestExtractJsSymbols:
    """Tests for _extract_js_symbols."""

    def test_function_declarations(self):
        code = "function greet() {}\nexport function farewell() {}"
        functions, _, _ = _extract_js_symbols(code)
        assert "greet" in functions
        assert "farewell" in functions

    def test_arrow_functions(self):
        code = "const greet = () => {};\nlet farewell = async (name) => {}"
        functions, _, _ = _extract_js_symbols(code)
        assert "greet" in functions
        assert "farewell" in functions

    def test_classes(self):
        code = "class Animal {}\nexport class Plant {}"
        _, classes, _ = _extract_js_symbols(code)
        assert "Animal" in classes
        assert "Plant" in classes

    def test_imports(self):
        code = "import React from 'react';\nconst fs = require('fs');"
        _, _, imports = _extract_js_symbols(code)
        assert "react" in imports
        assert "fs" in imports


class TestExtractSymbols:
    """Tests for _extract_symbols dispatching."""

    def test_python_dispatch(self):
        code = "def greet():\n    pass\n\nclass Dog:\n    pass"
        functions, classes, imports = _extract_symbols(code, "python")
        assert "greet" in functions
        assert "Dog" in classes

    def test_javascript_dispatch(self):
        code = "function greet() {}\nclass Cat {}"
        functions, classes, _ = _extract_symbols(code, "javascript")
        assert "greet" in functions
        assert "Cat" in classes

    def test_typescript_dispatch(self):
        code = "function greet() {}\nclass Cat {}"
        functions, classes, _ = _extract_symbols(code, "typescript")
        assert "greet" in functions
        assert "Cat" in classes

    def test_unknown_language_returns_empty(self):
        functions, classes, imports = _extract_symbols("some code", "rust")
        assert functions == []
        assert classes == []
        assert imports == []

    def test_plaintext_returns_empty(self):
        functions, classes, imports = _extract_symbols("hello world", "plaintext")
        assert functions == []


class TestExtractSymbolsTreeSitter:
    """Tests for _extract_symbols_tree_sitter."""

    def test_unsupported_language_returns_empty_tuple(self):
        result = _extract_symbols_tree_sitter("fn main() {}", "rust")
        # Either None (tree-sitter not installed) or ([], [], []) (unsupported lang)
        if result is not None:
            assert result == ([], [], [])

    def test_python_returns_none_or_symbols(self):
        code = "def greet():\n    pass"
        result = _extract_symbols_tree_sitter(code, "python")
        # None if tree-sitter not installed, otherwise tuple
        if result is not None:
            functions, classes, imports = result
            assert isinstance(functions, list)


class TestDetectLanguageEdgeCases:
    """Additional edge case tests for _detect_language."""

    def test_json_invalid_falls_through(self):
        # Starts with { and has :, but isn't valid JSON
        result = _detect_language("{invalid: json, no: quotes}")
        # Should not be "json" — falls through to later checks
        assert result != "json"

    def test_update_sql(self):
        assert _detect_language("UPDATE users SET name='x'") == "sql"

    def test_delete_sql(self):
        assert _detect_language("DELETE FROM users WHERE id=1") == "sql"

    def test_shebang_bash(self):
        assert _detect_language("#! /usr/bin/env python3") == "bash"

    def test_type_keyword_typescript(self):
        # `const` triggers JS, then `type ` + `: ` triggers TS
        assert _detect_language("const x: number = 1;\ntype Foo = string;") == "typescript"

    def test_var_triggers_javascript(self):
        assert _detect_language("var x = 42;") == "javascript"

    def test_arrow_function_javascript(self):
        assert _detect_language("const f = (x) => x + 1") == "javascript"

    def test_go_package_and_func(self):
        assert _detect_language("package main\nfunc hello() {}") == "go"

    def test_std_cpp(self):
        assert _detect_language("std::cout << x;") == "cpp"

    def test_public_static_void_java(self):
        assert _detect_language('public static void main(String[] args) {}') == "java"


class TestDedupePreserveOrder:
    """Tests for _dedupe_preserve_order."""

    def test_removes_duplicates(self):
        assert _dedupe_preserve_order(["a", "b", "a", "c"]) == ["a", "b", "c"]

    def test_removes_empty_strings(self):
        assert _dedupe_preserve_order(["a", "", "b"]) == ["a", "b"]

    def test_empty_input(self):
        assert _dedupe_preserve_order([]) == []

    def test_preserves_order(self):
        assert _dedupe_preserve_order(["c", "a", "b"]) == ["c", "a", "b"]


class TestNodeText:
    """Tests for _node_text helper."""

    def test_extracts_text_from_node(self):
        code_bytes = b"def hello():\n    pass"
        node = MagicMock()
        node.start_byte = 4
        node.end_byte = 9
        assert _node_text(node, code_bytes) == "hello"


class TestWalkTree:
    """Tests for _walk_tree iterator."""

    def test_walks_children(self):
        child1 = MagicMock()
        child1.children = []
        child2 = MagicMock()
        child2.children = []
        root = MagicMock()
        root.children = [child1, child2]
        nodes = list(_walk_tree(root))
        assert len(nodes) == 3
        assert nodes[0] is root

    def test_no_children_attr(self):
        root = MagicMock(spec=[])
        root.children = None
        nodes = list(_walk_tree(root))
        assert len(nodes) == 1


class TestExtractSymbolsTreeSitterMocked:
    """Tests for tree-sitter code paths with mocked parser."""

    def test_returns_none_when_import_fails(self):
        """Covers line 163-164: import exception returns None."""
        with patch(
            "searchat.core.code_extractor.get_parser",
            side_effect=ImportError,
            create=True,
        ):
            # Need to simulate the import failing inside the function
            import builtins
            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "tree_sitter_languages":
                    raise ImportError("not installed")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = _extract_symbols_tree_sitter("def foo(): pass", "python")
            assert result is None

    def test_unsupported_lang_returns_empty(self):
        result = _extract_symbols_tree_sitter("some code", "ruby")
        # Either None (tree-sitter not installed) or empty tuple
        if result is not None:
            assert result == ([], [], [])

    def test_extract_symbols_merges_ts_and_regex(self, monkeypatch):
        """When tree-sitter returns results, they merge with regex."""
        mock_ts_result = (["ts_func"], ["TsClass"], ["ts_import"])
        monkeypatch.setattr(
            "searchat.core.code_extractor._extract_symbols_tree_sitter",
            lambda code, lang: mock_ts_result,
        )
        code = "def greet():\n    pass\n\nclass Dog:\n    pass"
        functions, classes, imports = _extract_symbols(code, "python")
        assert "ts_func" in functions
        assert "greet" in functions
        assert "TsClass" in classes
        assert "Dog" in classes

    def test_extract_symbols_ts_merge_javascript(self, monkeypatch):
        """Tree-sitter merge path for javascript."""
        mock_ts_result = (["ts_fn"], ["TsJsClass"], ["ts_mod"])
        monkeypatch.setattr(
            "searchat.core.code_extractor._extract_symbols_tree_sitter",
            lambda code, lang: mock_ts_result,
        )
        code = "function greet() {}\nclass Cat {}"
        functions, classes, imports = _extract_symbols(code, "javascript")
        assert "ts_fn" in functions
        assert "greet" in functions
        assert "TsJsClass" in classes
        assert "Cat" in classes

    def test_extract_symbols_ts_merge_unknown_lang(self, monkeypatch):
        """Tree-sitter returns results for unsupported regex lang."""
        mock_ts_result = (["ts_fn"], [], [])
        monkeypatch.setattr(
            "searchat.core.code_extractor._extract_symbols_tree_sitter",
            lambda code, lang: mock_ts_result,
        )
        functions, classes, imports = _extract_symbols("some code", "go")
        assert functions == ["ts_fn"]
        assert classes == []
        assert imports == []

    def test_extract_symbols_ts_merge_typescript(self, monkeypatch):
        """Tree-sitter merge path for typescript."""
        mock_ts_result = (["ts_fn"], [], ["ts_mod"])
        monkeypatch.setattr(
            "searchat.core.code_extractor._extract_symbols_tree_sitter",
            lambda code, lang: mock_ts_result,
        )
        code = "function greet() {}\nclass Cat {}"
        functions, classes, imports = _extract_symbols(code, "typescript")
        assert "ts_fn" in functions
        assert "greet" in functions
