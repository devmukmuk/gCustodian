"""gCustodian MCP server: exposes Gmail (and later Photos/Drive) tools to Claude."""

from mcp.server.mcpserver import MCPServer

from gcustodian.services import gmail

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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
