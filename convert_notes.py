import argparse
import logging
import os
import re
import shutil
import typing

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")


parser = argparse.ArgumentParser()

parser.add_argument("--logseq", help="base directory of logseq graph", required=True)
parser.add_argument(
    "--output", help="base directory where output should go", required=True
)
parser.add_argument(
    "--overwrite_output",
    dest="overwrite_output",
    default=False,
    action="store_true",
    help="overwrites output directory if included",
)
parser.add_argument(
    "--unindent_once",
    default=False,
    action="store_true",
    help="unindents all lines once - lines at the highest level will have their bullet point removed",
)


# Global state isn't always bad mmkay
ORIGINAL_LINE = ""
INSIDE_CODE_BLOCK = False


def is_markdown_file(fpath: str) -> bool:
    return os.path.splitext(fpath)[-1].lower() == ".md"


def is_empty_markdown_file(fpath: str) -> bool:
    """Given a path to a markdown file, checks if it's empty
    A file is empty if it only contains whitespace
    A file containing only front matter / page properties is not empty
    """
    if not is_markdown_file(fpath):
        return False

    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        for line in lines:
            if not line.isspace():
                return False

    return True


def get_markdown_file_properties(fpath: str) -> tuple[dict, int]:
    """Given a path to a markdown file, returns a dictionary of its properties and the index of the first line after the properties

    Properties can either be in page property format: "title:: test"
    Or in front matter format:
        ---
        title: test
        ---
    """

    raise NotImplementedError()


def get_namespace_hierarchy(fname: str) -> list[str]:
    """Given a markdown filename (not full path) representing a logseq page, returns a list representing the namespace
    hierarchy for that file
    Eg a file in the namespace "A/B/C" would return ['A', 'B', 'C.md']
    Namespaces are detected in two ways:
        "%2F" in the file name
        If this is not present, dots in the filename
    """
    split_by_pct = fname.split("%2F")
    if len(split_by_pct) > 1:
        return split_by_pct

    split_by_underscores = fname.split("___")
    if len(split_by_underscores) > 1:
        return split_by_underscores

    split_by_dot = fname.split(".")
    split_by_dot[-2] += "." + split_by_dot[-1]
    split_by_dot.pop()
    if len(split_by_dot) > 1:
        return split_by_dot

    return [fname]


def update_links_and_tags(line: str, name_to_path: dict, curr_path: str) -> str:
    """Given a line of a logseq page, updates any links and tags in it

    :arg curr_path Absolute path of the current file, needed so that links can be replaced with relative paths
    """
    # First replace [[Aug 24th, 2022] with [[2022-08-24]]
    # This will stop the comma breaking tags
    month_map = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }

    def reformat_dates_in_links(match: re.Match):
        month = match[1]
        date = match[2]
        year = match[4]
        return "[[" + year + "-" + month_map[month] + "-" + date + "]]"

    line = re.sub(
        r"\[\[(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b (\d{1,2})(st|nd|rd|th), (\d{4})]]",
        reformat_dates_in_links,
        line,
    )

    # Replace #[[this type of tag]] with #this_type_of_tag
    def fix_long_tag(match: re.Match):
        s = match[0]
        s = s.replace(" ", "_")
        s = s.replace("[", "")
        s = s.replace("]", "")
        return s

    line = re.sub(r"#\[\[.*?]]", fix_long_tag, line)

    # Replace [[This/Type/OfLink]] with [OfLink](../Type/OfLink) - for example
    def fix_link(match: re.Match):
        s = match[0]
        s = s.replace("[", "")
        s = s.replace("]", "")
        # Or make it a tag if the page doesn't exist
        if s not in name_to_path:
            s = "#" + s
            s = s.replace(" ", "_")
            s = s.replace(",", "_")
            return s
        else:
            new_fpath = name_to_path[s]
            relpath = os.path.relpath(new_fpath, os.path.dirname(curr_path))
            relpath.replace(" ", "%20")  # Obsidian does this
            name = s.split("/")[-1]
            s = "[" + name + "](" + relpath + ")"
            return s

    line = re.sub(r"\[\[.*?]]", fix_link, line)

    return line


def update_assets(line: str, old_path: str, new_path: str):
    """Updates embedded asset links and copies the asset
    Assets are copied to the 'attachments' subfolder under the same directory as new_path is in
    Images (.PNG, .JPG) are embedded. Everything else is linked to
    """

    def fix_asset_embed(match: re.Match) -> str:
        out = []
        name = match[1]
        old_relpath = match[2]
        if old_relpath[:8] == "file:///":
            old_relpath = old_relpath[7:]

        old_relpath = old_relpath.replace("%20", " ")

        old_asset_path = os.path.normpath(
            os.path.join(os.path.dirname(old_path), old_relpath)
        )
        new_asset_path = os.path.join(
            os.path.dirname(new_path), "attachments", os.path.basename(old_asset_path)
        )
        new_asset_dir = os.path.dirname(new_asset_path)
        os.makedirs(new_asset_dir, exist_ok=True)
        print("Old note path: " + old_path)
        print("Old asset path: " + old_asset_path)
        print("New asset path: " + new_asset_path)
        try:
            shutil.copyfile(old_asset_path, new_asset_path)
            new_relpath = os.path.relpath(new_asset_path, os.path.dirname(new_path))
        except FileNotFoundError:
            print(
                "Warning: copying the asset from "
                + old_asset_path
                + " to "
                + new_asset_path
                + " failed, skipping it"
            )
            new_relpath = old_relpath
            # import ipdb; ipdb.set_trace()

        if os.path.splitext(old_asset_path)[1].lower() in [".png", ".jpg", ".jpeg", ".gif"]:
            out.append("!")
        out.append("[" + name + "]")
        out.append("(" + new_relpath + ")")

        return "".join(out)

    line = re.sub(r"!\[(.*?)]\((.*?)\)", fix_asset_embed, line)

    return line


def update_image_dimensions(line: str) -> str:
    """Updates the dimensions of embedded images with custom height/width specified
    Eg from ![image.png](image.png){:height 319, :width 568}
        to ![image.png|568](image.png)
    """

    def fix_image_dim(match):
        return "![" + match[1] + "|" + match[3] + "](" + match[2] + ")"

    line = re.sub(r"!\[(.*?)]\((.*?)\){:height \d*, :width (\d*)}", fix_image_dim, line)

    return line


def is_collapsed_line(line: str) -> bool:
    """Checks if the line is a logseq artefact representing a collapsed block"""
    match = re.match(r"\s*collapsed:: true\s*", line)
    return match is not None


def remove_block_links_embeds(line: str) -> str:
    """Returns the line stripped of any block links or embeddings"""
    line = re.sub(r"{{embed .*?}}", "", line)
    line = re.sub(r"\(\(.*?\)\)", "", line)
    return line


def convert_spaces_to_tabs(line: str) -> str:
    """Converts 2-4 spaces to a tab"""
    line = re.sub(r" {2,4}", "\t", line)
    return line


def convert_empty_line(line: str) -> str:
    """An empty line in logseq still starts with a hyphen"""
    line = re.sub(r"^- *$", "", line)
    return line


def add_space_after_hyphen_that_ends_line(line: str) -> str:
    """Add a space after a hyphen that ends a line"""
    line = re.sub(r"-$", "- ", line)
    return line


def prepend_code_block(line: str) -> list[str]:
    """Replaces a line starting a code block after a bullet point with two lines,
    so that the code block is displayed correctly in Obsidian

    If this line does not start a code block after a bullet point, then returns an empty list
    """
    out = []

    match = re.match(r"(\t*)-[ *]```(\w+)", line)
    if match is not None:
        tabs = match[1]
        language_name = match[2]
        out.append(tabs + "- " + language_name + " code block below:\n")
        out.append(tabs + "```" + language_name + "\n")
        INSIDE_CODE_BLOCK = True
        # import ipdb; ipdb.set_trace()

    return out


def escape_lt_gt(line: str) -> str:
    """Escapes < and > characters"""
    # Not if we're inside a code block
    if INSIDE_CODE_BLOCK:
        return line

    # Replace < and > with \< and \> respectively, but only if they're not at the start of the line
    line = re.sub(r"(?<!^)<", r"\<", line)
    line = re.sub(r"(?<!^)>", r"\>", line)

    return line

def convert_todos(line: str) -> str:
    # Not if we're inside a code block
    if INSIDE_CODE_BLOCK:
        return line

    line = re.sub(r"^- DONE", "- [X]", line)
    line = re.sub(r"^- TODO", "- [ ]", line)

    return line

def add_bullet_before_indented_image(line: str) -> str:
    """If an image has been embedded on a new line created after shift+enter, it won't be indented in Obsidian"""

    def add_bullet(match):
        return match[1] + "- " + match[2]

    line = re.sub(r"^(\t+)(!\[.*$)", add_bullet, line)
    return line


def unindent_once(line: str) -> str:
    """Returns the line after removing one level of indentation"""
    # If it starts with a tab, we can just remove it
    if line.startswith("\t"):
        return line[1:]

    # If it starts with a "- ", we can remove that
    if line.startswith("- "):
        return line[2:]

    return line


args = parser.parse_args()

old_base = args.logseq
new_base = args.output

old_to_new_paths = {}
new_to_old_paths = {}
new_paths = set()
pages_that_were_empty = set()
old_pagenames_to_new_paths = {}


# First loop: copy files to their new location, populate the maps and list of paths
assert os.path.exists(old_base) and os.path.isdir(old_base)

if args.overwrite_output and os.path.exists(new_base):
    shutil.rmtree(new_base)

os.makedirs(new_base, exist_ok=False)

# Copy journals pages to their own subfolder
old_journals = os.path.join(old_base, "journals")
assert os.path.isdir(old_journals)

new_journals = os.path.join(new_base, "journals")
os.mkdir(new_journals)

logging.info("Now beginning to copy the journal pages")
for fname in os.listdir(old_journals):
    fpath = os.path.join(old_journals, fname)
    logging.info("Now copying the journal page: " + fpath)
    if os.path.isfile(fpath):
        if not is_empty_markdown_file(fpath):
            new_fpath = os.path.join(new_journals, fname)
            shutil.copyfile(fpath, new_fpath)
            old_to_new_paths[fpath] = new_fpath
            new_to_old_paths[new_fpath] = fpath
            new_paths.add(new_fpath)
            old_pagenames_to_new_paths[os.path.splitext(fname)[0]] = new_fpath
        else:
            pages_that_were_empty.add(fname)

# Copy other markdown files to the new base folder, creating subfolders for namespaces
old_pages = os.path.join(old_base, "pages")
assert os.path.isdir(old_pages)

logging.info("Now beginning to copy the non-journal pages")
for fname in os.listdir(old_pages):
    fpath = os.path.join(old_pages, fname)
    logging.info("Now copying the non-journal page: " + fpath)
    if os.path.isfile(fpath) and is_markdown_file(fpath):
        hierarchy = get_namespace_hierarchy(fname)
        hierarchical_pagename = "/".join(hierarchy)
        if is_empty_markdown_file(fpath):
            pages_that_were_empty.add(fname)
        else:
            new_fpath = os.path.join(new_base, *hierarchy)
            logging.info("Destination path: " + new_fpath)
            new_dirname = os.path.split(new_fpath)[0]
            os.makedirs(new_dirname, exist_ok=True)
            shutil.copyfile(fpath, new_fpath)
            old_to_new_paths[fpath] = new_fpath
            new_to_old_paths[new_fpath] = fpath
            new_paths.add(new_fpath)
            old_pagenames_to_new_paths[
                os.path.splitext(hierarchical_pagename)[0]
            ] = new_fpath


# Second loop: for each new file, reformat its content appropriately
for fpath in new_paths:
    newlines = []
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

        # First replace the 'title:: my note' style of front matter with the Obsidian style (triple dashed)
        front_matter = {}
        in_front_matter = False
        first_line_after_front_matter = 0
        for idx, line in enumerate(lines):
            match = re.match(r"(.*?)::[\s]*(.*)", line)
            if match is not None:
                front_matter[match[1]] = match[2]
                first_line_after_front_matter = idx + 1
            else:
                break
        if bool(front_matter):
            # import ipdb; ipdb.set_trace()
            newlines.append("---\n")
            for key in front_matter:
                newlines.append(key + ": " + front_matter[key] + "\n")
            newlines.append("---\n")

        for line in lines[first_line_after_front_matter:]:
            ORIGINAL_LINE = line

            # Update global state if this is the end of a code block
            if INSIDE_CODE_BLOCK and line == "```\n":
                INSIDE_CODE_BLOCK = False

            # Ignore if the line if it's a collapsed:: true line
            if is_collapsed_line(line):
                continue

            # Convert empty lines in logseq to empty lines in Obsidian
            line = convert_empty_line(line)

            # Convert 2-4 spaces to a tab
            line = convert_spaces_to_tabs(line)

            # Unindent once if the user requested it
            if args.unindent_once:
                line = unindent_once(line)

            # Add a line above the start of a code block in a list
            lines = prepend_code_block(line)
            if len(lines) > 0:
                newlines.append(lines[0])
                line = lines[1]

            # Update links and tags
            line = update_links_and_tags(line, old_pagenames_to_new_paths, fpath)

            # Update assets
            line = update_assets(line, new_to_old_paths[fpath], fpath)

            # Update image dimensions
            line = update_image_dimensions(line)

            # Remove block links and embeds
            line = remove_block_links_embeds(line)

            # Self-explanatory
            line = add_space_after_hyphen_that_ends_line(line)

            # Self-explanatory
            line = convert_todos(line)

            # < and > need to be escaped to show up as normal characters in Obsidian
            line = escape_lt_gt(line)

            # Make sure images are indented correctly
            line = add_bullet_before_indented_image(line)

            newlines.append(line)

    with open(fpath, "w", encoding="utf-8") as f:
        f.writelines(newlines)
