"""Work out which data a tool written in Python reaches, from the SQL it runs."""

from honeywagon.capability.python_code import INPUT_WHOLE, PythonTool
from honeywagon.capability.sql import merge, read_sql
from honeywagon.guard.redact import safe_evidence
from honeywagon.models import DataScope, TableAccess


def _status(takes_any: bool, read: int, not_read: int) -> str:
    if takes_any:
        return "any"
    if read and not not_read:
        return "known"
    return "partial" if read else "unknown"


def data_scope(tool: PythonTool) -> DataScope:
    """Summarise the database use of one tool. Names in it are safe to show."""
    statements = [effect for effect in tool.effects if effect.touch == "database"]
    if not statements and not tool.databases:
        return DataScope("none")

    takes_any = False
    read = not_read = 0
    accesses: list[TableAccess] = []
    for effect in statements:
        if effect.input == INPUT_WHOLE or effect.input_in_text:
            # The statement, or a piece of it, is whatever the caller sends.
            takes_any = True
            continue
        found = read_sql(effect.statement) if effect.statement is not None else None
        if found is None:
            not_read += 1
        else:
            read += 1
            accesses.extend(found)

    target = tool.databases[0] if len(tool.databases) == 1 else None
    return DataScope(
        status=_status(takes_any, read, not_read),
        database=safe_evidence(target.name) if target and target.name else None,
        database_variable=(
            safe_evidence(target.variable) if target and target.variable else None
        ),
        tables=tuple(
            TableAccess(
                table=safe_evidence(access.table),
                action=access.action,
                columns=tuple(safe_evidence(column) for column in access.columns),
            )
            for access in merge(accesses)
        ),
    )
