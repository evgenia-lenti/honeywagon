"""Read Python code without running it: tools, what they touch, agent options."""

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from honeywagon.datafiles import load_data
from honeywagon.files import ProjectFile

# How much of a command, statement or address comes from the tool's input.
INPUT_NONE = "none"
INPUT_PART = "part"
INPUT_WHOLE = "whole"

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class Effect:
    """One call inside a tool that touches something outside the program.

    `line` is where the call starts. `argument_line` is where its command,
    statement or address is written, which is a later line in a long call.
    """

    touch: str
    line: int
    input: str
    argument_line: int
    through_shell: bool = False


@dataclass(frozen=True)
class PythonTool:
    name: str
    file: str
    line: int
    has_inputs: bool
    effects: tuple[Effect, ...]

    @property
    def touches(self) -> tuple[str, ...]:
        return tuple(sorted({effect.touch for effect in self.effects}))

    @property
    def boundedness(self) -> str:
        if not self.has_inputs:
            return "fixed"
        free = any(
            effect.input == INPUT_WHOLE
            or (effect.through_shell and effect.input == INPUT_PART)
            for effect in self.effects
            if effect.touch in ("shell", "database", "network")
        )
        return "free_form" if free else "parameterized"


@dataclass(frozen=True)
class Keyword:
    value: Any
    line: int


@dataclass(frozen=True)
class AgentOptions:
    file: str
    line: int
    keywords: dict[str, Keyword]
    has_unpacked_keywords: bool
    allowed_tools: tuple[tuple[str, int], ...]


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


class _Inputs:
    """Tracks which names inside one tool hold the tool's input."""

    def __init__(self, function: FunctionNode, whole: set[str], bag: str | None):
        # `whole` names are one input value each. `bag` is the single dict that
        # an Agent SDK tool receives: an item of it is one input value.
        self.whole = set(whole)
        self.bag = bag
        self.tainted = set(whole) | ({bag} if bag else set())
        self._follow_assignments(function)

    def _follow_assignments(self, function: FunctionNode) -> None:
        assignments = [
            (node.targets, node.value)
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
        ]
        changed = True
        while changed:
            changed = False
            for targets, value in assignments:
                names = {t.id for t in targets if isinstance(t, ast.Name)}
                if self.is_whole(value) and not names <= self.whole:
                    self.whole |= names
                    self.tainted |= names
                    changed = True
                elif self.reaches(value) and not names <= self.tainted:
                    self.tainted |= names
                    changed = True

    def is_whole(self, node: ast.expr | None) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.whole
        if self.bag is None:
            return False
        if isinstance(node, ast.Subscript):
            return isinstance(node.value, ast.Name) and node.value.id == self.bag
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            return (
                node.func.attr == "get"
                and isinstance(receiver, ast.Name)
                and receiver.id == self.bag
            )
        return False

    def reaches(self, node: ast.AST | None) -> bool:
        return bool(_names(node) & self.tainted)

    def classify(self, node: ast.expr | None) -> str:
        if self.is_whole(node):
            return INPUT_WHOLE
        return INPUT_PART if self.reaches(node) else INPUT_NONE


class PythonModule:
    """One parsed Python file of the audited project."""

    def __init__(self, file: ProjectFile, tree: ast.Module):
        self.file = file
        self.tree = tree
        self._calls = load_data("python_calls.toml")

    @cached_property
    def aliases(self) -> dict[str, str]:
        """Map each imported name to the full name it stands for."""
        aliases = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        aliases[alias.asname] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        return aliases

    def resolve(self, node: ast.expr) -> str | None:
        """Return the full dotted name of what a call refers to, if it has one."""
        name = _dotted(node)
        if name is None:
            return None
        head, dot, rest = name.partition(".")
        return self.aliases.get(head, head) + dot + rest

    def calls(self, name: str) -> Iterator[ast.Call]:
        """Yield every call to the function with this full name."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and self.resolve(node.func) == name:
                yield node

    @cached_property
    def tools(self) -> tuple[PythonTool, ...]:
        tools = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                tool = self._tool(node)
                if tool:
                    tools.append(tool)
        return tuple(sorted(tools, key=lambda tool: tool.line))

    def _tool(self, function: FunctionNode) -> PythonTool | None:
        parameters = [
            argument.arg
            for argument in (
                *function.args.posonlyargs,
                *function.args.args,
                *function.args.kwonlyargs,
            )
            if argument.arg not in self._calls["ignored_parameters"]
        ]
        for decorator in function.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if self.resolve(target) == self._calls["sdk_tool_decorator"]:
                arguments = decorator.args if isinstance(decorator, ast.Call) else []
                name = function.name
                if arguments and isinstance(arguments[0], ast.Constant):
                    name = str(arguments[0].value)
                schema = arguments[2] if len(arguments) > 2 else None
                has_inputs = not (isinstance(schema, ast.Dict) and not schema.keys)
                inputs = _Inputs(function, set(), parameters[0] if parameters else None)
            elif isinstance(target, ast.Attribute) and target.attr == "tool":
                name = function.name
                has_inputs = bool(parameters)
                inputs = _Inputs(function, set(parameters), None)
            else:
                continue
            return PythonTool(
                name=name,
                file=self.file.path,
                line=function.lineno,
                has_inputs=has_inputs,
                effects=tuple(self._effects(function, inputs)),
            )
        return None

    def _effects(self, function: FunctionNode, inputs: _Inputs) -> list[Effect]:
        calls = self._calls
        effects = []
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            name = self.resolve(node.func)
            method = node.func.attr if isinstance(node.func, ast.Attribute) else None
            first = node.args[0] if node.args else None
            keywords = {k.arg: k.value for k in node.keywords if k.arg}

            def effect(
                touch: str,
                argument: ast.expr | None,
                through_shell: bool = False,
                call: ast.Call = node,
            ) -> Effect:
                return Effect(
                    touch=touch,
                    line=call.lineno,
                    input=inputs.classify(argument),
                    argument_line=argument.lineno if argument else call.lineno,
                    through_shell=through_shell,
                )

            if name in calls["shell"]:
                shell = keywords.get("shell")
                through_shell = name in calls["always_shell"] or (
                    isinstance(shell, ast.Constant) and shell.value is True
                )
                command = first or keywords.get("args")
                effects.append(effect("shell", command, through_shell))
            elif name in calls["network"]:
                effects.append(effect("network", first or keywords.get("url")))
            elif method in calls["database_methods"]:
                effects.append(effect("database", first))
            elif name == "open":
                mode = node.args[1] if len(node.args) > 1 else keywords.get("mode")
                writes = isinstance(mode, ast.Constant) and any(
                    letter in str(mode.value) for letter in "wax+"
                )
                touch = "filesystem_write" if writes else "filesystem_read"
                effects.append(effect(touch, first))
            elif method in calls["read_methods"] or method in calls["write_methods"]:
                assert isinstance(node.func, ast.Attribute)
                reads = method in calls["read_methods"]
                touch = "filesystem_read" if reads else "filesystem_write"
                effects.append(effect(touch, node.func.value))
        return sorted(effects, key=lambda effect: (effect.line, effect.touch))

    @cached_property
    def agent_options(self) -> tuple[AgentOptions, ...]:
        found = []
        for call in self.calls(self._calls["agent_options"]):
            keywords = {}
            allowed_tools: list[tuple[str, int]] = []
            for keyword in call.keywords:
                if keyword.arg is None:
                    continue
                value = keyword.value
                constant = value.value if isinstance(value, ast.Constant) else None
                keywords[keyword.arg] = Keyword(constant, value.lineno)
                if keyword.arg == "allowed_tools" and isinstance(
                    value, ast.List | ast.Tuple
                ):
                    allowed_tools = [
                        (str(item.value), item.lineno)
                        for item in value.elts
                        if isinstance(item, ast.Constant)
                    ]
            found.append(
                AgentOptions(
                    file=self.file.path,
                    line=call.lineno,
                    keywords=keywords,
                    has_unpacked_keywords=any(k.arg is None for k in call.keywords),
                    allowed_tools=tuple(allowed_tools),
                )
            )
        return tuple(sorted(found, key=lambda options: options.line))


def parse_python(file: ProjectFile) -> PythonModule | None:
    """Parse one file. A file that cannot be parsed gives None."""
    try:
        return PythonModule(file, ast.parse(file.text))
    except (SyntaxError, ValueError):
        return None
