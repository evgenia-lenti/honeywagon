"""Ask the OSV database which known security problems a package version has.

This is the only place where the tool uses the network, and it happens only
when the person who runs the audit asks for it. What is sent is the name of
the registry, the name of the package and its version. Nothing else.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
TIMEOUT_SECONDS = 10
MAX_PAGES = 5
# The ratings the database gives, the most serious first.
RATINGS = ("CRITICAL", "HIGH", "MODERATE", "LOW")
# Which id names a problem when it has several: the first prefix that is found.
PREFERRED_IDS = ("GHSA-", "CVE-")

Package = tuple[str, str, str]


@dataclass(frozen=True)
class Advisory:
    """One published security problem, as the database describes it."""

    id: str
    rating: str | None
    fixed_in: tuple[str, ...]


# Returns the advisories of one package version. None means the lookup failed.
Lookup = Callable[[str, str, str], tuple[Advisory, ...] | None]


def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    """Order versions by their numbers, so that 2.9 comes before 2.10."""
    parts = version.replace("-", ".").split(".")
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)


def _same_name(left: str, right: str) -> bool:
    def normalise(name: str) -> str:
        return name.lower().replace("_", "-").replace(".", "-")

    return normalise(left) == normalise(right)


def _fixed_versions(record: Mapping[str, Any], ecosystem: str, name: str) -> set[str]:
    fixed = set()
    for affected in record.get("affected", []):
        package = affected.get("package", {})
        if package.get("ecosystem") != ecosystem:
            continue
        if not _same_name(str(package.get("name", "")), name):
            continue
        for version_range in affected.get("ranges", []):
            for event in version_range.get("events", []):
                if "fixed" in event:
                    fixed.add(str(event["fixed"]))
    return fixed


def advisories_from(
    records: Iterable[Mapping[str, Any]], ecosystem: str, name: str
) -> tuple[Advisory, ...]:
    """Turn the records of the database into advisories, each problem once.

    The database lists the same problem under several ids, for example as
    GHSA-... and as PYSEC-..., each naming the others as aliases.
    """
    groups: list[tuple[set[str], list[Mapping[str, Any]]]] = []
    for record in records:
        ids = {str(record["id"]), *map(str, record.get("aliases", []))}
        members = [record]
        for group in [group for group in groups if group[0] & ids]:
            ids |= group[0]
            members += group[1]
            groups.remove(group)
        groups.append((ids, members))

    advisories = []
    for _, members in groups:
        own_ids = sorted(str(member["id"]) for member in members)
        preferred = [
            i for prefix in PREFERRED_IDS for i in own_ids if i.startswith(prefix)
        ]
        ratings = {
            str(member.get("database_specific", {}).get("severity", "")).upper()
            for member in members
        }
        fixed: set[str] = set()
        for member in members:
            fixed |= _fixed_versions(member, ecosystem, name)
        advisories.append(
            Advisory(
                id=(preferred or own_ids)[0],
                rating=next((rating for rating in RATINGS if rating in ratings), None),
                fixed_in=tuple(sorted(fixed, key=_version_key)),
            )
        )
    return tuple(sorted(advisories, key=lambda advisory: advisory.id))


def osv_lookup(ecosystem: str, name: str, version: str) -> tuple[Advisory, ...] | None:
    """Ask the OSV database about one package version, over the network."""
    query: dict[str, Any] = {
        "package": {"ecosystem": ecosystem, "name": name},
        "version": version,
    }
    records: list[Mapping[str, Any]] = []
    for _ in range(MAX_PAGES):
        request = urllib.request.Request(
            OSV_QUERY_URL,
            data=json.dumps(query).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                answer = json.load(response)
        except (OSError, ValueError):
            # No network, a timeout, an error status, or an answer that is not JSON.
            return None
        if not isinstance(answer, dict):
            return None
        records.extend(answer.get("vulns", []))
        token = answer.get("next_page_token")
        if not token:
            return advisories_from(records, ecosystem, name)
        query["page_token"] = token
    return None


def look_up_all(
    packages: Iterable[Package], lookup: Lookup
) -> dict[Package, tuple[Advisory, ...] | None]:
    """Look each package version up once, in a fixed order."""
    return {package: lookup(*package) for package in sorted(set(packages))}
