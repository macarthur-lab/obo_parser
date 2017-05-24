import os
import unittest

from obo_parser import _open_input_stream, parse_obo_format

OBO_FILE_PATH = os.path.join(os.path.dirname(__file__), "data/hpo_subset.obo")


class ParserTests(unittest.TestCase):

    def test_open_input_stream(self):
        self.assertRaises(ValueError, lambda: _open_input_stream(None))
        self.assertRaises(ValueError, lambda: _open_input_stream("dir/missing_file.obo"))

        with _open_input_stream(OBO_FILE_PATH) as input_stream:
            content = input_stream.read()
            file_size = len(content)
            self.assertGreater(file_size, 2000)

    def test_parse_obo_format(self):
        with _open_input_stream(OBO_FILE_PATH) as input_stream:
            obo_records_dict = parse_obo_format(input_stream)

        self.assertListEqual(list(obo_records_dict.keys()), [
            'HP:0000001', 'HP:0000118', 'HP:0012374', 'HP:0012372', 'HP:0004329',
            'HP:0001098', 'HP:0000478', 'HP:0000479', 'HP:0000480', 'HP:0000589',
            'HP:0000315', 'HP:0000271', 'HP:0000234', 'HP:0000152', 'HP:0007808',
        ])

        self.assertEqual(obo_records_dict['HP:0000480'].get('name'), "Retinal coloboma")
        self.assertEqual(obo_records_dict['HP:0000118'].get('name'), "Phenotypic abnormality")
        self.assertEqual(obo_records_dict['HP:0000234'].get('name'), "Abnormality of the head")
        self.assertEqual(obo_records_dict['HP:0000152'].get('name'), "Abnormality of head or neck")
        self.assertEqual(obo_records_dict['HP:0007808'].get('name'), "Bilateral retinal coloboma")

        self.assertEqual(
            obo_records_dict['HP:0000480'].get('def'),
            '"A notch or cleft of the retina." [HPO:probinson]')

        self.assertListEqual(
            obo_records_dict['HP:0000480'].get('is_a'),
            ['HP:0000479', 'HP:0000589'])
