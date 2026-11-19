"""Find user-facing API messages so the reviewed translation catalog can be checked against source text.

Exact strings and f-string templates (placeholders numbered {0}, {1}, …) are collected from
error payloads, `*_ERRORS` message tables, raised exceptions, and returned (ok, message) pairs in archive/*.py.
"""

import ast
import pathlib


def _template(node):
    """An f-string as a template with numbered placeholders: f"Tag {name} not found" -> "Tag {0} not found"."""
    parts, index = [], 0
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value).replace("{", "{{").replace("}", "}}"))
        else:
            parts.append("{%d}" % index); index += 1
    return "".join(parts)


def extract(root=None):
    root = pathlib.Path(root or pathlib.Path(__file__).parent)
    exact, templates = set(), set()
    template = _template

    def variants(node):
        # f"This {'a' if x else 'b'} …" also yields each full sentence, so it can be translated whole.
        texts = [""]
        for value in node.values:
            if isinstance(value, ast.Constant):
                options = [str(value.value)]
            elif (isinstance(value, ast.FormattedValue) and value.conversion == -1 and value.format_spec is None
                  and isinstance(value.value, ast.IfExp)
                  and all(isinstance(part, ast.Constant) and isinstance(part.value, str) for part in (value.value.body, value.value.orelse))):
                options = [value.value.body.value, value.value.orelse.value]
            else:
                return []
            texts = [text + option for text in texts for option in options]
        return texts

    def collect(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if " " in text and text[:1].isupper() and len(text) < 400:
                exact.add(text)
        elif isinstance(node, ast.JoinedStr):
            text = template(node)
            if " " in text and (text[:1].isupper() or text.startswith("{0} ")):
                templates.add(text)
                for variant in variants(node):
                    collect(ast.Constant(variant))
        elif isinstance(node, ast.IfExp):
            collect(node.body); collect(node.orelse)

    for path in sorted(root.glob("*.py")):
        if path.name.startswith("test_") or path.name in {"msg_fixture.py", "conftest.py"}:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                    and any(isinstance(target, ast.Name) and target.id.isupper() for target in node.targets)):
                collect(node.value)  # module constants used as messages, e.g. storage.UNSUPPORTED
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                    and any(isinstance(target, ast.Name) and target.id.endswith("_ERRORS") for target in node.targets)):
                for value in node.value.values:  # module-level message tables, e.g. FILTER_ERRORS
                    collect(value)
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
