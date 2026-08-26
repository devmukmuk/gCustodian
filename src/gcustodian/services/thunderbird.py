"""Read-only access to a local Thunderbird "Local Folders" mbox archive.

The archive is treated as foreign, live data -- Thunderbird may be running
and holding these files. Nothing in this module ever writes back into the
Thunderbird profile; the search index it builds is entirely separate state
owned by gCustodian (see INDEX_DB_PATH).
"""

import email
import email.policy
import html
import json
import mailbox
import os
import re
import sqlite3
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
INDEX_DB_PATH = REPO_ROOT / "data" / "thunderbird_index.sqlite"
MISSIONARY_METADATA_PATH = REPO_ROOT / "data" / "missionaries.json"

_SKIP_SUFFIXES = {".msf", ".dat"}
_MESSAGE_FACTORY = lambda f: email.message_from_binary_file(f, policy=email.policy.default)  # noqa: E731
_EMAIL_RE = re.compile(r"<([^<>]+)>")
_MONTH_FOLDER_RE = re.compile(r"(\d{4})-(\d{2})$")


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


def _owner_email() -> str:
    value = os.environ.get("GCUSTODIAN_OWNER_EMAIL")
    if not value:
        raise RuntimeError(
            "GCUSTODIAN_OWNER_EMAIL is not set. Point it at the email address "
            "whose sent mail should count as a reply, e.g. you@example.com."
        )
    return value.strip().lower()


def _index_db_path() -> Path:
    override = os.environ.get("GCUSTODIAN_THUNDERBIRD_INDEX_DB")
    return Path(override) if override else INDEX_DB_PATH


def _missionary_metadata_path() -> Path:
    override = os.environ.get("GCUSTODIAN_MISSIONARY_METADATA")
    return Path(override) if override else MISSIONARY_METADATA_PATH


def _load_missionary_metadata(email_addr: str) -> dict[str, Any]:
    """Optional per-missionary overrides, keyed by lowercase email, e.g.
    {"katelyn.thacker@missionary.org": {"start_date": "2026-01-05"}}.

    Lives under data/ (gitignored) rather than Thunderbird's own address
    book -- see docs/epics/TBIRD.md on why writes never touch the live
    profile. Missing file or missing entry is not an error; callers fall
    back to inferring the start date from mail.
    """
    path = _missionary_metadata_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get(email_addr.lower(), {})


def _db() -> sqlite3.Connection:
    db_path = _index_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
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


def _extract_email(from_addr: str) -> str:
    match = _EMAIL_RE.search(from_addr)
    return (match.group(1) if match else from_addr).strip().lower()


def _month_key(folder: str) -> tuple[int, int] | None:
    match = _MONTH_FOLDER_RE.search(folder)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _ts_month(ts: float) -> tuple[int, int]:
    dt = datetime.fromtimestamp(ts)
    return dt.year, dt.month


def _shift_month(ym: tuple[int, int], delta: int) -> tuple[int, int]:
    year, month = ym
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def missionary_report(name: str) -> dict[str, Any]:
    """Weekly contact report for one missionary, in calendar-week windows
    from a start date -- not tied to any subject-line convention, since
    real missionaries use non-standard subjects (sometimes none at all).

    `name` is matched against the indexed From header the same way
    thunderbird_search's sender filter works (substring, case-insensitive).
    Run thunderbird_index first so the missionary's incoming mail is indexed;
    the owner's outgoing mail is found by scanning the raw archive directly
    (the index doesn't track To/Cc), bounded to the months the report spans.

    The start of week 1 comes from data/missionaries.json (gitignored,
    keyed by the missionary's lowercase email, e.g.
    {"start_date": "2026-01-05", "end_date": "2026-07-01"}) if an entry
    exists; otherwise it falls back to the date of their earliest indexed
    message. `end_date` bounds the last week generated; omit it (or leave
    no metadata entry at all) to run through today. Weeks with no message
    in either direction are still included as a row, marked blank, rather
    than being skipped.
    """
    owner_email = _owner_email()

    hits = search(sender=name, max_results=5000)
    if not hits:
        raise ValueError(f"No indexed messages found from sender matching {name!r}. Run thunderbird_index first.")

    missionary_email = _extract_email(hits[0]["from"])

    seen: set[tuple[str, str]] = set()
    received: list[dict[str, Any]] = []
    for hit in hits:
        dedup_key = (hit["subject"], hit["date"])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        received.append({"subject": hit["subject"], "date": hit["date"], "date_ts": _date_ts(hit["date"])})

    meta = _load_missionary_metadata(missionary_email)

    start_ts = _parse_date_bound(meta["start_date"]) if meta.get("start_date") else None
    start_source = "metadata"
    if start_ts is None:
        known_ts = [m["date_ts"] for m in received if m["date_ts"] is not None]
        if not known_ts:
            raise ValueError(
                f"Can't determine a start date for {name!r}: no dated messages indexed, and no "
                f"entry in {_missionary_metadata_path()} to fall back on."
            )
        start_ts = min(known_ts)
        start_source = "earliest_message"

    end_ts = _parse_date_bound(meta["end_date"]) if meta.get("end_date") else None
    if end_ts is None:
        end_ts = datetime.now().timestamp()

    month_bounds = (
        _shift_month(_ts_month(start_ts), -1),
        _shift_month(_ts_month(end_ts), 1),
    )

    root = _mail_root()
    sent_emails: list[dict[str, Any]] = []
    for folder, abs_path in _iter_mbox_files(root):
        month = _month_key(folder)
        if month is not None and not (month_bounds[0] <= month <= month_bounds[1]):
            continue
        mbox = mailbox.mbox(str(abs_path), factory=_MESSAGE_FACTORY)
        try:
            for _key, msg in mbox.items():
                from_addr = (msg.get("From", "") or "").lower()
                if owner_email not in from_addr:
                    continue
                recipients = f"{msg.get('To', '')} {msg.get('Cc', '')}".lower()
                if missionary_email not in recipients:
                    continue
                date_raw = msg.get("Date", "")
                sent_emails.append(
                    {
                        "subject": msg.get("Subject", ""),
                        "date": date_raw,
                        "date_ts": _date_ts(date_raw),
                    }
                )
        finally:
            mbox.close()

    week_seconds = timedelta(days=7).total_seconds()
    report_weeks: list[dict[str, Any]] = []
    week_num = 1
    window_start = start_ts
    while window_start < end_ts:
        window_end = window_start + week_seconds
        received_in_week = [
            m for m in received if m["date_ts"] is not None and window_start <= m["date_ts"] < window_end
        ]
        sent_in_week = [
            m for m in sent_emails if m["date_ts"] is not None and window_start <= m["date_ts"] < window_end
        ]
        report_weeks.append(
            {
                "week": week_num,
                "window_start": datetime.fromtimestamp(window_start).date().isoformat(),
                "window_end": datetime.fromtimestamp(window_end).date().isoformat(),
                "received": bool(received_in_week),
                "received_emails": [{"subject": m["subject"], "date": m["date"]} for m in received_in_week],
                "sent": bool(sent_in_week),
                "sent_emails": [{"subject": m["subject"], "date": m["date"]} for m in sent_in_week],
            }
        )
        week_num += 1
        window_start = window_end

    weeks_received = sum(1 for w in report_weeks if w["received"])
    weeks_sent = sum(1 for w in report_weeks if w["sent"])
    weeks_blank = sum(1 for w in report_weeks if not w["received"] and not w["sent"])
    return {
        "missionary": {"name": name, "email": missionary_email},
        "owner_email": owner_email,
        "start_date": datetime.fromtimestamp(start_ts).date().isoformat(),
        "start_date_source": start_source,
        "weeks": report_weeks,
        "summary": {
            "total_weeks": len(report_weeks),
            "weeks_received": weeks_received,
            "weeks_sent": weeks_sent,
            "weeks_blank": weeks_blank,
        },
    }
