# Mailocase

> [!NOTE]
> Most code is generated with Claude and *reviewed by human*. Still, there is no absolute guarantee of quality and caution is recommended.

A local mailing list emulator and static site generator. Write and send emails to a simulated mailing list, organize them into threaded conversations, and render the archive as a static HTML website.

## Features

- Create and edit draft emails in your preferred text editor
- Reply-to chains with automatic thread tracking (RFC 5322 `In-Reply-To`/`References` headers)
- CC recipient support, with per-command overwrite, append, or remove control
- Send-as support: choose any address from your configured `addresses` list
- Automatic thread organization by parent-child relationships
- Static HTML site generation with full thread visualization
- Zero external dependencies — pure Python standard library

## Installation

Requires Python 3.11+. Install with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install .
```

Or with pip:

```sh
pip install .
```

## Quick Start

```sh
# Initialize a new mailocase archive in the current directory
mailocase init

# Edit config.json to set your name, addresses, editor, etc.

# Create a new draft email
mailocase draft

# Send the draft (use the filename shown after drafting)
mailocase send <draft-filename>

# Render the archive to a static website
mailocase render
```

Open `site/index.html` in a browser to view the rendered archive.

## Commands

### `init [location]`

Initialize a new mailocase directory. Creates the following structure:

```
./
├── config.json   # Configuration
├── draft/        # Unsent draft emails
├── mail/         # Sent emails (named by content hash)
└── site/         # Generated static site (after render)
```

If `location` is omitted, initializes in the current directory.

### `draft [name]`

Open a new draft email in your configured editor.

```sh
mailocase draft                        # New draft
mailocase draft <filename>             # Edit an existing draft
mailocase draft -r <hash>              # Pre-fill reply headers for a sent email
mailocase draft -c <addr> [<addr>...]  # Set CC recipients (replaces existing)
mailocase draft --cc+ <addr> [...]     # Append to CC recipients
mailocase draft --cc- <addr> [...]     # Remove from CC recipients
mailocase draft -a <addr>              # Send as a specific address (must be in config)
```

### `send <filename>`

Send a draft to the mailing list archive.

```sh
mailocase send <filename>
mailocase send <filename> -r <hash>              # Set reply-to (overwrites any in draft)
mailocase send <filename> -c <addr> [<addr>...]  # Replace CC list
mailocase send <filename> --cc+ <addr> [...]     # Append to CC list
mailocase send <filename> --cc- <addr> [...]     # Remove from CC list
mailocase send <filename> -a <addr>              # Send as address (must be in config)
```

The message is stored in `mail/` under a filename derived from its SHA256 hash. The draft is removed after sending.

### `delete <name>`

Delete a draft or a sent email by filename or hash.

```sh
mailocase delete <draft-filename>
mailocase delete <hash>
```

### `render [output_dir]`

Generate the static HTML archive. Defaults to `site/` inside the mailocase directory.

```sh
mailocase render
mailocase render /path/to/output
```

Produces:
- `index.html` — thread listing with reply counts
- `m/<hash>.html` — individual email pages with thread view

You can also immediately preview the site with `-p`:

```sh
mailocase render -p              # Bind 127.0.0.1:8000 by default
mailocase render -b 0.0.0.0 9000 # Optionally specify address and port
```

### `list [filters]`

Search and filter emails.

```sh
mailocase list                          # List all sent emails
mailocase list --root                   # Only root messages (no In-Reply-To)
mailocase list --from <email>           # Filter by sender address
mailocase list --cc <email>             # Filter where email appears in CC
mailocase list --subject <regex>        # Filter by subject regex
mailocase list --content <regex>        # Filter where any body line matches regex
mailocase list --include-draft          # Include drafts in results
```

## Configuration

`config.json` is created by `mailocase init` and can be edited manually:

```json
{
  "editor": "nano",
  "addresses": [
    {"name": "You", "email": "you@example.com"}
  ],
  "default_from": "you@example.com",
  "list_address": "list@example.com",
  "encode_email": false,
  "site": {
    "title": "Mailocase Archive",
    "footer": "Powered by Mailocase",
    "homepage_text": "",
    "favicon": "",
    "links": [
      { "url": "", "label": "" }
    ]
  }
}
```

| Key | Description |
|---|---|
| `editor` | Command used to open draft files |
| `addresses` | List of sender addresses (objects with `name` and `email` fields) available when drafting or using `-a` |
| `default_from` | Default `From` address for new drafts (email or `name@example.com`) |
| `list_address` | Address used as the mailing list `To` |
| `encode_email` | Encode sent emails with Base64 |
| `site.title` | Title shown in the rendered site |
| `site.footer` | Footer text on every page |
| `site.homepage_text` | Optional intro text on the index page |
| `site.links` | Navigation links in header |

Mailocase searches for `config.json` by walking up the directory tree from your current working directory, so you can run commands from any subdirectory of your archive.

## Email Format

Drafts and sent emails use plain text RFC 5322-style format:

```
From: You <you@example.com>
To: list@example.com
Subject: Hello, world
Date: Thu, 26 Feb 2026 12:00:00 +0000
Message-ID: <abc123@mailocase>

Body text goes here.
```

Files are stored as-is and parsed by the standard library `email` module.
