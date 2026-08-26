"""gCustodian MCP server: exposes Gmail (and later Photos/Drive) tools to Claude."""

from mcp.server.mcpserver import MCPServer

from gcustodian.services import gmail, thunderbird

mcp = MCPServer("gcustodian")


@mcp.tool()
def gmail_search(query: str = "", max_results: int = 10) -> list[dict]:
    """Search Gmail messages using Gmail search syntax, e.g. 'from:x is:unread'."""
    return gmail.list_messages(query=query, max_results=max_results)


@mcp.tool()
def gmail_read(message_id: str) -> dict:
    """Read the full content of one Gmail message by id."""
    return gmail.get_message(message_id)


@mcp.tool()
def gmail_label(message_id: str, add: list[str] | None = None, remove: list[str] | None = None) -> dict:
    """Add and/or remove label ids on a message. Use gmail_list_labels to find ids."""
    return gmail.modify_labels(message_id, add=add, remove=remove)


@mcp.tool()
def gmail_archive(message_id: str) -> dict:
    """Archive a message (remove it from the Inbox without deleting it)."""
    return gmail.archive_message(message_id)


@mcp.tool()
def gmail_list_labels() -> list[dict]:
    """List all Gmail labels (system and user-created) with their ids."""
    return gmail.list_labels()


@mcp.tool()
def thunderbird_index(full: bool = False) -> dict:
    """Scan the local Thunderbird archive and refresh the search index.

    Set full=True to force a full rescan; otherwise unchanged folders are
    skipped. Requires GCUSTODIAN_THUNDERBIRD_PROFILE to be set.
    """
    return thunderbird.build_index(full=full)


@mcp.tool()
def thunderbird_search(
    sender: str = "",
    subject_contains: str = "",
    folder: str = "",
    date_from: str = "",
    date_to: str = "",
    max_results: int = 20,
) -> list[dict]:
    """Search the indexed Thunderbird archive. Run thunderbird_index first.

    date_from/date_to are 'YYYY-MM-DD'. folder is an exact indexed folder
    path, e.g. 'Archives.sbd/2026.sbd/2026-08' (see thunderbird_list_folders).
    """
    return thunderbird.search(
        sender=sender,
        subject_contains=subject_contains,
        folder=folder,
        date_from=date_from,
        date_to=date_to,
        max_results=max_results,
    )


@mcp.tool()
def thunderbird_read(message_key: str) -> dict:
    """Read the full content of one indexed Thunderbird message.

    message_key comes from thunderbird_search results.
    """
    return thunderbird.read(message_key)


@mcp.tool()
def thunderbird_list_folders() -> list[dict]:
    """List indexed Thunderbird folders with message counts."""
    return thunderbird.list_folders()


@mcp.tool()
def thunderbird_missionary_report(name: str) -> dict:
    """Weekly report for a missionary's "Week N" updates, cross-referenced
    against mail GCUSTODIAN_OWNER_EMAIL sent them.

    `name` matches the indexed From header (substring, case-insensitive),
    e.g. "Jackson Webb". Run thunderbird_index first. Each week in the
    result is marked sent=True/False depending on whether the owner sent
    that missionary anything in the window between that week's update and
    the next one.
    """
    return thunderbird.missionary_report(name)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
