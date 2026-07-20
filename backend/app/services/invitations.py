"""SMTP delivery and invite-token helpers."""

from __future__ import annotations

import hashlib
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import cast
from urllib.parse import quote

from app.services.settings_store import SmtpConfig

# Where Mathom lives on the web. The base URL is per-install (from SMTP config),
# while the project's home and source are fixed brand destinations.
MATHOM_GITHUB_URL = "https://github.com/MacNite/mathom"
MATHOM_WEBSITE_URL = "https://macnite.github.io/mathom/"

# The brand mark bundled with the backend, embedded inline so the email renders
# the logo without reaching out to any host (local-first, no external calls).
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "mathom-logo-mark-color.png"

# The email mirrors the app's "Cartographer's Table" palette (tailwind.config.js)
# so an invitation feels like the archive it opens.
_PAPER = "#e9e2cf"
_CARD = "#f6f1e2"
_BORDER = "#cdbf9d"
_MOSS = "#223027"
_GILD = "#e9c88a"
_INK = "#2b2a20"
_INK_SOFT = "#5e5540"
_HEARTH = "#8a5a2b"
# Email clients ignore custom fonts, so fall back to the same intent as the
# app's tokens: a serif display face and a system sans body.
_DISPLAY_FONT = "'Iowan Old Style', 'Hoefler Text', Georgia, Cambria, serif"
_BODY_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@lru_cache(maxsize=1)
def _logo_bytes() -> bytes | None:
    try:
        return _LOGO_PATH.read_bytes()
    except OSError:
        return None


def _plain_body(name: str, recipient: str, url: str, config: SmtpConfig, base_url: str) -> str:
    return (
        f"Hello {name or recipient},\n\n"
        "You have been invited to Mathom, your own local archive for "
        "conversations and memories.\n\n"
        "Use this one-time link to set your password and sign in:\n\n"
        f"{url}\n\n"
        f"This invitation expires in {config.invite_expiry_hours} hours.\n\n"
        "—\n"
        f"Open Mathom: {base_url}\n"
        f"Website: {MATHOM_WEBSITE_URL}\n"
        f"GitHub: {MATHOM_GITHUB_URL}\n"
    )


def _html_body(
    name: str, recipient: str, url: str, config: SmtpConfig, base_url: str, logo_cid: str | None
) -> str:
    greeting = escape(name or recipient)
    safe_url = escape(url, quote=True)
    logo = (
        f'<img src="cid:{logo_cid}" width="72" height="72" alt="Mathom" '
        'style="display:block;border:0;outline:none;text-decoration:none;'
        'width:72px;height:72px;" />'
        if logo_cid
        else ""
    )
    return f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background-color:{_PAPER};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
      style="background-color:{_PAPER};">
      <tr>
        <td align="center" style="padding:32px 16px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
            style="max-width:520px;width:100%;background-color:{_CARD};
            border:1px solid {_BORDER};border-radius:16px;overflow:hidden;
            box-shadow:3px 3px 0 rgba(90,70,40,0.06);">
            <tr>
              <td align="center" style="background-color:{_MOSS};padding:28px 24px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="padding-right:14px;vertical-align:middle;">{logo}</td>
                    <td style="vertical-align:middle;font-family:{_DISPLAY_FONT};
                      font-size:30px;letter-spacing:0.06em;color:{_GILD};">Mathom</td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 32px 24px 32px;font-family:{_BODY_FONT};
                color:{_INK};">
                <h1 style="margin:0 0 16px 0;font-family:{_DISPLAY_FONT};
                  font-size:22px;font-weight:600;color:{_INK};">
                  Hello {greeting},
                </h1>
                <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:{_INK_SOFT};">
                  You have been invited to Mathom — your own local archive for
                  conversations and memories. Use the one-time link below to set
                  your password and sign in.
                </p>
                <table role="presentation" cellpadding="0" cellspacing="0" border="0"
                  style="margin:24px 0;">
                  <tr>
                    <td align="center" style="border-radius:12px;background-color:{_HEARTH};">
                      <a href="{safe_url}"
                        style="display:inline-block;padding:13px 28px;font-family:{_BODY_FONT};
                        font-size:15px;font-weight:600;color:{_CARD};text-decoration:none;
                        border-radius:12px;">
                        Set your password
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 8px 0;font-size:13px;line-height:1.6;color:{_INK_SOFT};">
                  This invitation expires in {config.invite_expiry_hours} hours.
                </p>
                <p style="margin:0;font-size:13px;line-height:1.6;color:{_INK_SOFT};
                  word-break:break-all;">
                  If the button does not work, copy this link into your browser:<br />
                  <a href="{safe_url}" style="color:{_HEARTH};">{safe_url}</a>
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:0 32px;">
                <hr style="border:0;border-top:1px solid {_BORDER};margin:0;" />
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:20px 32px 28px 32px;font-family:{_BODY_FONT};
                font-size:13px;color:{_INK_SOFT};">
                <a href="{escape(base_url, quote=True)}"
                  style="color:{_HEARTH};text-decoration:none;">Open Mathom</a>
                &nbsp;&middot;&nbsp;
                <a href="{MATHOM_WEBSITE_URL}"
                  style="color:{_HEARTH};text-decoration:none;">Website</a>
                &nbsp;&middot;&nbsp;
                <a href="{MATHOM_GITHUB_URL}"
                  style="color:{_HEARTH};text-decoration:none;">GitHub</a>
              </td>
            </tr>
          </table>
          <p style="max-width:520px;margin:16px auto 0 auto;font-family:{_BODY_FONT};
            font-size:12px;line-height:1.5;color:#8a8264;text-align:center;">
            A trusted local archive for your conversations and memories.
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def build_invitation_message(
    config: SmtpConfig, recipient: str, name: str, token: str
) -> EmailMessage:
    """Assemble the branded multipart invitation (plain text + HTML + logo)."""
    base_url = config.public_base_url.rstrip("/")
    if not base_url:
        raise ValueError("A public base URL is required to send invitations")
    url = f"{base_url}/register?token={quote(token)}"

    message = EmailMessage()
    message["Subject"] = "You are invited to Mathom"
    message["From"] = (
        f"{config.from_name} <{config.from_email}>" if config.from_name else config.from_email
    )
    message["To"] = recipient

    message.set_content(_plain_body(name, recipient, url, config, base_url))

    logo = _logo_bytes()
    logo_cid: str | None = None
    if logo is not None:
        # make_msgid returns "<id@host>"; the src attribute needs the bare id.
        logo_cid = make_msgid(domain="mathom.local")[1:-1]
    message.add_alternative(
        _html_body(name, recipient, url, config, base_url, logo_cid), subtype="html"
    )
    if logo is not None and logo_cid is not None:
        html_part = cast(EmailMessage, message.get_payload(-1))
        html_part.add_related(logo, maintype="image", subtype="png", cid=f"<{logo_cid}>")
    return message


def send_invitation(config: SmtpConfig, recipient: str, name: str, token: str) -> None:
    if not config.configured:
        raise ValueError("SMTP is not configured")
    message = build_invitation_message(config, recipient, name, token)
    context = ssl.create_default_context()
    if config.use_tls:
        with smtplib.SMTP(config.host, config.port, timeout=15) as server:
            server.starttls(context=context)
            server.login(config.username, config.password)
            server.send_message(message)
    else:
        with smtplib.SMTP_SSL(config.host, config.port, context=context, timeout=15) as server:
            server.login(config.username, config.password)
            server.send_message(message)
