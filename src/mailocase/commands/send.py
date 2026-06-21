from __future__ import annotations

import hashlib
from typing import Optional

from mailocase.config import (
    find_config, load_config, lookup_user, format_address, _extract_email,
)
from mailocase.mail import MailMessage, encode_mail_content, read_mail_file


def cmd_send(
    name: str,
    reply_to: Optional[str] = None,
    cc: list[str] | None = None,
    cc_add: list[str] | None = None,
    cc_remove: list[str] | None = None,
    send_as: Optional[str] = None,
) -> None:
    cfg_path = find_config()
    if cfg_path is None:
        print("Error: Not in a mailocase directory.")
        return

    cfg = load_config(cfg_path)
    base = cfg_path.parent
    draft_path = base / "draft" / name
    mail_dir = base / "mail"

    if not draft_path.exists():
        print(f"Error: Draft '{name}' not found.")
        return

    msg = MailMessage.from_string(draft_path.read_text())

    if send_as is not None:
        addresses = cfg.get("addresses", [])
        user = lookup_user(send_as, addresses)
        if user is None:
            print(f"Error: '{send_as}' is not in config addresses.")
            return
        msg.from_addr = format_address(user)

    if reply_to:
        reply_path = mail_dir / reply_to
        if reply_path.exists():
            parent = MailMessage.from_string(read_mail_file(reply_path))
            msg.in_reply_to = parent.message_id
            msg.references = list(parent.references) + [parent.message_id]
        else:
            print(f"Warning: Sent item '{reply_to}' not found.")

    if cc is not None:
        msg.cc = list(cc)

    if cc_add:
        for addr in cc_add:
            if addr not in msg.cc:
                msg.cc.append(addr)

    if cc_remove:
        remove_emails = {_extract_email(r).lower() for r in cc_remove}
        msg.cc = [a for a in msg.cc if _extract_email(a).lower() not in remove_emails]

    content = msg.to_string()
    mail_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    mail_path = mail_dir / mail_hash

    if mail_path.exists():
        print(f"Already exists (identical content): {mail_hash}")
        draft_path.unlink()
        return

    if cfg.get("encode_emails", False):
        content = encode_mail_content(content)

    mail_path.write_text(content)
    draft_path.unlink()
    print(f"Sent: {mail_hash}")
