"""Gmail operations backing the MCP tools in server.py."""

import base64
from email.mime.text import MIMEText
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
