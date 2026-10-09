"""Read a SQL statement as text: which tables it touches, and how.

The statement is parsed and never run. This is the only module that uses
sqlglot, so the parser can be replaced without touching anything else.
"""

import logging
import re
from collections.abc import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from honeywagon.models import ALL_COLUMNS, DATA_ACTIONS, TableAccess

# sqlglot warns on the log about syntax it does not know. That case is handled here.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

# The dialect is not known, so each one is tried until the text parses.
DIALECTS = (None, "sqlite", "mysql", "postgres")
# Placeholders of the Python database drivers that are not SQL: %s, %(name)s, $1.
DRIVER_PLACEHOLDER = re.compile(r"%\(\w+\)s|%s|\$\d+")

WRITES = (exp.Insert, exp.Update, exp.Merge)
DELETES = (exp.Delete, exp.Drop, exp.TruncateTable)
SCHEMA_CHANGES = (exp.Create, exp.Alter)
# Statements that are understood and touch no table.
NO_DATA = (exp.Transaction, exp.Commit, exp.Rollback, exp.Pragma)


def _parse(text: str) -> list[exp.Expr] | None:
    text = DRIVER_PLACEHOLDER.sub("?", text)
    for dialect in DIALECTS:
        try:
            statements = sqlglot.parse(text, read=dialect)
        except (SqlglotError, RecursionError):
            continue
        return [statement for statement in statements if statement is not None]
    return None


def _table_name(table: exp.Table) -> str:
    return ".".join(part for part in (table.catalog, table.db, table.name) if part)


def _action(statement: exp.Expr) -> str | None:
    """Return what the statement does to its own table. None: it only reads."""
    if isinstance(statement, WRITES):
        return "write"
    if isinstance(statement, DELETES):
        return "delete"
    if isinstance(statement, SCHEMA_CHANGES):
        return "schema"
    return None


def _target(statement: exp.Expr) -> exp.Table | None:
    """Return the table that a statement writes, deletes or defines."""
    node = statement.args.get("this")
    if isinstance(node, exp.Table):
        return node
    found = node.find(exp.Table) if isinstance(node, exp.Expr) else None
    return found or statement.find(exp.Table)


def _target_columns(statement: exp.Expr) -> tuple[str, ...]:
    if isinstance(statement, exp.Insert):
        schema = statement.args.get("this")
        if isinstance(schema, exp.Schema):
            return tuple(column.name for column in schema.expressions)
        return (ALL_COLUMNS,)
    if isinstance(statement, exp.Update):
        return tuple(
            assignment.this.name
            for assignment in statement.expressions
            if isinstance(assignment, exp.EQ)
            and isinstance(assignment.this, exp.Column)
        )
    if isinstance(statement, DELETES):
        return (ALL_COLUMNS,)
    return ()


def _read_columns(
    statement: exp.Expr,
    tables: dict[int, str],
    reading: Iterable[exp.Table],
    only_inside_select: bool,
) -> dict[str, tuple[str, ...]]:
    """Work out the columns read from each table, where that is certain.

    With one table in the statement every column belongs to it. With more, a
    column is counted only when it names its table, and one that does not makes
    the columns of every table unknown.
    """
    names = set(tables.values())
    only_table = next(iter(names)) if len(names) == 1 else None
    # What may stand in front of a column: the name or the alias of a table.
    qualifiers: dict[str, set[str]] = {}
    for table in statement.find_all(exp.Table):
        if id(table) in tables:
            for qualifier in (table.name, table.alias):
                if qualifier:
                    qualifiers.setdefault(qualifier, set()).add(tables[id(table)])
    aliases = {alias.alias for alias in statement.find_all(exp.Alias)}
    found: dict[str, list[str]] = {tables[id(table)]: [] for table in reading}
    certain = True

    for column in statement.find_all(exp.Column):
        if only_inside_select and column.find_ancestor(exp.Select) is None:
            continue
        qualifier = column.table
        if not qualifier and column.name in aliases:
            continue
        if qualifier and qualifier not in qualifiers:
            # A column of a subquery in FROM, not of a table.
            continue
        owners = qualifiers[qualifier] if qualifier else names
        if len(owners) != 1:
            certain = False
            continue
        owner = next(iter(owners))
        if owner in found:
            found[owner].append(ALL_COLUMNS if column.is_star else column.name)
    for star in statement.find_all(exp.Star):
        if isinstance(star.parent, exp.Select):
            if only_table is None:
                certain = False
            elif only_table in found:
                found[only_table].append(ALL_COLUMNS)

    if not certain:
        return {name: () for name in found}
    return {
        name: (ALL_COLUMNS,)
        if ALL_COLUMNS in columns
        else tuple(dict.fromkeys(columns))
        for name, columns in found.items()
    }


def _accesses(statement: exp.Expr) -> list[TableAccess] | None:
    if isinstance(statement, NO_DATA):
        return []
    action = _action(statement)
    if action is None and not isinstance(statement, exp.Query):
        return None
    defined_here = {cte.alias for cte in statement.find_all(exp.CTE)}
    tables = {
        id(table): _table_name(table)
        for table in statement.find_all(exp.Table)
        if table.name and table.name not in defined_here
    }
    target = _target(statement) if action else None
    accesses = []
    if target is not None and id(target) in tables:
        accesses.append(
            TableAccess(tables[id(target)], action or "", _target_columns(statement))
        )
    reading = [
        table
        for table in statement.find_all(exp.Table)
        if id(table) in tables and table is not target
    ]
    columns = _read_columns(statement, tables, reading, target is not None)
    accesses.extend(TableAccess(name, "read", columns[name]) for name in columns)
    return accesses


def merge(accesses: Iterable[TableAccess]) -> tuple[TableAccess, ...]:
    """Join the entries of the same table and action into one."""
    merged: dict[tuple[str, str], tuple[str, ...]] = {}
    for access in accesses:
        key = (access.table, access.action)
        known = merged.get(key)
        if known is None:
            merged[key] = access.columns
        elif ALL_COLUMNS in (*known, *access.columns):
            merged[key] = (ALL_COLUMNS,)
        elif not known or not access.columns:
            # One of the statements did not show its columns.
            merged[key] = ()
        else:
            merged[key] = tuple(dict.fromkeys((*known, *access.columns)))
    ordered = sorted(merged, key=lambda key: (key[0], DATA_ACTIONS.index(key[1])))
    return tuple(
        TableAccess(table, action, merged[table, action]) for table, action in ordered
    )


def read_sql(text: str) -> tuple[TableAccess, ...] | None:
    """Return what the statements in the text touch. None: they cannot be read."""
    statements = _parse(text)
    if statements is None:
        return None
    accesses: list[TableAccess] = []
    for statement in statements:
        found = _accesses(statement)
        if found is None:
            return None
        accesses.extend(found)
    return merge(accesses)
