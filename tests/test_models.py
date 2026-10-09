from honeywagon.models import finding_id


def test_finding_id_is_the_check_and_a_short_hash() -> None:
    identifier = finding_id("perm-broad-bash", "SKILL.md", "allowed-tools: Bash")

    check_id, digest = identifier.split(":")
    assert check_id == "perm-broad-bash"
    assert len(digest) == 6


def test_finding_id_ignores_extra_spaces_in_the_evidence() -> None:
    plain = finding_id("perm-broad-bash", "SKILL.md", "allowed-tools: Bash")
    spaced = finding_id("perm-broad-bash", "SKILL.md", "  allowed-tools:   Bash ")

    assert plain == spaced


def test_finding_id_changes_with_the_file_and_with_the_evidence() -> None:
    base = finding_id("perm-broad-bash", "SKILL.md", "allowed-tools: Bash")

    assert base != finding_id(
        "perm-broad-bash", "other/SKILL.md", "allowed-tools: Bash"
    )
    assert base != finding_id("perm-broad-bash", "SKILL.md", "allowed-tools: Bash(*)")
