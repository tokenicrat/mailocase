from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MailMessage:
    from_addr: str
    to_addr: str
    subject: str
    date: str
    message_id: str
    body: str
    in_reply_to: str = ""
    references: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)

    def to_string(self) -> str:
        lines = [
            f"From: {self.from_addr}",
            f"To: {self.to_addr}",
        ]
        if self.cc:
            lines.append(f"Cc: {', '.join(self.cc)}")
        lines += [
            f"Date: {self.date}",
            f"Subject: {self.subject}",
            f"Message-ID: {self.message_id}",
        ]
        if self.in_reply_to:
            lines.append(f"In-Reply-To: {self.in_reply_to}")
        if self.references:
            lines.append(f"References: {' '.join(self.references)}")
        lines += ["", self.body]
        return "\n".join(lines)

    @classmethod
    def from_string(cls, s: str) -> MailMessage:
        if "\n\n" in s:
            header_part, body = s.split("\n\n", 1)
        else:
            header_part, body = s, ""

        headers: dict[str, str] = {}
        current_key: str | None = None
        current_val = ""

        for line in header_part.split("\n"):
            if line and line[0] in (" ", "\t") and current_key:
                current_val += " " + line.strip()
            else:
                if current_key:
                    headers[current_key] = current_val
                if ": " in line:
                    k, _, v = line.partition(": ")
                    current_key = k.lower()
                    current_val = v
                else:
                    current_key = None
                    current_val = ""

        if current_key:
            headers[current_key] = current_val

        references = headers["references"].split() if "references" in headers else []
        cc_raw = headers.get("cc", "")
        cc = [a.strip() for a in cc_raw.split(",") if a.strip()] if cc_raw else []

        return cls(
            from_addr=headers.get("from", ""),
            to_addr=headers.get("to", ""),
            subject=headers.get("subject", ""),
            date=headers.get("date", ""),
            message_id=headers.get("message-id", ""),
            body=body,
            in_reply_to=headers.get("in-reply-to", ""),
            references=references,
            cc=cc,
        )

    def hash(self) -> str:
        return hashlib.sha256(self.to_string().encode()).hexdigest()[:16]

    def bare_subject(self) -> str:
        """Subject with Re: prefixes stripped."""
        s = self.subject
        while re.match(r"(?i)^re:\s*", s):
            s = re.sub(r"(?i)^re:\s*", "", s)
        return s.strip()

    def is_reply(self) -> bool:
        return bool(self.in_reply_to)


def encode_mail_content(plain: str) -> str:
    return base64.b64encode(plain.encode()).decode()


def decode_mail_content(data: str) -> str:
    try:
        decoded_bytes = base64.b64decode(data, validate=True)
        result = decoded_bytes.decode()
        if result.startswith("From:"):
            return result
    except Exception:
        pass
    return data


def read_mail_file(path: Path) -> str:
    return decode_mail_content(path.read_text())
