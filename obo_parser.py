"""
This module provides utility functions for parsing data in the .obo (Open Biomedical Ontologies)
format and writing it out as a .tsv table for easier analysis.

The .obo format spec can be found here:
http://owlcollab.github.io/oboformat/doc/GO.format.obo-1_2.html
"""

import argparse
import collections
import contextlib
import logging
import os
import re
import sys
import tqdm
import urllib

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s')
logger = logging.getLogger(__name__)

# regex used to parse records
TAG_AND_VALUE_REGEX = "(?P<tag>[^:]+):(?P<value>[^!]+)"

# column groups and re-mappings
ONLY_ONE_ALLOWED_PER_STANZA = set(["id", "name", "def", "comment"])
EXCLUDE_FROM_TSV = set(["consider", "replaced_by", "property_value", "is_obsolete", "is_anonymous"])
RENAME_COLUMNS = {
    'is_a': 'parent_ids',
    'def': 'definition',
}


def convert_obo_to_tsv(input_path, output_path="-", root_id=None, add_category_column=False):
    """Main entry point for parsing an .obo file and converting it to a .tsv table.

    Args:
        input_path (str): .obo file url or local file path
        output_path (str): path where to write the .tsv file. Defaults to "-" which is standard out.
        root_id (str): If specified, ignore ontology terms that are not either descendants of the
            given id or have this id themselves. For example, 'HP:0000118'.
        add_category_column (bool): Whether to add a 'category' column to the output .tsv file
            which lists each term's top-level category. A top-level category is a term that's a
            direct child of the ontology's root term.
    """

    if output_path is None:
        output_path = os.path.basename(input_path).replace(".obo", "") + ".tsv"

    # read in data
    logger.info("Parsing %s", input_path)
    with _open_input_stream(input_path) as input_stream:
        obo_records_dict = parse_obo_format(input_stream)

    # find root term
    if root_id is None:
        root_id = _compute_root_id(obo_records_dict)

    _confirm_id_is_valid(root_id, obo_records_dict, label="root_id")

    # add 'category' columns to records
    if add_category_column:
        compute_category_column(obo_records_dict, root_id=root_id)

    # print stats and output .tsv
    print_stats(obo_records_dict, input_path)

    if output_path == "-":
        write_tsv(obo_records_dict, output_stream=sys.stdout, root_id=root_id)
    else:
        with open(output_path, "w") as output_stream:
            write_tsv(obo_records_dict, output_stream, root_id=root_id)

    logger.info("Done")


def parse_obo_format(lines):
    """Parses .obo-formatted text.

    Args:
        lines (iter): Iterator over lines of text in .obo format.
    Returns:
        dict: .obo records, keyed by term id. Each record is a dictionary where the keys are tags
            such as "id", "name", "is_a", and values are strings (for tags that can only occur once
             - such as "id"), or lists (for tags that can appear multiple times per stanza - such as
             "xref")
    """

    obo_records_dict = collections.OrderedDict()
    current_stanza_type = None
    current_record = None
    all_tags = set()

    if logger.isEnabledFor(logging.INFO):
        lines = tqdm.tqdm(lines, unit=" lines")

    for line in lines:
        if line.startswith("["):
            current_stanza_type = line.strip("[]\n")
            continue

        # skip header lines and stanzas that aren't "Terms"
        if current_stanza_type != "Term":
            continue

        # remove new-line character and any comments
        line = line.rstrip('\n').split("!")[0]
        if len(line) == 0:
            continue

        match = re.match(TAG_AND_VALUE_REGEX, line)
        if not match:
            raise ValueError("Unexpected line format: %s" % str(line))

        tag = match.group("tag")
        value = match.group("value").strip()

        if tag == "id":
            current_record = collections.defaultdict(list)
            obo_records_dict[value] = current_record

        all_tags.add(tag)
        if tag in ONLY_ONE_ALLOWED_PER_STANZA:
            if tag in current_record:
                raise ValueError("More than one '%s' found in %s stanza: %s" % (
                    tag, current_stanza_type, ", ".join([current_record[tag], value])))

            current_record[tag] = value
        else:
            current_record[tag].append(value)

    # add a 'children' key and list of child ids to all records that have children
    _compute_children_column(obo_records_dict)

    return obo_records_dict


def print_stats(obo_records_dict, input_path):
    """Print various summary stats about the given .obo records.

    Args:
        obo_records_dict (dict): data structure returned by parse_obo_format(..)
        input_path (str): source path of .obo data.
    """

    if not logger.isEnabledFor(logging.INFO):
        return

    tag_counter = collections.defaultdict(int)
    value_counter = collections.defaultdict(int)
    for term_id, record in obo_records_dict.items():
        for tag, value in record.items():
            tag_counter[tag] += 1
            if isinstance(value, list):
                value_counter[tag] += len(value)

    logger.info("Parsed %s terms from %s", len(obo_records_dict), input_path)
    total_records = len(obo_records_dict)
    for tag, records_with_tag in sorted(tag_counter.items(), key=lambda t: t[1], reverse=True):
        percent_with_tag = 100*records_with_tag/float(total_records) if total_records > 0 else 0

        message = "%(records_with_tag)s out of %(total_records)s (%(percent_with_tag)0.1f%%) " \
            "records have a %(tag)s tag"
        if tag in value_counter:
            values_per_record = value_counter[tag] / float(records_with_tag)
            message += ", and have, on average, %(values_per_record)0.1f values per record."
        logger.info(message % locals())


def _compute_root_id(obo_records_dict):
    """Finds the top-level term in the heirarchy.
    NOTE: this implementation assumes the ontology has a single root term, and doesn't have cycles.
    """

    if not obo_records_dict:
        return None

    # start with a random id and walk up the heirarchy to find a term that doesn't have a parent
    term_id = obo_records_dict.iterkeys().next()
    while True:
        parent_ids = obo_records_dict[term_id].get("is_a")
        if parent_ids is None or len(parent_ids) == 0:
            return term_id

        _confirm_id_is_valid(parent_ids[0], obo_records_dict, label="%s's parent id" % term_id)

        term_id = parent_ids[0]


def get_substree(obo_records_dict, root_id, skip_record=None):
    """Generates .obo records that are either descendants of the given root_id or the root record
    itself.

    Args:
        obo_records_dict (dict): data structure returned by parse_obo_format(..)
        root_id (str): Only ontology terms that are either descendants of the
            given id or have this id themselves are returned. For example, 'HP:0000118'.
        skip_record (function): A function which takes a record and returns True if the record (and
            it's descendants) should be skipped.
    Yields:
        dict: .obo records
    """

    _confirm_id_is_valid(root_id, obo_records_dict, label='root_id')

    ids_to_process = collections.deque([root_id])
    processed_ids = set()
    while ids_to_process:
        next_id = ids_to_process.popleft()
        record = obo_records_dict[next_id]
        if next_id in processed_ids or (skip_record is not None and skip_record(record)):
            continue

        yield record

        processed_ids.add(next_id)
        child_ids = record.get('children', [])
        ids_to_process.extend(child_ids)


def _compute_children_column(obo_records_dict):
    """For each record that has child terms, compute a list of child term ids and store it in the
    record under a new 'children' attribute.
    """

    for term_id, current_record in obo_records_dict.items():
        if "is_a" not in current_record:
            continue

        for parent_id in current_record["is_a"]:
            if parent_id not in obo_records_dict:
                logger.warn("%s has a parent id %s which is not in the ontology" % (
                    term_id, parent_id))
                continue

            parent_record = obo_records_dict[parent_id]
            if 'children' not in parent_record:
                parent_record['children'] = []

            parent_record['children'].append(term_id)


def compute_category_column(
        obo_records_dict,
        root_id,
        add_category_id_column=True,
        add_category_name_column=True):
    """Adds a "category_id" and/or "category_name" column to each record that's a descendant of the
    root term.

    Args:
        obo_records_dict (dict): data structure returned by parse_obo_format(..)
        root_id (str): Only ontology terms that are either descendants of the
            given id or have this id themselves are returned. For example, 'HP:0000118'.
        add_category_id_column (bool): Whether to add a "category_id" to each record.
        add_category_name_column (bool): Whether to add a "category_name" to each record.
    """

    _confirm_id_is_valid(root_id, obo_records_dict, label='root_id')

    root_record = obo_records_dict[root_id]
    root_child_ids = root_record.get('children', [])

    if not root_child_ids:
        logger.warn("root term has no child terms")
        return

    for category_id in root_child_ids:
        category_name = obo_records_dict[category_id].get("name", "")

        def is_category_already_assigned(record):
            return 'category_id' in record or 'category_name' in record

        category_subtree = get_substree(
            obo_records_dict,
            root_id=category_id,
            skip_record=is_category_already_assigned
        )

        for record in category_subtree:
            if add_category_id_column:
                record['category_id'] = category_id
            if add_category_name_column:
                record['category_name'] = category_name


def _open_input_stream(path):
    """Returns an open stream for iterating over lines in the given path.

    Args:
        path (str): url or local file path
    Return:
        iter: iterator over file handle
    """
    if not isinstance(path, (str, unicode)):
        raise ValueError("Unexpected path type: %s" % str(path))

    is_url = path.startswith("http")
    if is_url:
        line_iterator = contextlib.closing(urllib.urlopen(path))
    else:
        if not os.path.isfile(path):
            raise ValueError("File not found: %s" % path)

        line_iterator = open(path)

    return line_iterator


def _compute_tsv_header(obo_records):
    """Compute .tsv file header as a list of strings containing all tags in the given obo_records

    Args:
        obo_records (iter): iterator over .obo records
    """
    all_tags = set()
    for record in obo_records:
        for tag in record.keys():
            all_tags.add(tag)

    header = ['id', 'name']
    other_columns = sorted(list(all_tags - set(EXCLUDE_FROM_TSV) - set(header)))
    header.extend(other_columns)

    return header


def write_tsv(obo_records_dict, output_stream, root_id=None, separator=", "):
    """Write obo_records_dict to the given output_stream.

    Args:
        obo_records_dict (dict): data structure returned by parse_obo_format(..)
        output_stream (file): output stream where to write the .tsv file
        root_id (str): Only ontology terms that are either descendants of the
            given id or have this id themselves are returned. For example, 'HP:0000118'.
        separator (str): separator for concatenating multiple values in a single column
    """

    header = _compute_tsv_header(obo_records_dict.itervalues())
    output_stream.write("\t".join([RENAME_COLUMNS.get(column, column) for column in header]))
    output_stream.write("\n")
    for record in get_substree(obo_records_dict, root_id):
        row = []
        for tag in header:
            value = record.get(tag)
            if value is None:
                row.append("")
            elif isinstance(value, list):
                row.append(separator.join(map(str, value)))
            else:
                row.append(str(value))
        output_stream.write("\t".join(row))
        output_stream.write("\n")


def _confirm_id_is_valid(term_id, obo_records_dict, label="id"):
    """Raises an exception if the given term id doesn't exist in the given obo_records_dict."""

    if term_id not in obo_records_dict:
        raise ValueError("%s '%s' not found in ontology" % (label, term_id))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Parse an .obo file and write out a .tsv table")
    p.add_argument("-o", "--output-path", help="output .tsv file path. Defaults to standard out.",
        default="-")
    p.add_argument("-r", "--root-id", help="If specified, ignore ontology terms that are not "
        "either descendants of the given id or have this id themselves. For example: 'HP:0000118'.")
    p.add_argument("-c", "--add-category-column", action="store_true", help="add a 'category' "
        "column to the output .tsv file which lists each term's top-level category. A top-level "
        "category is a term that's a direct child of the ontology's root term.")
    p.add_argument("input_path", help=".obo file url or local file path. For example: "
        "http://purl.obolibrary.org/obo/hp.obo")
    p.add_argument("-v", "--verbose", action="store_true", help="Print stats and other info")
    args = p.parse_args()

    if args.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARN)

    convert_obo_to_tsv(
        args.input_path,
        output_path=args.output_path,
        root_id=args.root_id,
        add_category_column=args.add_category_column,
    )
