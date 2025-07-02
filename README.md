# LogSeq to Obsidian Migration Tools

This project provides tools to help you migrate your notes from LogSeq to Obsidian while preserving formatting, links, and folder structure.

## ⚠️ Important Warning

**Always backup your notes before using these migration tools.** The scripts are experimental and may modify your files irreversibly.

## Quick Start

1. **CSS Theme**: Copy `bonofix-snippet.css` to your Obsidian snippets folder for LogSeq-inspired styling
2. **Convert Notes**: Run the Python conversion script to migrate your markdown files

```bash
python convert_notes.py --logseq /path/to/logseq/graph --output /path/to/output/folder
```

## Tools Included

### CSS Theme (`bonofix-snippet.css`)

A visual theme that makes Obsidian look more like LogSeq with Bonofix styling mixed with Typora aesthetics.

**Installation:**
1. Install the [Minimal theme](https://github.com/kepano/obsidian-minimal) in Obsidian
2. Copy `bonofix-snippet.css` to your Obsidian snippets folder
3. Enable the snippet in Obsidian settings

### Note Converter (`convert_notes.py`)

A Python script that converts LogSeq markdown files to Obsidian-compatible format, handling links, formatting, and folder structure.

## Usage

```bash
python convert_notes.py --logseq /path/to/logseq/graph --output /path/to/output/folder
```

### Command Line Options

| Flag | Description |
|------|-------------|
| `--overwrite_output` | Overwrite existing output folder |
| `--unindent_once` | Remove one level of indentation (converts bullet points to paragraphs) |
| `--ignore_dot_for_namespaces` | Ignore `.` characters when creating folder hierarchies |
| `--convert_tags_to_links` | Convert `#[[long tags]]` to `[[long tags]]` and `#tags` to `[[tags]]` |
| `--tag_prop_to_taglist` | Convert frontmatter tags to Taglinks format |
| `--journal_dashes` | Use dashes in journal filenames (`2023-08-03.md` vs `2023_08_03.md`) |

## What Gets Converted

### ✅ Supported Features

- **Folder Structure**: Creates hierarchical folders based on LogSeq namespaces (dots in filenames)
- **Links**: Updates internal links between notes and converts missing notes to tags
- **Assets**: Copies embedded images/files to `attachments` subfolder with proper resizing
- **Frontmatter**: Converts LogSeq format (`title:: My Note`) to Obsidian YAML format
- **Code Blocks**: Fixes formatting issues when code blocks appear in lists
- **Journal Pages**: Converts date formats (with `--journal_dashes` flag)
- **Tags**: Various tag conversion options available
- **Special Characters**: Escapes `<` and `>` characters for proper display

### ❌ Known Limitations

- Page properties not used for namespace detection
- Subfolders in LogSeq assets not fully supported
- No alias handling
- No namespace support under journal pages
- PDF embedding not implemented
- Asset names with `%20` may cause issues

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests to improve the migration tools.
