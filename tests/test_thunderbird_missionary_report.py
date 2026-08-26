"""Tests for thunderbird.missionary_report against a synthetic mbox archive."""

import json
import mailbox
from email.message import EmailMessage

import pytest

from gcustodian.services import thunderbird


def _add(mbox: mailbox.mbox, *, from_addr: str, to_addr: str, subject: str, date: str) -> None:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = date
    msg.set_content("body")
    mbox.add(msg)


@pytest.fixture
def archive(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    inbox_path = profile / "Mail" / "Local Folders" / "Inbox"
    inbox_path.parent.mkdir(parents=True)

    mbox = mailbox.mbox(str(inbox_path))
    mbox.lock()
    try:
        # Missionary's updates, non-standard subjects, each indexed twice
        # (mirrors the duplicate Sent/All-Mail copies seen in the real
        # archive) -- start date is fixed via data/missionaries.json below,
        # so week 1 runs Mon Jan 5 through Sun Jan 11.
        for _ in range(2):
            _add(
                mbox,
                from_addr="Test Missionary <missionary@example.org>",
                to_addr="owner@example.com",
                subject="Prelude part 1",
                date="Mon, 05 Jan 2026 09:00:00 -0500",
            )
            _add(
                mbox,
                from_addr="Test Missionary <missionary@example.org>",
                to_addr="owner@example.com",
                subject="hi",
                date="Wed, 14 Jan 2026 09:00:00 -0500",
            )
        # Owner reply that falls inside week 1's window (before week 2).
        _add(
            mbox,
            from_addr="Owner <owner@example.com>",
            to_addr="Test Missionary <missionary@example.org>",
            subject="Re: Prelude part 1",
            date="Tue, 06 Jan 2026 09:00:00 -0500",
        )
        # No owner reply in week 2's or week 3's window.
    finally:
        mbox.unlock()
        mbox.close()

    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_PROFILE", str(profile))
    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_INDEX_DB", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("GCUSTODIAN_OWNER_EMAIL", "owner@example.com")

    metadata_path = tmp_path / "missionaries.json"
    metadata_path.write_text(
        json.dumps(
            {
                "missionary@example.org": {
                    "start_date": "2026-01-05",
                    "end_date": "2026-01-26",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GCUSTODIAN_MISSIONARY_METADATA", str(metadata_path))

    thunderbird.build_index()
    return tmp_path


def test_missionary_report_marks_received_sent_and_blank_weeks(archive):
    report = thunderbird.missionary_report("Test Missionary")

    assert report["missionary"] == {"name": "Test Missionary", "email": "missionary@example.org"}
    assert report["start_date"] == "2026-01-05"
    assert report["start_date_source"] == "metadata"
    # end_date 2026-01-25 bounds the report to 3 weekly windows.
    assert [w["week"] for w in report["weeks"]] == [1, 2, 3]
    assert [w["received"] for w in report["weeks"]] == [True, True, False]
    assert [w["sent"] for w in report["weeks"]] == [True, False, False]
    assert report["summary"] == {
        "total_weeks": 3,
        "weeks_received": 2,
        "weeks_sent": 1,
        "weeks_blank": 1,
    }


def test_missionary_report_dedupes_duplicate_index_entries(archive):
    report = thunderbird.missionary_report("Test Missionary")

    # Each update was indexed twice; the report should still list each once.
    assert len(report["weeks"][0]["received_emails"]) == 1


def test_missionary_report_requires_owner_email(archive, monkeypatch):
    monkeypatch.delenv("GCUSTODIAN_OWNER_EMAIL")

    with pytest.raises(RuntimeError, match="GCUSTODIAN_OWNER_EMAIL"):
        thunderbird.missionary_report("Test Missionary")


def test_missionary_report_unknown_sender_raises(archive):
    with pytest.raises(ValueError, match="No indexed messages"):
        thunderbird.missionary_report("Nobody Here")


def test_missionary_report_falls_back_to_earliest_message_without_metadata(tmp_path, monkeypatch):
    profile = tmp_path / "profile"
    inbox_path = profile / "Mail" / "Local Folders" / "Inbox"
    inbox_path.parent.mkdir(parents=True)

    mbox = mailbox.mbox(str(inbox_path))
    mbox.lock()
    try:
        _add(
            mbox,
            from_addr="Test Missionary <missionary@example.org>",
            to_addr="owner@example.com",
            subject="settled in",
            date="Mon, 02 Feb 2026 09:00:00 -0500",
        )
    finally:
        mbox.unlock()
        mbox.close()

    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_PROFILE", str(profile))
    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_INDEX_DB", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("GCUSTODIAN_OWNER_EMAIL", "owner@example.com")
    # No GCUSTODIAN_MISSIONARY_METADATA set -- points at a nonexistent
    # default path, so the loader falls back cleanly.
    monkeypatch.setenv("GCUSTODIAN_MISSIONARY_METADATA", str(tmp_path / "missing.json"))
    thunderbird.build_index()

    report = thunderbird.missionary_report("Test Missionary")

    assert report["start_date"] == "2026-02-02"
    assert report["start_date_source"] == "earliest_message"
