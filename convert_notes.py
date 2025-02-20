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
parser.add_argument(
    "--journal_dashes",
    default=False,
    action="store_true",
    help="use dashes in daily journal - e.g. 2023-12-03.md",
)
parser.add_argument(
    "--tag_prop_to_taglist",
    default=False,
    action="store_true",
    help="convert tags in tags:: property to a list of tags in front matter",
)
parser.add_argument(
    "--ignore_dot_for_namespaces",
    default=False,
    action="store_true",
    help="ignore the use of '.' as a namespace character",
)
parser.add_argument(
    "--convert_tags_to_links",
    default=False,
    action="store_true",
    help="Convert #[[long tags]] to [[long tags]]",
)

# Global state isn't always bad mmkay
ORIGINAL_LINE = ""
INSIDE_CODE_BLOCK = False
alias_to_page = {}


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
    properties = {}
    first_line_after = 0
    
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
        # Check for Logseq-style properties (key:: value)
        for idx, line in enumerate(lines):
            match = re.match(r"(.*?)::[\s]*(.*)", line)
            if match is not None:
                key = match[1].strip()
                value = match[2].strip()
                properties[key] = value
                first_line_after = idx + 1
            else:
                break
                
    return properties, first_line_after


def get_namespace_hierarchy(fname: str) -> list[str]:
    """Given a markdown filename (not full path) representing a logseq page, returns a list representing the namespace
    hierarchy for that file
    Eg a file in the namespace "A/B/C" would return ['A', 'B', 'C.md']
    Namespaces are detected as follows ways:
        Splitting by "%2F" in the file name
        Splitting by "___" in the file name if the above is not present
        Splitting by "." in the file name if the above is not present and the --ignore_dot_for_namespaces flag is not present
    """
    split_by_pct = fname.split("%2F")
    if len(split_by_pct) > 1:
        return split_by_pct

    split_by_underscores = fname.split("___")
    if len(split_by_underscores) > 1:
        return split_by_underscores

    if not args.ignore_dot_for_namespaces:
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

        if len(date) == 1:
            date = "0" + date

        return "[[" + year + "-" + month_map[month] + "-" + date + "]]"

    line = re.sub(
        r"\[\[(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b (\d{1,2})(st|nd|rd|th), (\d{4})]]",
        reformat_dates_in_links,
        line,
    )

    # Replace #[[this type of tag]] with #this_type_of_tag or [[this type of tag]] depending on args.convert_tags_to_links
    def fix_long_tag(match: re.Match):
        s = match[0]

        if args.convert_tags_to_links:
            s = s.replace("#","")
        else:
            s = s.replace(" ", "_")
            s = s.replace("[", "")
            s = s.replace("]", "")
        return s

    line = re.sub(r"#\[\[.*?]]", fix_long_tag, line)

    # Convert a 'short' #tag to a [[tag]] link, if args.convert_tags_to_links is true
    def convert_tag_to_link(match: re.Match):
        s = match[0]

        if args.convert_tags_to_links:
            s = s.replace("#","")
            s = "[[{}]]".format(s)
        
        return s

    line = re.sub(r"#\w+", convert_tag_to_link, line)

    # Replace [[This/Type/OfLink]] with [OfLink](../Type/OfLink) - for example
    def fix_link(match: re.Match):
        s = match[0]
        s = s.replace("[", "")
        s = s.replace("]", "")

        # Check if this is an alias
        if s in alias_to_page:
            target_page = alias_to_page[s]
            if target_page in name_to_path:
                new_fpath = name_to_path[target_page]
                relpath = os.path.relpath(new_fpath, os.path.dirname(curr_path))
                relpath = relpath.replace(" ", "%20")  # Obsidian does this
                relpath = fix_escapes(relpath)
                return "[[" + target_page + "|" + s + "]]"

        # Or make it a tag if the page doesn't exist
        if s not in name_to_path:
            if args.convert_tags_to_links:
                s = s.replace(":", ".")
                return "[[" + s + "]]"
            else:
                s = "#" + s
                s = s.replace(" ", "_")
                s = s.replace(",", "_")
                return s
        else:
            new_fpath = name_to_path[s]
            relpath = os.path.relpath(new_fpath, os.path.dirname(curr_path))
            relpath = relpath.replace(" ", "%20")  # Obsidian does this
            relpath = fix_escapes(relpath)
            name = s.split("/")[-1]
            return "[[" + name + "]]"

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
        
        # Skip data URLs - they're embedded images that don't need file copying
        if old_relpath.startswith("data:"):
            out.append("!")
            out.append("[" + name + "]")
            out.append("(" + old_relpath + ")")
            return "".join(out)
        
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

    line = re.sub(r"!\[(.*?)]\((?!https?://)(.*?)\)", fix_asset_embed, line)

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
    """An empty line in logseq can still contain just  a hyphen"""
    line = re.sub(r"^\s*-\s*$", "", line)
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

    match = re.match(r"(\t*)-[ *]```(\w*)", line)
    if match is not None:
        tabs = match[1]
        language_name = match[2]
        out.append(tabs + "- " + language_name + " ↓\n")
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

def fix_escapes(old_str: str) -> str:
    """Given a filename, replace url escaped characters with an acceptable character for Obsidian filenames

    :arg old_str old string
    """
    if old_str.find("%") < 0:
        return old_str

    replace_map = {
        "%3A":".",
    }

    new_str = old_str

    for escape_str in replace_map:
        if new_str.find(escape_str) >= 0:
            new_str = new_str.replace(escape_str,replace_map[escape_str])

    return new_str

def unencode_filenames_for_links(old_str: str) -> str:    
    """Given a filename, replace url escaped characters with the normal character as it would appear in a link

    :arg old_str old value
    """
    if old_str.find("%") < 0:
        return old_str

    replace_map = {
        "%3A":":",
    }

    new_str = old_str

    for escape_str in replace_map:
        if new_str.find(escape_str) >= 0:
            new_str = new_str.replace(escape_str,replace_map[escape_str])

    return new_str

args = parser.parse_args()

old_base = args.logseq
new_base = args.output

old_to_new_paths = {}
new_to_old_paths = {}
new_paths = set()
pages_that_were_empty = set()
old_pagenames_to_new_paths = {}


# First loop: copy files to their new location, populate the maps and list of paths

if not os.path.exists(old_base) or not os.path.isdir(old_base):
    raise ValueError(f"The directory '{old_base}' does not exist or is not a valid directory.")

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
            
            if args.journal_dashes:
                new_fpath = new_fpath.replace("_","-")

            shutil.copyfile(fpath, new_fpath)
            old_to_new_paths[fpath] = new_fpath
            new_to_old_paths[new_fpath] = fpath
            new_paths.add(new_fpath)

            newfile = os.path.splitext(fname)[0]
            old_pagenames_to_new_paths[newfile] = new_fpath

            if args.journal_dashes:
                old_pagenames_to_new_paths[newfile.replace("_","-")] = new_fpath
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
            new_fpath = fix_escapes(new_fpath)
            logging.info("Destination path: " + new_fpath)
            new_dirname = os.path.split(new_fpath)[0]
            os.makedirs(new_dirname, exist_ok=True)
            shutil.copyfile(fpath, new_fpath)
            old_to_new_paths[fpath] = new_fpath
            new_to_old_paths[new_fpath] = fpath
            new_paths.add(new_fpath)

            old_pagename = os.path.splitext(hierarchical_pagename)[0]
            old_pagenames_to_new_paths[
                old_pagename
            ] = new_fpath
            # Add mapping of unencoded filename for links
            old_pagenames_to_new_paths[
                unencode_filenames_for_links(old_pagename)
            ] = new_fpath

# First build up alias mapping
for fpath in new_paths:
    properties, _ = get_markdown_file_properties(fpath)
    if 'alias' in properties:
        # Get the page name this alias points to
        page_name = os.path.splitext(os.path.basename(fpath))[0]
        # Split aliases on commas and map each to this page
        aliases = [a.strip() for a in properties['alias'].split(',')]
        for alias in aliases:
            alias_to_page[alias] = page_name

# Second loop: for each new file, reformat its content appropriately
for fpath in new_paths:
    newlines = []
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

        # Get properties including any aliases
        properties, first_line_after_front_matter = get_markdown_file_properties(fpath)
        
        # Start building new front matter
        front_matter = {}
        
        # Convert aliases if they exist
        if 'alias' in properties:
            # Split aliases on commas if multiple exist
            aliases = [a.strip() for a in properties['alias'].split(',')]
            front_matter['aliases'] = aliases
            
        # Handle other front matter properties
        for key, value in properties.items():
            if key != 'alias':  # Skip alias since we handled it specially
                if (key.find("tags") >= 0 or key.find("Tags") >= 0) and args.tag_prop_to_taglist:
                    # convert tags:: value1, #[[value 2]] 
                    # to
                    # taglinks: 
                    #   - "[[value1]]"
                    #   - "[[value 2]]"
                    tags = value.split(",")

                    front_matter['taglinks'] = []
                    for tag in tags:
                        tag = tag.strip()
                        clean_tag = tag.replace("#","")
                        clean_tag = clean_tag.replace("[[","")
                        clean_tag = clean_tag.replace("]]","")

                        front_matter['taglinks'].append('  - "[[' + clean_tag + ']]"')
                else:
                    front_matter[key] = value

        # Write the new front matter
        if bool(front_matter):
            newlines.append("---\n")
            for key, value in front_matter.items():
                if key == 'aliases':
                    newlines.append('aliases:\n')
                    for alias in value:
                        newlines.append(f'  - {alias}\n')
                elif key == 'taglinks':
                    newlines.append('taglinks:\n')
                    for tag in value:
                        newlines.append(f'  - {tag}\n')
                else:
                    newlines.append(f'{key}: {value}\n')
            newlines.append("---\n")

        for line in lines[first_line_after_front_matter:]:
            ORIGINAL_LINE = line

            # Update global state if this is the end of a code block
            if INSIDE_CODE_BLOCK and re.match(r"^```", line):
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
