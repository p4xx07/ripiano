"""Find user-facing API messages so the reviewed translation catalog can be checked against source text.

Exact strings and f-string templates (placeholders numbered {0}, {1}, …) are collected from
error payloads, raised exceptions, and returned (ok, message) pairs in archive/*.py.
"""

import ast
import pathlib


def extract(root=None):
    root = pathlib.Path(root or pathlib.Path(__file__).parent)
    exact, templates = set(), set()
    def template(node):
        parts, index = [], 0
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value).replace("{", "{{").replace("}", "}}"))
            else:
                parts.append("{%d}" % index); index += 1
        return "".join(parts)

    def collect(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if " " in text and text[:1].isupper() and len(text) < 400:
                exact.add(text)
        elif isinstance(node, ast.JoinedStr):
            text = template(node)
            if " " in text and text[:1].isupper():
                templates.add(text)
        elif isinstance(node, ast.IfExp):
            collect(node.body); collect(node.orelse)

    for path in sorted(root.glob("*.py")):
        if path.name.startswith("test_") or path.name in {"msg_fixture.py", "conftest.py"}:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in ("error", "detail", "message"):
                        collect(value)
            elif isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                collect(node.exc.args[0])
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg in ("error", "message"):
                        collect(keyword.value)
            elif isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
                for element in node.value.elts:
                    collect(element)
            elif isinstance(node, ast.Return) and node.value is not None and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
                collect(node.value)
    return exact, templates
