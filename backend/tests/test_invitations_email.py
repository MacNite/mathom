"""The invitation email carries Mathom's branding and links."""

from app.services.invitations import (
    MATHOM_GITHUB_URL,
    MATHOM_WEBSITE_URL,
    build_invitation_message,
)
from app.services.settings_store import SmtpConfig


def _config(**overrides: object) -> SmtpConfig:
    base = dict(
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="secret",
        from_email="mathom@example.com",
        from_name="Mathom",
        public_base_url="https://mathom.example.com/",
        use_tls=True,
        invite_expiry_hours=48,
    )
    base.update(overrides)
    return SmtpConfig(**base)  # type: ignore[arg-type]


def _parts(message: object) -> dict[str, str]:
    parts: dict[str, str] = {}
    for part in message.walk():  # type: ignore[attr-defined]
        ctype = part.get_content_type()
        if ctype in {"text/plain", "text/html"}:
            parts[ctype] = part.get_content()
    return parts


def test_message_is_multipart_alternative_with_inline_logo() -> None:
    message = build_invitation_message(_config(), "new@user.com", "Frodo", "tok-123")

    assert message.get_content_type() == "multipart/alternative"
    types = [part.get_content_type() for part in message.walk()]
    assert "text/plain" in types
    assert "text/html" in types
    # The logo is embedded inline (cid) so the mail renders with no network call.
    images = [part for part in message.walk() if part.get_content_type() == "image/png"]
    assert len(images) == 1
    assert images[0].get("Content-ID") is not None
    assert (images[0].get("Content-Disposition") or "").startswith("inline")


def test_html_carries_registration_link_logo_and_brand_links() -> None:
    message = build_invitation_message(_config(), "new@user.com", "Frodo", "tok-abc")
    html = _parts(message)["text/html"]

    assert "https://mathom.example.com/register?token=tok-abc" in html
    assert "cid:" in html  # references the inline logo
    assert "Mathom" in html
    assert "Frodo" in html
    assert "48 hours" in html
    # Brand destinations: base URL, website, and GitHub.
    assert "https://mathom.example.com" in html
    assert MATHOM_WEBSITE_URL in html
    assert MATHOM_GITHUB_URL in html


def test_plain_text_fallback_has_the_essentials() -> None:
    message = build_invitation_message(_config(), "new@user.com", "", "tok-xyz")
    plain = _parts(message)["text/plain"]

    # Falls back to the recipient address when no name is given.
    assert "new@user.com" in plain
    assert "https://mathom.example.com/register?token=tok-xyz" in plain
    assert MATHOM_WEBSITE_URL in plain
    assert MATHOM_GITHUB_URL in plain
    assert "48 hours" in plain


def test_missing_base_url_is_rejected() -> None:
    try:
        build_invitation_message(_config(public_base_url=""), "new@user.com", "Sam", "tok")
    except ValueError as exc:
        assert "public base URL" in str(exc)
    else:  # pragma: no cover - the guard must raise
        raise AssertionError("expected a ValueError for a missing base URL")
