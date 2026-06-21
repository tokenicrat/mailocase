from __future__ import annotations
from logging.handlers import SocketHandler

import html
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate
from pathlib import Path
from typing import Any

from mailocase.config import find_config, load_config
from mailocase.mail import MailMessage, read_mail_file

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_URL_RE = re.compile(r"<(https?://[^\s>]+)>")


def _linkify(text: str) -> str:
    """Escape *text*, converting <url> patterns to clickable links."""
    parts: list[str] = []
    last = 0
    for m in _URL_RE.finditer(text):
        parts.append(html.escape(text[last : m.start()]))
        url = m.group(1)
        parts.append(f'&lt;<a href="{html.escape(url)}">{html.escape(url)}</a>&gt;')
        last = m.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def _format_body(raw: str) -> str:
    """Convert a raw email body to HTML with quote colouring and URL links."""
    out: list[str] = []
    for line in raw.split("\n"):
        processed = _linkify(line)
        if line.startswith(">"):
            out.append(f'<span class="quote">{processed}</span>')
        else:
            out.append(processed)
    return "\n".join(out)


def _fill(template: str, **kw: str) -> str:
    for k, v in kw.items():
        template = template.replace(f"{{{k}}}", v)
    return template


@dataclass
class ThreadNode:
    hash: str
    message: MailMessage
    children: list[ThreadNode] = field(default_factory=list)


def _date_key(msg: MailMessage) -> datetime:
    try:
        parts = parsedate(msg.date)
        if parts:
            return datetime(*parts[:6])
    except Exception:
        pass
    return datetime.min


def _load_messages(mail_dir: Path) -> dict[str, MailMessage]:
    messages: dict[str, MailMessage] = {}
    if not mail_dir.is_dir():
        return messages
    for f in mail_dir.iterdir():
        if f.is_file() and not f.name.startswith("."):
            try:
                messages[f.name] = MailMessage.from_string(read_mail_file(f))
            except Exception:
                pass
    return messages


def _build_threads(
    messages: dict[str, MailMessage],
) -> tuple[list[ThreadNode], dict[str, str]]:
    # message-id → filename hash
    id_map: dict[str, str] = {msg.message_id: h for h, msg in messages.items()}
    children_map: dict[str, list[str]] = {h: [] for h in messages}
    roots: list[str] = []

    for h, msg in messages.items():
        parent_mid = msg.in_reply_to
        if parent_mid and parent_mid in id_map and id_map[parent_mid] in messages:
            children_map[id_map[parent_mid]].append(h)
        else:
            roots.append(h)

    def build_node(h: str) -> ThreadNode:
        children = sorted(
            (build_node(c) for c in children_map[h]),
            key=lambda n: _date_key(n.message),
        )
        return ThreadNode(hash=h, message=messages[h], children=children)

    root_nodes = sorted(
        (build_node(r) for r in roots),
        key=lambda n: _date_key(n.message),
        reverse=True,
    )
    return root_nodes, id_map


def _count_descendants(node: ThreadNode) -> int:
    return sum(1 + _count_descendants(c) for c in node.children)


def _find_root_node(
    target_hash: str,
    roots: list[ThreadNode],
    messages: dict[str, MailMessage],
    id_map: dict[str, str],
) -> ThreadNode:
    """Return the root ThreadNode whose subtree contains target_hash."""
    visited: set[str] = set()
    h = target_hash
    while True:
        visited.add(h)
        mid = messages[h].in_reply_to
        if not mid or mid not in id_map:
            break
        parent_h = id_map[mid]
        if parent_h not in messages or parent_h in visited:
            break
        h = parent_h
    for node in roots:
        if node.hash == h:
            return node
    # Orphaned — synthesise a solo node
    return ThreadNode(hash=target_hash, message=messages[target_hash])


def _thread_tree_html(node: ThreadNode, current: str) -> str:
    msg = node.message
    subj = html.escape(msg.subject or "(no subject)")
    frm = html.escape(msg.from_addr)
    meta = f'<span class="meta"> — {frm}</span>'

    if node.hash == current:
        item = f'<span class="cur">{subj}</span>{meta}'
    else:
        item = f'<a href="{node.hash}.html">{subj}</a>{meta}'

    li = f"<li>{item}"
    if node.children:
        inner = "\n".join(_thread_tree_html(c, current) for c in node.children)
        li += f"\n<ul>\n{inner}\n</ul>"
    li += "</li>"
    return li


def _page(
    page_title: str,
    body: str,
    site: dict[str, Any],
    *,
    css_path: str = "style.css",
    index_path: str = "index.html",
) -> str:
    links = site.get("links", [])
    if links:
        items = "".join(
            f'<a href="{html.escape(lnk.get("url", ""))}">'
            f'{html.escape(lnk.get("label", ""))}</a>'
            for lnk in links
        )
        nav = f'<nav id="site-nav">{items}</nav>'
    else:
        nav = ""

    favicon = site.get("favicon", "")
    favicon_link = (
        html.escape(favicon) if favicon else ""
    )

    tmpl = (_TEMPLATES_DIR / "page.html").read_text()
    return _fill(
        tmpl,
        title=html.escape(page_title),
        favicon_link=favicon_link,
        css_path=css_path,
        index_path=index_path,
        site_title=html.escape(site.get("title", "")),
        nav=nav,
        body=body,
        footer=html.escape(site.get("footer", "")),
    )


def _truncate_string(string: str, length: int) -> str:
    if len(string) <= length:
        return string
    elif length <= 3:
        return '...'
    else:
        return string[:length - 3] + '...'


def _render_index(roots: list[ThreadNode], site: dict[str, Any]) -> str:
    intro = site.get("homepage_text", "")
    intro_html = f'<p class="intro">{html.escape(intro)}</p>\n' if intro else ""

    rows = []
    for node in roots:
        msg = node.message
        subj = html.escape(msg.subject or "(no subject)")
        frm = html.escape(msg.from_addr)
        date = html.escape(msg.date)
        replies = _count_descendants(node)
        reply_str = f"+{replies}" if replies else ""
        rows.append(
            f"<tr>"
            f'<td><a href="m/{node.hash}.html">{subj}</a></td>'
            f'<td class="col-from">{_truncate_string(frm, 15)}</td>'
            f'<td class="col-replies">{reply_str}</td>'
            f'<td class="col-date">{date}</td>'
            f"</tr>"
        )

    tbody = "\n".join(rows) if rows else '<tr><td colspan="4">(no messages)</td></tr>'
    table = (
        '<table class="threads">\n'
        "<thead><tr>"
        "<th>Subject</th><th>From</th><th>Replies</th><th>Date</th>"
        "</tr></thead>\n"
        f"<tbody>{tbody}</tbody>\n"
        "</table>"
    )

    body = f"{intro_html}{table}"
    return _page(site.get("title", "Archive"), body, site)


def _render_email(
    msg_hash: str,
    msg: MailMessage,
    root_node: ThreadNode,
    site: dict[str, Any],
) -> str:
    def hrow(label: str, value: str) -> str:
        return (
            f"<tr><th>{html.escape(label)}</th>"
            f"<td>{html.escape(value)}</td></tr>"
        )

    rows = [hrow("From", msg.from_addr), hrow("To", msg.to_addr)]
    if msg.cc:
        rows.append(hrow("Cc", ", ".join(msg.cc)))
    rows += [
        hrow("Date", msg.date),
        hrow("Subject", msg.subject or ""),
        hrow("ID", msg.message_id),
    ]
    if msg.in_reply_to:
        rows.append(hrow("Ref", msg.in_reply_to))

    headers_html = f'<table>{"".join(rows)}</table>'
    body_html = _format_body(msg.body)

    tree_li = _thread_tree_html(root_node, msg_hash)
    thread_html = (
        '<div class="thread-box">'
        "<h3>Thread</h3>"
        f'<ul class="thread-tree">{tree_li}</ul>'
        "</div>"
    )

    body = (
        '<div class="email-container">\n'
        f'<div class="email-headers">{headers_html}</div>\n'
        f'<div class="email-body">{body_html}</div>\n'
        f"{thread_html}\n"
        "</div>"
    )
    title = f"{msg.subject or '(no subject)'} — {site.get('title', '')}"
    return _page(title, body, site, css_path="../style.css", index_path="../index.html")


def render_site(mail_dir: Path, output_dir: Path, config: dict[str, Any]) -> None:
    site = config.get("site", {})
    output_dir.mkdir(parents=True, exist_ok=True)
    m_dir = output_dir / "m"
    m_dir.mkdir(exist_ok=True)

    static_dir = mail_dir.parent / "static"
    if static_dir.is_dir():
        shutil.copytree(static_dir, output_dir, dirs_exist_ok=True)

    messages = _load_messages(mail_dir)
    roots, id_map = _build_threads(messages)

    (output_dir / "style.css").write_text((_TEMPLATES_DIR / "style.css").read_text())
    (output_dir / "index.html").write_text(_render_index(roots, site))

    for h, msg in messages.items():
        root_node = _find_root_node(h, roots, messages, id_map)
        page = _render_email(h, msg, root_node, site)
        (m_dir / f"{h}.html").write_text(page)


def _preview(base_path: Path, addr: str = "127.0.0.1", port: int = 8000) -> None:
    import http.server
    import socketserver
    from functools import partial

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=base_path)

    with socketserver.TCPServer((addr, port), handler) as httpd:
        print(f"Preview available at http://{addr}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def cmd_render(output: str = "site", preview: bool = False, binding: tuple[str, int] = ("127.0.0.1", 8000)) -> None:
    cfg_path = find_config()
    if cfg_path is None:
        print("Error: Not in a mailocase directory. Run 'mailocase init' first.")
        return

    config = load_config(cfg_path)
    base = cfg_path.parent
    mail_dir = base / "mail"
    output_dir = Path(output) if Path(output).is_absolute() else base / output

    count = sum(1 for f in mail_dir.iterdir() if f.is_file()) if mail_dir.is_dir() else 0
    render_site(mail_dir, output_dir, config)
    print(f"Rendered {count} message(s) → {output_dir}")

    if preview:
        _preview(output_dir, binding[0], binding[1])
