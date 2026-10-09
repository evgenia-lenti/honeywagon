"""Read which packages a project depends on, and where each one is declared."""

import re
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from honeywagon.datafiles import load_data
from honeywagon.files import Project, ProjectFile
from honeywagon.models import NotChecked

if TYPE_CHECKING:
    from honeywagon.capability.config_files import McpServer

PYPI = "PyPI"
NPM = "npm"

PYPROJECT_FILE = "pyproject.toml"
REQUIREMENTS_FILE = re.compile(r"^requirements[\w.-]*\.txt$")
# A requirement: the name, optional extras in brackets, then the version rule.
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")
# The only rule that names one version: ==1.2.3, with no wildcard.
EXACT_VERSION = re.compile(r"^===?\s*([A-Za-z0-9][A-Za-z0-9._+!-]*)$")
NPM_VERSION = re.compile(r"^\d+(\.\d+)*([-+][0-9A-Za-z.+-]+)?$")
EXECUTABLE_SUFFIX = re.compile(r"\.(cmd|exe|bat)$", re.IGNORECASE)


@dataclass(frozen=True)
class Dependency:
    """One declared dependency. No version means that no exact one is named."""

    ecosystem: str
    name: str
    version: str | None
    file: str
    line: int

    @property
    def package(self) -> tuple[str, str, str]:
        """What a lookup is asked about: registry, name and version."""
        return (self.ecosystem, self.name, self.version or "")

    @property
    def label(self) -> str:
        return f"{self.name} {self.version}" if self.version else self.name


def _pypi_name(name: str) -> str:
    """Write a Python package name the way the registry does."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement(text: str) -> tuple[str, str | None] | None:
    """Split one requirement into name and exact version, if it has one."""
    text = text.split(" #")[0].strip()
    is_bare_address = "://" in text and " @ " not in text
    if not text or text.startswith(("#", "-")) or is_bare_address:
        return None
    match = REQUIREMENT.match(text)
    if match is None:
        return None
    rule = match.group(2).split(";")[0].strip()
    exact = EXACT_VERSION.match(rule)
    version = exact.group(1) if exact and "*" not in rule else None
    return _pypi_name(match.group(1)), version


def _from_requirements(file: ProjectFile) -> Iterator[Dependency]:
    for number, line in enumerate(file.lines, start=1):
        parsed = _requirement(line)
        if parsed:
            yield Dependency(PYPI, parsed[0], parsed[1], file.path, number)


def _from_pyproject(file: ProjectFile) -> Iterator[Dependency | NotChecked]:
    try:
        data: dict[str, Any] = tomllib.loads(file.text)
    except tomllib.TOMLDecodeError:
        yield NotChecked(file.path, "invalid_toml")
        return
    project = data.get("project")
    if not isinstance(project, dict):
        return
    optional = project.get("optional-dependencies")
    groups = [project.get("dependencies")]
    if isinstance(optional, dict):
        groups.extend(optional.values())
    for group in groups:
        for requirement in group if isinstance(group, list) else []:
            parsed = _requirement(requirement) if isinstance(requirement, str) else None
            if parsed:
                line = file.find_line(requirement) or 1
                yield Dependency(PYPI, parsed[0], parsed[1], file.path, line)


def launched_package(server: "McpServer") -> tuple[str, str] | None:
    """Return the package that a launcher such as npx downloads and runs, and
    the registry it comes from."""
    rules = load_data("dependencies.toml")
    command = EXECUTABLE_SUFFIX.sub("", (server.command or "").rsplit("/", 1)[-1])
    ecosystem = rules["launchers"].get(command)
    if ecosystem is None:
        return None
    for argument in server.args:
        if not argument.startswith("-") and argument not in rules["subcommands"]:
            return argument, ecosystem
    return None


def split_version(package: str) -> tuple[str, str | None]:
    """Split name@1.2.3 or name==1.2.3 into the name and the version.

    A scoped npm name starts with @, which is not the version sign.
    """
    if "==" in package:
        name, _, version = package.partition("==")
        return name, version or None
    name, _, version = package[1:].partition("@")
    return package[0] + name, version if version and version != "latest" else None


def _from_mcp_servers(
    project: Project, servers: Iterable["McpServer"]
) -> Iterator[Dependency]:
    for server in servers:
        launched = launched_package(server)
        if launched is None:
            continue
        package, ecosystem = launched
        name, version = split_version(package)
        if ecosystem == PYPI:
            name = _pypi_name(name.partition("[")[0])
        elif version and not NPM_VERSION.match(version):
            # A range or a tag such as ^1.2 or next names no single version.
            version = None
        file = project.file(server.file)
        line = file.find_line(package, server.line - 1) if file else None
        yield Dependency(ecosystem, name, version, server.file, line or server.line)


def read_dependencies(
    project: Project, servers: Iterable["McpServer"]
) -> Iterator[Dependency | NotChecked]:
    """Yield every dependency the project declares, in the order of its files."""
    for file in project.files:
        if REQUIREMENTS_FILE.match(file.name):
            yield from _from_requirements(file)
        elif file.name == PYPROJECT_FILE:
            yield from _from_pyproject(file)
    yield from _from_mcp_servers(project, servers)
