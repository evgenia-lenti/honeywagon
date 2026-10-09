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
    `statement` is the SQL of a database call when it is written as constant
    text. `built_text` says that the SQL is text put together in code.
    """

    touch: str
    line: int
    input: str
    argument_line: int
    through_shell: bool = False
    statement: str | None = None
    built_text: bool = False

    @property
    def input_in_text(self) -> bool:
        """Say whether input of the tool is pasted into a command or a statement."""
        if self.input != INPUT_PART:
            return False
        return self.through_shell or (self.touch == "database" and self.built_text)


@dataclass(frozen=True)
class DatabaseTarget:
    """The database a tool opens: a name written in the code, or the environment
    variable it is read from. Neither means that it could not be told."""

    name: str | None = None
    variable: str | None = None


@dataclass(frozen=True)
class PythonTool:
    name: str
    file: str
    line: int
    has_inputs: bool
    effects: tuple[Effect, ...]
    databases: tuple[DatabaseTarget, ...] = ()

    @property
    def touches(self) -> tuple[str, ...]:
        touches = {effect.touch for effect in self.effects}
        if self.databases:
            touches.add("database")
        return tuple(sorted(touches))

    @property
    def boundedness(self) -> str:
        if not self.has_inputs:
            return "fixed"
        free = any(
            effect.input == INPUT_WHOLE or effect.input_in_text
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


def _text_of(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_text(node: ast.expr) -> bool:
    is_constant = _text_of(node) is not None
    return is_constant or isinstance(node, ast.JoinedStr) or _is_built_text(node)


def _is_built_text(node: ast.expr | None) -> bool:
    """Say whether an expression puts text together: f-string, +, % or format."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(value, ast.FormattedValue) for value in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mod):
        return _is_text(node.left) or _is_text(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format" and _is_text(node.func.value)
    return False


class _Inputs:
    """Tracks which names inside one tool hold the tool's input."""

    def __init__(
        self,
        function: FunctionNode,
        whole: set[str],
        bag: str | None,
        number_calls: frozenset[str],
    ):
        # `whole` names are one input value each. `bag` is the single dict that
        # an Agent SDK tool receives: an item of it is one input value.
        self.whole = set(whole)
        self.bag = bag
        self.tainted = set(whole) | ({bag} if bag else set())
        self.number_calls = number_calls
        self._follow_assignments(function)

    def _follow_assignments(self, function: FunctionNode) -> None:
        # Each entry: the names assigned, the value, and whether the names
        # become exactly that value (`=`) or only get it added (`+=`).
        assignments: list[tuple[set[str], ast.expr, bool]] = []
        for node in ast.walk(function):
            if isinstance(node, ast.Assign):
                names = {t.id for t in node.targets if isinstance(t, ast.Name)}
                assignments.append((names, node.value, True))
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                assignments.append(({node.target.id}, node.value, False))
        changed = True
        while changed:
            changed = False
            for names, value, replaces in assignments:
                if replaces and self.is_whole(value) and not names <= self.whole:
                    self.whole |= names
                    self.tainted |= names
                    changed = True
                elif self.reaches(value) and not names <= self.tainted:
                    self.tainted |= names
                    changed = True

    def _names(self, node: ast.AST | None) -> set[str]:
        """Collect the names used in an expression, except inside int() or float()."""
        names: set[str] = set()
        pending = [node] if node is not None else []
        while pending:
            current = pending.pop()
            if isinstance(current, ast.Call) and isinstance(current.func, ast.Name):
                if current.func.id in self.number_calls:
                    continue
            if isinstance(current, ast.Name):
                names.add(current.id)
            pending.extend(ast.iter_child_nodes(current))
        return names

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
        return bool(self._names(node) & self.tainted)

    def classify(self, node: ast.expr | None) -> str:
        if self.is_whole(node):
            return INPUT_WHOLE
        return INPUT_PART if self.reaches(node) else INPUT_NONE


class _Scope:
    """The values a tool can see by name: its own assignments, then the
    constants at the top of the file."""

    def __init__(
        self, function: FunctionNode, constants: dict[str, ast.expr], inputs: _Inputs
    ):
        self.constants = constants
        self.inputs = inputs
        self.assigned: dict[str, list[ast.expr]] = {}
        self.added_to: set[str] = set()
        for node in ast.walk(function):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.assigned.setdefault(target.id, []).append(node.value)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                self.added_to.add(node.target.id)

    def value(self, node: ast.expr | None) -> ast.expr | None:
        """Follow a name to the one value it stands for, when there is exactly one."""
        if not isinstance(node, ast.Name) or node.id in self.inputs.tainted:
            return node
        if node.id in self.added_to:
            return node
        values = self.assigned.get(node.id)
        if values is None:
            return self.constants.get(node.id, node)
        return values[0] if len(values) == 1 else node

    def is_built_text(self, node: ast.expr | None) -> bool:
        if isinstance(node, ast.Name):
            values = self.assigned.get(node.id, [])
            return node.id in self.added_to or any(map(_is_built_text, values))
        return _is_built_text(node)


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

    @cached_property
    def constants(self) -> dict[str, ast.expr]:
        """Map each name assigned once at the top of the file to its value."""
        assigned: dict[str, list[ast.expr]] = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, []).append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is not None:
                    assigned.setdefault(node.target.id, []).append(node.value)
        return {
            name: values[0] for name, values in assigned.items() if len(values) == 1
        }

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
        numbers = frozenset(self._calls["number_calls"])
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
                bag = parameters[0] if parameters else None
                inputs = _Inputs(function, set(), bag, numbers)
            elif isinstance(target, ast.Attribute) and target.attr == "tool":
                name = function.name
                has_inputs = bool(parameters)
                inputs = _Inputs(function, set(parameters), None, numbers)
            else:
                continue
            scope = _Scope(function, self.constants, inputs)
            return PythonTool(
                name=name,
                file=self.file.path,
                line=function.lineno,
                has_inputs=has_inputs,
                effects=tuple(self._effects(function, inputs, scope)),
                databases=tuple(self._databases(function, scope)),
            )
        return None

    def _databases(self, function: FunctionNode, scope: _Scope) -> list[DatabaseTarget]:
        """List the databases that the tool opens itself, each one once."""
        targets = []
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            if self.resolve(node.func) not in self._calls["database_connect"]:
                continue
            keywords = {k.arg: k.value for k in node.keywords if k.arg}
            argument = node.args[0] if node.args else keywords.get("database")
            targets.append(self._database(scope.value(argument)))
        return list(dict.fromkeys(targets))

    def _database(self, node: ast.expr | None) -> DatabaseTarget:
        calls = self._calls
        name = _text_of(node)
        if name is not None:
            return DatabaseTarget(name=name)
        if isinstance(node, ast.Call) and node.args:
            variable = _text_of(node.args[0])
            if variable and self.resolve(node.func) in calls["environment_reads"]:
                default = node.args[1] if len(node.args) > 1 else None
                return DatabaseTarget(name=_text_of(default), variable=variable)
        if isinstance(node, ast.Subscript):
            variable = _text_of(node.slice)
            if variable and self.resolve(node.value) == calls["environment"]:
                return DatabaseTarget(variable=variable)
        return DatabaseTarget()

    def _effects(
        self, function: FunctionNode, inputs: _Inputs, scope: _Scope
    ) -> list[Effect]:
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
                is_sql = touch == "database"
                return Effect(
                    touch=touch,
                    line=call.lineno,
                    input=inputs.classify(argument),
                    argument_line=argument.lineno if argument else call.lineno,
                    through_shell=through_shell,
                    statement=_text_of(scope.value(argument)) if is_sql else None,
                    built_text=is_sql and scope.is_built_text(argument),
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
