"""Gmail operations backing the MCP tools in server.py."""

import base64
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as _escape
from typing import Any

from googleapiclient.discovery import build

from gcustodian.auth import get_credentials


def _client():
    return build("gmail", "v1", credentials=get_credentials())


def list_messages(query: str = "", max_results: int = 10) -> list[dict[str, Any]]:
    """Search messages using Gmail search syntax (e.g. 'from:x older_than:30d')."""
    service = _client()
    resp = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    messages = resp.get("messages", [])

    results = []
    for msg in messages:
        full = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata",
                 metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        results.append({
            "id": full["id"],
            "labelIds": full.get("labelIds", []),
            "snippet": full.get("snippet", ""),
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
        })
    return results


def get_message(message_id: str) -> dict[str, Any]:
    """Fetch full details (including body) for one message."""
    service = _client()
    full = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
    return {
        "id": full["id"],
        "labelIds": full.get("labelIds", []),
        "from": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "snippet": full.get("snippet", ""),
        "body": _extract_body(full["payload"]),
    }


def _extract_body(payload: dict[str, Any]) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


def modify_labels(message_id: str, add: list[str] | None = None, remove: list[str] | None = None) -> dict[str, Any]:
    service = _client()
    body = {"addLabelIds": add or [], "removeLabelIds": remove or []}
    return service.users().messages().modify(userId="me", id=message_id, body=body).execute()


def archive_message(message_id: str) -> dict[str, Any]:
    """Remove from Inbox without deleting."""
    return modify_labels(message_id, remove=["INBOX"])


def list_labels() -> list[dict[str, Any]]:
    service = _client()
    return service.users().labels().list(userId="me").execute().get("labels", [])


_UL_ITEM = re.compile(r"^\s*-\s+(.*)$")
_OL_ITEM = re.compile(r"^\s*\d+\.\s+(.*)$")


def _body_to_html(body: str) -> str:
    """Derive a simple HTML rendering from a plain-text body.

    Blank lines separate paragraphs. A block whose non-empty lines are all
    "- " items becomes a <ul>; all "1." / "2." items becomes an <ol>.
    Text is HTML-escaped; a single newline within a paragraph becomes <br>.
    """
    text = body.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not text.strip():
        return "<p></p>"

    html_blocks: list[str] = []
    for block in re.split(r"\n[ \t]*\n", text):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        ul_items = [m.group(1).strip() for ln in lines if (m := _UL_ITEM.match(ln))]
        ol_items = [m.group(1).strip() for ln in lines if (m := _OL_ITEM.match(ln))]

        if len(ul_items) == len(lines):
            items = "".join(f"<li>{_escape(i)}</li>" for i in ul_items)
            html_blocks.append(f"<ul>{items}</ul>")
        elif len(ol_items) == len(lines):
            items = "".join(f"<li>{_escape(i)}</li>" for i in ol_items)
            html_blocks.append(f"<ol>{items}</ol>")
        else:
            escaped = _escape(block.strip("\n"))
            html_blocks.append("<p>" + escaped.replace("\n", "<br>\n") + "</p>")

    return "\n".join(html_blocks)


def create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: str | None = None,
) -> dict[str, Any]:
    """Create a Gmail draft. Never sends -- only calls drafts.create.

    Builds a multipart/alternative message: the plain-text `body` as the
    fallback part, plus an HTML part that Gmail renders and reflows to the
    window. When `html` is omitted it is derived from `body` (see
    `_body_to_html`); pass `html` to supply exact markup.

    The draft lands in the user's Drafts folder for them to review and send
    manually. There is deliberately no send path here.
    """
    service = _client()
    message = MIMEMultipart("alternative")
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc

    html_part = html if html is not None else _body_to_html(body)
    # Least-preferred part first: Gmail renders the last (HTML) part.
    message.attach(MIMEText(body, "plain", "utf-8"))
    message.attach(MIMEText(html_part, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return {"id": draft["id"], "message_id": draft["message"]["id"]}
