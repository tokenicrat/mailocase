from __future__ import annotations

import random
import string
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mailocase.config import (
    find_config, load_config, lookup_user, format_address, _extract_email,
)
from mailocase.mail import MailMessage, read_mail_file


def _draft_filename() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{ts}_{rand}"


def _message_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"<{ts}.{rand}@mailocase>"


def _edit(path: Path, editor: str) -> None:
    subprocess.run([editor, str(path)], check=False)


def _apply_reply(
    msg: MailMessage, reply_to: str, mail_dir: Path,
    overwrite: bool, update_subject: bool = False,
) -> None:
    """Load reply headers from a sent item onto msg.

    If overwrite is False, skip when in_reply_to is already set.
    """
    if not overwrite and msg.in_reply_to:
        return
    reply_path = mail_dir / reply_to
    if reply_path.exists():
        parent = MailMessage.from_string(read_mail_file(reply_path))
        msg.in_reply_to = parent.message_id
        msg.references = list(parent.references) + [parent.message_id]
        if update_subject:
            subj = parent.subject.strip()
            msg.subject = subj if subj.lower().startswith("re:") else f"Re: {subj}"
    else:
        print(f"Warning: Sent item '{reply_to}' not found; reply headers omitted.")


def cmd_draft(
    name: Optional[str] = None,
    reply_to: Optional[str] = None,
    cc: list[str] | None = None,
    cc_add: list[str] | None = None,
    cc_remove: list[str] | None = None,
    send_as: Optional[str] = None,
) -> None:
    cfg_path = find_config()
    if cfg_path is None:
        print("Error: Not in a mailocase directory. Run 'mailocase init' first.")
        return

    cfg = load_config(cfg_path)
    base = cfg_path.parent
    draft_dir = base / "draft"
    mail_dir = base / "mail"

    if name:
        p = draft_dir / name
        if not p.exists():
            print(f"Error: Draft '{name}' not found.")
            return

        # Apply requested modifications to the existing draft before editing.
        if any(x is not None for x in (send_as, reply_to)) or cc or cc_add or cc_remove:
            msg = MailMessage.from_string(p.read_text())

            if send_as is not None:
                addresses = cfg.get("addresses", [])
                user = lookup_user(send_as, addresses)
                if user is None:
                    print(f"Error: '{send_as}' is not in config addresses.")
                    return
                msg.from_addr = format_address(user)

            if reply_to is not None:
                _apply_reply(msg, reply_to, mail_dir, overwrite=True, update_subject=True)

            if cc is not None:
                msg.cc = list(cc)
            if cc_add:
                for addr in cc_add:
                    if addr not in msg.cc:
                        msg.cc.append(addr)
            if cc_remove:
                remove_emails = {_extract_email(r).lower() for r in cc_remove}
                msg.cc = [a for a in msg.cc if _extract_email(a).lower() not in remove_emails]

            p.write_text(msg.to_string())

        _edit(p, cfg["editor"])
        print(f"Draft: {name}")
        return

    # Build a fresh draft.
    addresses = cfg.get("addresses", [])

    if send_as is not None:
        user = lookup_user(send_as, addresses)
        if user is None:
            print(f"Error: '{send_as}' is not in config addresses.")
            return
        from_addr = format_address(user)
    else:
        default_from = cfg.get("default_from", "")
        if default_from:
            user = lookup_user(default_from, addresses)
            from_addr = format_address(user) if user else default_from
        else:
            from_addr = format_address(addresses[0]) if addresses else "user@example.com"

    list_addr = cfg.get("list_address", "list@example.com")
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    filename = _draft_filename()
    draft_path = draft_dir / filename

    subject = ""
    in_reply_to = ""
    references: list[str] = []

    if reply_to:
        reply_path = mail_dir / reply_to
        if reply_path.exists():
            parent = MailMessage.from_string(read_mail_file(reply_path))
            in_reply_to = parent.message_id
            references = list(parent.references) + [parent.message_id]
            subj = parent.subject.strip()
            subject = subj if subj.lower().startswith("re:") else f"Re: {subj}"
        else:
            print(f"Warning: Sent item '{reply_to}' not found; reply headers omitted.")

    # For new drafts -c and --cc+ both initialise CC (nothing to overwrite).
    initial_cc: list[str] = list(cc) if cc is not None else []
    for addr in (cc_add or []):
        if addr not in initial_cc:
            initial_cc.append(addr)

    msg = MailMessage(
        from_addr=from_addr,
        to_addr=list_addr,
        subject=subject,
        date=date_str,
        message_id=_message_id(),
        body="\n\n-- \n",
        in_reply_to=in_reply_to,
        references=references,
        cc=initial_cc,
    )

    draft_path.write_text(msg.to_string())
    _edit(draft_path, cfg["editor"])
    print(f"Draft: {filename}")
