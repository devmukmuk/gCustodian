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
def gmail_create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: str | None = None,
) -> dict:
    """Create a Gmail draft for the user to review and send manually.

    Writes a multipart/alternative message to the user's Drafts folder: the
    plain-text `body` plus an HTML part Gmail renders and reflows to the
    window. When `html` is omitted it is derived from `body` -- blank lines
    start new paragraphs, "- " lines become bullet lists, "1."/"2." lines
    become numbered lists. Pass `html` to supply exact markup instead.

    It never sends the email automatically -- there is no send capability
    here by design. Returns the draft id and the underlying message id.
    """
    return gmail.create_draft(
        to=to, subject=subject, body=body, cc=cc, bcc=bcc, html=html
    )


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
    """Weekly contact report for a missionary, in calendar-week windows
    (not tied to any subject-line convention), cross-referenced against
    mail GCUSTODIAN_OWNER_EMAIL sent them.

    `name` matches the indexed From header (substring, case-insensitive),
    e.g. "Jackson Webb". Run thunderbird_index first. Week 1 starts from
    data/missionaries.json's "start_date" entry for that missionary's email
    if present, otherwise their earliest indexed message; add an entry
    there (and optionally "end_date") for missionaries with no metadata
    yet. Each week row is marked received=True/False and sent=True/False;
    weeks with neither are still included, marked blank.
    """
    return thunderbird.missionary_report(name)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
