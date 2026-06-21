from __future__ import annotations

import re

from mailocase.config import find_config, _extract_email
from mailocase.mail import MailMessage, read_mail_file


def _matches(
    msg: MailMessage,
    root: bool,
    from_addr: str | None,
    cc_filter: str | None,
    subject: str | None,
    content: str | None,
) -> bool:
    if root and msg.in_reply_to:
        return False
    if from_addr is not None:
        if _extract_email(msg.from_addr).lower() != from_addr.lower():
            return False
    if cc_filter is not None:
        cc_emails = {_extract_email(a).lower() for a in msg.cc}
        if cc_filter.lower() not in cc_emails:
            return False
    if subject is not None:
        if not re.search(subject, msg.subject):
            return False
    if content is not None:
        if not any(re.search(content, line) for line in msg.body.splitlines()):
            return False
    return True


def cmd_list(
    root: bool = False,
    from_addr: str | None = None,
    cc_filter: str | None = None,
    subject: str | None = None,
    content: str | None = None,
    include_draft: bool = False,
) -> None:
    cfg_path = find_config()
    if cfg_path is None:
        print("Error: Not in a mailocase directory. Run 'mailocase init' first.")
        return

    base = cfg_path.parent
    mail_dir = base / "mail"
    draft_dir = base / "draft"

    results: list[str] = []

    if mail_dir.exists():
        for p in sorted(mail_dir.iterdir()):
            if p.is_file():
                try:
                    msg = MailMessage.from_string(read_mail_file(p))
                except Exception:
                    continue
                if _matches(msg, root, from_addr, cc_filter, subject, content):
                    results.append(f"mail/{p.name}")

    if include_draft and draft_dir.exists():
        for p in sorted(draft_dir.iterdir()):
            if p.is_file():
                try:
                    msg = MailMessage.from_string(p.read_text())
                except Exception:
                    continue
                if _matches(msg, root, from_addr, cc_filter, subject, content):
                    results.append(f"draft/{p.name}")

    for r in results:
        print(r)
