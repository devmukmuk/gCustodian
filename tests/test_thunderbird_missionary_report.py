"""Tests for thunderbird.missionary_report against a synthetic mbox archive."""

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
        # Missionary's weekly updates, each indexed twice (mirrors the
        # duplicate Sent/All-Mail copies seen in the real archive).
        for _ in range(2):
            _add(
                mbox,
                from_addr="Test Missionary <missionary@example.org>",
                to_addr="owner@example.com",
                subject="Week 1",
                date="Mon, 05 Jan 2026 09:00:00 -0500",
            )
            _add(
                mbox,
                from_addr="Test Missionary <missionary@example.org>",
                to_addr="owner@example.com",
                subject="Week 2",
                date="Mon, 12 Jan 2026 09:00:00 -0500",
            )
            _add(
                mbox,
                from_addr="Test Missionary <missionary@example.org>",
                to_addr="owner@example.com",
                subject="Week 3",
                date="Mon, 19 Jan 2026 09:00:00 -0500",
            )
        # Owner reply that falls inside week 1's window (before week 2).
        _add(
            mbox,
            from_addr="Owner <owner@example.com>",
            to_addr="Test Missionary <missionary@example.org>",
            subject="Re: Week 1",
            date="Tue, 06 Jan 2026 09:00:00 -0500",
        )
        # No owner reply in week 2's or week 3's window.
    finally:
        mbox.unlock()
        mbox.close()

    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_PROFILE", str(profile))
    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_INDEX_DB", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("GCUSTODIAN_OWNER_EMAIL", "owner@example.com")
    thunderbird.build_index()
    return tmp_path


def test_missionary_report_marks_sent_and_not_sent_weeks(archive):
    report = thunderbird.missionary_report("Test Missionary")

    assert report["missionary"] == {"name": "Test Missionary", "email": "missionary@example.org"}
    assert [w["week"] for w in report["weeks"]] == [1, 2, 3]
    assert [w["sent"] for w in report["weeks"]] == [True, False, False]
    assert report["summary"] == {"total_weeks": 3, "weeks_sent": 1, "weeks_not_sent": 2}


def test_missionary_report_dedupes_duplicate_index_entries(archive):
    report = thunderbird.missionary_report("Test Missionary")

    # Each week was indexed twice; the report should still list each once.
    assert len(report["weeks"]) == 3


def test_missionary_report_requires_owner_email(archive, monkeypatch):
    monkeypatch.delenv("GCUSTODIAN_OWNER_EMAIL")

    with pytest.raises(RuntimeError, match="GCUSTODIAN_OWNER_EMAIL"):
        thunderbird.missionary_report("Test Missionary")


def test_missionary_report_unknown_sender_raises(archive):
    with pytest.raises(ValueError, match="No indexed messages"):
        thunderbird.missionary_report("Nobody Here")


def test_missionary_report_collapses_unrelated_thread_with_same_week_number(tmp_path, monkeypatch):
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
            subject="Week 5",
            date="Mon, 02 Feb 2026 09:00:00 -0500",
        )
        # An unrelated reply thread that happens to reuse "Week 5" in its
        # subject days later -- should not become a second report row.
        _add(
            mbox,
            from_addr="Test Missionary <missionary@example.org>",
            to_addr="owner@example.com",
            subject="Re: Week 5 - side topic",
            date="Thu, 05 Feb 2026 09:00:00 -0500",
        )
    finally:
        mbox.unlock()
        mbox.close()

    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_PROFILE", str(profile))
    monkeypatch.setenv("GCUSTODIAN_THUNDERBIRD_INDEX_DB", str(tmp_path / "index.sqlite"))
    monkeypatch.setenv("GCUSTODIAN_OWNER_EMAIL", "owner@example.com")
    thunderbird.build_index()

    report = thunderbird.missionary_report("Test Missionary")

    assert len(report["weeks"]) == 1
    assert report["weeks"][0]["subject"] == "Week 5"
