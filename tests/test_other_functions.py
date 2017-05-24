import logging
import os
import sys
import unittest

if sys.version_info >= (3, 0):
    from io import StringIO
else:
    from StringIO import StringIO


from obo_parser import _open_input_stream, parse_obo_format, _compute_tsv_header, \
    compute_category_column, _compute_root_id, get_substree, \
    _confirm_id_is_valid, print_stats, write_tsv, logger

OBO_FILE_PATH = os.path.join(os.path.dirname(__file__), "data/hpo_subset.obo")


class ParserTests(unittest.TestCase):

    def setUp(self):
        with _open_input_stream(OBO_FILE_PATH) as input_stream:
            self.obo_records_dict = parse_obo_format(input_stream)

    def test_compute_root_id(self):
        self.obo_records_dict

    def test_compute_tsv_header(self):
        self.assertListEqual(_compute_tsv_header([]), ['id', 'name'])

        self.assertListEqual(_compute_tsv_header(self.obo_records_dict.values()), [
            'id', 'name', 'alt_id', 'comment', 'created_by', 'creation_date', 'def', 'is_a',
            'subset', 'synonym', 'xref'
        ])

    def test_compute_children_column(self):
        self.assertTrue('children' in self.obo_records_dict['HP:0000118'])
        self.assertTrue('children' in self.obo_records_dict['HP:0000480'])
        self.assertTrue('children' in self.obo_records_dict['HP:0000479'])

        self.assertListEqual(
            self.obo_records_dict['HP:0000118']['children'],
            ['HP:0000478', 'HP:0000152']
        )

    def test_compute_category_column(self):
        compute_category_column(self.obo_records_dict, root_id='HP:0000118')

        self.assertTrue('category_id' not in self.obo_records_dict['HP:0000118'])
        self.assertTrue('category_id' in self.obo_records_dict['HP:0000480'])
        self.assertTrue('category_id' in self.obo_records_dict['HP:0000479'])
        self.assertTrue('category_id' in self.obo_records_dict['HP:0007808'])

        self.assertEqual('HP:0000478', self.obo_records_dict['HP:0000480']['category_id'])
        self.assertEqual('HP:0000478', self.obo_records_dict['HP:0007808']['category_id'])
        self.assertEqual('HP:0000478', self.obo_records_dict['HP:0007808']['category_id'])
        self.assertEqual('HP:0000478', self.obo_records_dict['HP:0000478']['category_id'])
        self.assertEqual('HP:0000478', self.obo_records_dict['HP:0000479']['category_id'])

        self.assertEqual('HP:0000152', self.obo_records_dict['HP:0000152']['category_id'])
        self.assertEqual('HP:0000152', self.obo_records_dict['HP:0000234']['category_id'])
        self.assertEqual('HP:0000152', self.obo_records_dict['HP:0000271']['category_id'])

    def test_compute_tsv_header(self):
        self.assertListEqual(_compute_tsv_header([]), ['id', 'name'])
        self.assertListEqual(_compute_tsv_header(self.obo_records_dict.values()), [
            'id', 'name', 'alt_id', 'children',
            'comment', 'created_by', 'creation_date', 'def', 'is_a', 'subset', 'synonym', 'xref'
        ])

        compute_category_column(self.obo_records_dict, root_id='HP:0000118')

        self.assertListEqual(_compute_tsv_header(self.obo_records_dict.values()), [
            'id', 'name', 'alt_id', 'category_id', 'category_name', 'children',
            'comment', 'created_by', 'creation_date', 'def', 'is_a', 'subset', 'synonym', 'xref'
        ])

    def test_print_stats(self):
        # just test that the code runs without crashing
        logger.setLevel(logging.INFO)

        print_stats({}, 'input_path.obo')

        print_stats(self.obo_records_dict, 'input_path.obo')

    def test_get_subtree(self):
        subtree = {
            record['id']: record for record in get_substree(self.obo_records_dict, 'HP:0000118')
        }
        self.assertFalse('HP:000001' in subtree)
        self.assertTrue('HP:0000118' in subtree)
        self.assertTrue('HP:0000118' in subtree)

    def test_compute_root_id(self):
        root_id = _compute_root_id(self.obo_records_dict)
        self.assertEqual('HP:0000001', root_id)

        for root_id in ['HP:0000118', 'HP:0000479']:
            subtree = {
                record['id']: record for record in get_substree(self.obo_records_dict, root_id)
            }

            # unlink subtree from parent tree
            subtree[root_id]['is_a'] = None

            computed_root_id = _compute_root_id(subtree)
            self.assertEqual(root_id, computed_root_id)

    def test_confirm_id_is_valid(self):
        self.assertRaises(ValueError, lambda: _confirm_id_is_valid('HP:000ABC', self.obo_records_dict))

    def test_write_tsv(self):
        output_stream = StringIO()

        write_tsv(self.obo_records_dict, output_stream, root_id="HP:0000480")

        lines = output_stream.getvalue().rstrip('\n').split('\n')
        self.assertEqual(3, len(lines))
        self.assertEqual(lines[0], "id	name	alt_id	children	comment	created_by	creation_date	definition	parent_ids	subset	synonym	xref")
        self.assertEqual(lines[1], 'HP:0000480	Retinal coloboma		HP:0007808				"A notch or cleft of the retina." [HPO:probinson]	HP:0000479, HP:0000589	hposlim_core		SNOMEDCT_US:39302008, UMLS:C0240896')
        self.assertEqual(lines[2], "HP:0007808	Bilateral retinal coloboma							HP:0000480			UMLS:C4024797")

