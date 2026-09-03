"""Tests for gmail.create_draft: multipart/alternative build and auto-HTML.

The Gmail API is stubbed out -- these never touch the network. A fake
service records the body passed to drafts().create and raises if any
send path is touched.
"""

import base64
import email

import pytest

from gcustodian.services import gmail


class _FakeExec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeDrafts:
    def __init__(self, recorder):
        self._recorder = recorder

    def create(self, userId, body):  # noqa: N803 - Gmail API kwarg name
        self._recorder["userId"] = userId
        self._recorder["body"] = body
        return _FakeExec({"id": "draft123", "message": {"id": "msg456"}})

    def send(self, *args, **kwargs):
        raise AssertionError("drafts().send must never be called by create_draft")


class _FakeMessages:
    def send(self, *args, **kwargs):
        raise AssertionError("messages().send must never be called by create_draft")


class _FakeUsers:
    def __init__(self, recorder):
        self._recorder = recorder

    def drafts(self):
        return _FakeDrafts(self._recorder)

    def messages(self):
        return _FakeMessages()


class _FakeService:
    def __init__(self, recorder):
        self._recorder = recorder

    def users(self):
        return _FakeUsers(self._recorder)


@pytest.fixture
def recorder(monkeypatch):
    rec = {}
    monkeypatch.setattr(gmail, "_client", lambda: _FakeService(rec))
    return rec


def _sent_message(recorder):
    raw = recorder["body"]["message"]["raw"]
    decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
    return email.message_from_bytes(decoded)


def _parts_by_type(msg):
    return {p.get_content_type(): p for p in msg.walk() if not p.is_multipart()}


def test_create_draft_returns_draft_and_message_ids(recorder):
    result = gmail.create_draft(to="a@example.com", subject="Hi", body="Hello")
    assert result == {"id": "draft123", "message_id": "msg456"}
    assert recorder["userId"] == "me"


def test_create_draft_builds_multipart_alternative_with_both_parts(recorder):
    gmail.create_draft(to="a@example.com", subject="Hi", body="Hello there")

    msg = _sent_message(recorder)
    assert msg.get_content_type() == "multipart/alternative"

    parts = list(msg.get_payload())
    assert [p.get_content_type() for p in parts] == ["text/plain", "text/html"]

    by_type = _parts_by_type(msg)
    assert by_type["text/plain"].get_payload(decode=True).decode("utf-8") == "Hello there"
    html = by_type["text/html"].get_payload(decode=True).decode("utf-8")
    assert "<p>Hello there</p>" in html


def test_create_draft_sets_headers_and_omits_absent_cc_bcc(recorder):
    gmail.create_draft(to="a@example.com", subject="Subject line", body="x")

    msg = _sent_message(recorder)
    assert msg["To"] == "a@example.com"
    assert msg["Subject"] == "Subject line"
    assert msg["Cc"] is None
    assert msg["Bcc"] is None


def test_create_draft_includes_cc_and_bcc_when_given(recorder):
    gmail.create_draft(
        to="a@example.com",
        subject="s",
        body="x",
        cc="c@example.com",
        bcc="b@example.com",
    )

    msg = _sent_message(recorder)
    assert msg["Cc"] == "c@example.com"
    assert msg["Bcc"] == "b@example.com"


def test_create_draft_uses_explicit_html_verbatim(recorder):
    gmail.create_draft(
        to="a@example.com",
        subject="s",
        body="plain fallback",
        html="<p>exact <b>markup</b></p>",
    )

    by_type = _parts_by_type(_sent_message(recorder))
    assert by_type["text/plain"].get_payload(decode=True).decode("utf-8") == "plain fallback"
    assert by_type["text/html"].get_payload(decode=True).decode("utf-8") == "<p>exact <b>markup</b></p>"


def test_create_draft_never_touches_send(recorder):
    # _FakeDrafts.send / _FakeMessages.send raise AssertionError if hit.
    gmail.create_draft(to="a@example.com", subject="s", body="x")


# --- _body_to_html -----------------------------------------------------------


def test_body_to_html_blank_lines_become_paragraphs():
    html = gmail._body_to_html("First para.\n\nSecond para.")
    assert html == "<p>First para.</p>\n<p>Second para.</p>"


def test_body_to_html_single_newline_becomes_br():
    html = gmail._body_to_html("line one\nline two")
    assert html == "<p>line one<br>\nline two</p>"


def test_body_to_html_dash_block_becomes_ul():
    html = gmail._body_to_html("- first\n- second\n- third")
    assert html == "<ul><li>first</li><li>second</li><li>third</li></ul>"


def test_body_to_html_numbered_block_becomes_ol():
    html = gmail._body_to_html("1. alpha\n2. beta")
    assert html == "<ol><li>alpha</li><li>beta</li></ol>"


def test_body_to_html_escapes_markup():
    html = gmail._body_to_html("a < b & c > d")
    assert "&lt; b &amp; c &gt;" in html
    assert "<p>" in html  # the wrapping tag is not escaped


def test_body_to_html_mixed_block_is_a_paragraph_not_a_list():
    html = gmail._body_to_html("intro line\n- not really a list")
    assert html == "<p>intro line<br>\n- not really a list</p>"


def test_body_to_html_combines_paragraph_and_list_blocks():
    html = gmail._body_to_html("Hi there,\n\n- one\n- two\n\nThanks")
    assert html == (
        "<p>Hi there,</p>\n"
        "<ul><li>one</li><li>two</li></ul>\n"
        "<p>Thanks</p>"
    )


def test_body_to_html_empty_body():
    assert gmail._body_to_html("") == "<p></p>"
    assert gmail._body_to_html("   \n  \n") == "<p></p>"
