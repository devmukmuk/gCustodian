"""Read-only access to a local Thunderbird "Local Folders" mbox archive.

The archive is treated as foreign, live data -- Thunderbird may be running
and holding these files. Nothing in this module ever writes back into the
Thunderbird profile; the search index it builds is entirely separate state
owned by gCustodian (see INDEX_DB_PATH).
"""

import email
import email.policy
import html
import mailbox
import os
import re
import sqlite3
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INDEX_DB_PATH = REPO_ROOT / "data" / "thunderbird_index.sqlite"

_SKIP_SUFFIXES = {".msf", ".dat"}
_MESSAGE_FACTORY = lambda f: email.message_from_binary_file(f, policy=email.policy.default)  # noqa: E731


def _profile_root() -> Path:
    value = os.environ.get("GCUSTODIAN_THUNDERBIRD_PROFILE")
    if not value:
        raise RuntimeError(
            "GCUSTODIAN_THUNDERBIRD_PROFILE is not set. Point it at the "
            "Thunderbird profile directory, e.g. "
            r"E:\archive\Thunderbird (the folder containing Mail\Local Folders)."
        )
    return Path(value)


def _mail_root() -> Path:
    return _profile_root() / "Mail" / "Local Folders"


def _db() -> sqlite3.Connection:
    INDEX_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(INDEX_DB_PATH))
    con.execute(
        "CREATE TABLE IF NOT EXISTS folders ("
        "path TEXT PRIMARY KEY, mtime REAL NOT NULL, size INTEGER NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "folder TEXT NOT NULL, mbox_key INTEGER NOT NULL, message_id TEXT, "
        "from_addr TEXT, subject TEXT, date_raw TEXT, date_ts REAL, "
        "snippet TEXT, PRIMARY KEY (folder, mbox_key))"
    )
    return con


def _iter_mbox_files(root: Path):
    """Yield (folder_path_str, absolute_path) for every mbox file under root."""
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            suffix = Path(name).suffix
            if suffix in _SKIP_SUFFIXES:
                continue
            abs_path = Path(dirpath) / name
            if abs_path.stat().st_size == 0:
                continue
            folder = abs_path.relative_to(root).as_posix()
            yield folder, abs_path


def _extract_snippet(msg: email.message.EmailMessage, limit: int = 200) -> str:
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        text = part.get_content()
        if part.get_content_type() == "text/html":
            text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        return " ".join(text.split())[:limit]
    except Exception:
        return ""


def _extract_body(msg: email.message.EmailMessage) -> str:
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        return part.get_content()
    except Exception:
        return ""


def _date_ts(date_raw: str | None) -> float | None:
    if not date_raw:
        return None
    try:
        return parsedate_to_datetime(date_raw).timestamp()
    except (TypeError, ValueError):
        return None


def build_index(full: bool = False) -> dict[str, Any]:
    """Scan the Thunderbird archive and refresh the local search index.

    Folders whose mtime/size haven't changed since the last run are skipped
    unless full=True.
    """
    root = _mail_root()
    con = _db()
    try:
        folders_scanned = 0
        folders_skipped = 0
        messages_indexed = 0

        for folder, abs_path in _iter_mbox_files(root):
            stat = abs_path.stat()
            if not full:
                row = con.execute(
                    "SELECT mtime, size FROM folders WHERE path = ?", (folder,)
                ).fetchone()
                if row and row[0] == stat.st_mtime and row[1] == stat.st_size:
                    folders_skipped += 1
                    continue

            mbox = mailbox.mbox(str(abs_path), factory=_MESSAGE_FACTORY)
            try:
                con.execute("DELETE FROM messages WHERE folder = ?", (folder,))
                for key, msg in mbox.items():
                    date_raw = msg.get("Date", "")
                    con.execute(
                        "INSERT INTO messages (folder, mbox_key, message_id, "
                        "from_addr, subject, date_raw, date_ts, snippet) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            folder,
                            key,
                            msg.get("Message-ID", ""),
                            msg.get("From", ""),
                            msg.get("Subject", ""),
                            date_raw,
                            _date_ts(date_raw),
                            _extract_snippet(msg),
                        ),
                    )
                    messages_indexed += 1
            finally:
                mbox.close()

            con.execute(
                "INSERT INTO folders (path, mtime, size) VALUES (?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET mtime = excluded.mtime, "
                "size = excluded.size",
                (folder, stat.st_mtime, stat.st_size),
            )
            folders_scanned += 1
            con.commit()

        return {
            "folders_scanned": folders_scanned,
            "folders_skipped": folders_skipped,
            "messages_indexed": messages_indexed,
        }
    finally:
        con.close()


def _parse_date_bound(value: str) -> float | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").timestamp()


def search(
    sender: str = "",
    subject_contains: str = "",
    folder: str = "",
    date_from: str = "",
    date_to: str = "",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search the indexed Thunderbird archive. Run thunderbird_index first."""
    clauses = []
    params: list[Any] = []

    if sender:
        clauses.append("from_addr LIKE ?")
        params.append(f"%{sender}%")
    if subject_contains:
        clauses.append("subject LIKE ?")
        params.append(f"%{subject_contains}%")
    if folder:
        clauses.append("folder = ?")
        params.append(folder)
    from_ts = _parse_date_bound(date_from)
    if from_ts is not None:
        clauses.append("date_ts >= ?")
        params.append(from_ts)
    to_ts = _parse_date_bound(date_to)
    if to_ts is not None:
        clauses.append("date_ts <= ?")
        params.append(to_ts)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = (
        f"SELECT folder, mbox_key, from_addr, subject, date_raw, snippet "
        f"FROM messages {where} ORDER BY date_ts DESC LIMIT ?"
    )
    params.append(max_results)

    con = _db()
    try:
        rows = con.execute(query, params).fetchall()
    finally:
        con.close()

    return [
        {
            "message_key": f"{row[0]}::{row[1]}",
            "folder": row[0],
            "from": row[2],
            "subject": row[3],
            "date": row[4],
            "snippet": row[5],
        }
        for row in rows
    ]


def read(message_key: str) -> dict[str, Any]:
    """Fetch full content (including body) for one indexed message."""
    folder, _, key_str = message_key.rpartition("::")
    if not folder:
        raise ValueError(f"Malformed message_key: {message_key!r}")
    mbox_key = int(key_str)

    root = _mail_root()
    abs_path = root / folder

    con = _db()
    try:
        row = con.execute(
            "SELECT mtime, size FROM folders WHERE path = ?", (folder,)
        ).fetchone()
    finally:
        con.close()

    if row is None:
        raise RuntimeError(f"Folder {folder!r} is not indexed. Run thunderbird_index first.")
    stat = abs_path.stat()
    if row[0] != stat.st_mtime or row[1] != stat.st_size:
        raise RuntimeError(
            f"Folder {folder!r} has changed since it was indexed. "
            "Run thunderbird_index to refresh before reading from it."
        )

    mbox = mailbox.mbox(str(abs_path), factory=_MESSAGE_FACTORY)
    try:
        msg = mbox.get(mbox_key)
    finally:
        mbox.close()

    if msg is None:
        raise KeyError(f"No message at key {mbox_key} in folder {folder!r}")

    return {
        "message_key": message_key,
        "folder": folder,
        "from": msg.get("From", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "body": _extract_body(msg),
    }


def list_folders() -> list[dict[str, Any]]:
    """List indexed folders with message counts. Run thunderbird_index first."""
    con = _db()
    try:
        rows = con.execute(
            "SELECT folder, COUNT(*) FROM messages GROUP BY folder ORDER BY folder"
        ).fetchall()
    finally:
        con.close()
    return [{"folder": row[0], "message_count": row[1]} for row in rows]
