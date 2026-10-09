"""Read the YAML block at the top of a Markdown file, with line numbers."""

from dataclasses import dataclass

import yaml

from honeywagon.files import ProjectFile

FENCE = "---"


class FrontmatterError(Exception):
    """The YAML block is there but cannot be parsed."""


@dataclass(frozen=True)
class Value:
    text: str
    line: int


def frontmatter_values(file: ProjectFile, key: str) -> list[Value]:
    """Return the values of one key, each with its line in the file.

    A plain value gives one entry and a YAML list gives one entry per item.
    A file without frontmatter, or without the key, gives an empty list.
    """
    lines = file.lines
    if not lines or lines[0].strip() != FENCE:
        return []
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == FENCE)
    except StopIteration:
        return []
    try:
        root = yaml.compose("\n".join(lines[1:end]), Loader=yaml.SafeLoader)
    except yaml.YAMLError as error:
        raise FrontmatterError(str(error)) from error
    if not isinstance(root, yaml.MappingNode):
        return []

    # The YAML starts on the second line of the file, and marks count from zero.
    def file_line(node: yaml.Node) -> int:
        return int(node.start_mark.line) + 2

    for key_node, value_node in root.value:
        if key_node.value != key:
            continue
        if isinstance(value_node, yaml.ScalarNode):
            return [Value(str(value_node.value), file_line(key_node))]
        if isinstance(value_node, yaml.SequenceNode):
            return [
                Value(str(item.value), file_line(item))
                for item in value_node.value
                if isinstance(item, yaml.ScalarNode)
            ]
    return []
