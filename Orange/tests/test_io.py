# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring

import unittest
from unittest.mock import Mock, patch
import os
import tempfile
import shutil
import io

from Orange import data

from Orange.data.io import FileFormat, TabReader, CSVReader, PickleReader
from Orange.data.table import get_sample_datasets_dir
from Orange.data import Table, Variable
from Orange.tests import test_dirname


class WildcardReader(FileFormat):
    EXTENSIONS = ('.wild', '.wild[0-9]')
    DESCRIPTION = "Dummy reader for testing extensions"

    def read(self):
        pass


class TestChooseReader(unittest.TestCase):

    def test_usual_extensions(self):
        self.assertIsInstance(FileFormat.get_reader("t.tab"), TabReader)
        self.assertIsInstance(FileFormat.get_reader("t.csv"), CSVReader)
        self.assertIsInstance(FileFormat.get_reader("t.pkl"), PickleReader)
        with self.assertRaises(OSError):
            FileFormat.get_reader("test.undefined_extension")

    def test_wildcard_extension(self):
        self.assertIsInstance(FileFormat.get_reader("t.wild"),
                              WildcardReader)
        self.assertIsInstance(FileFormat.get_reader("t.wild2"),
                              WildcardReader)
        with self.assertRaises(OSError):
            FileFormat.get_reader("t.wild2a")


class SameExtension(FileFormat):
    PRIORITY = 100
    EXTENSIONS = ('.same_extension',)
    DESCRIPTION = "Same extension, different priority"

    def read(self):
        pass


class SameExtensionPreferred(SameExtension):
    PRIORITY = 90


class SameExtensionL(SameExtension):
    PRIORITY = 110


class TestMultipleSameExtension(unittest.TestCase):

    def test_find_reader(self):
        reader = FileFormat.get_reader("some.same_extension")
        self.assertIsInstance(reader, SameExtensionPreferred)


class TestLocate(unittest.TestCase):

    def test_locate_sample_datasets(self):
        with self.assertRaises(OSError):
            FileFormat.locate("iris.tab",
                              search_dirs=[os.path.dirname(__file__)])
        iris = FileFormat.locate("iris.tab",
                                 search_dirs=[get_sample_datasets_dir()])
        self.assertEqual(os.path.basename(iris), "iris.tab")
        # test extension adding
        iris = FileFormat.locate("iris",
                                 search_dirs=[get_sample_datasets_dir()])
        self.assertEqual(os.path.basename(iris), "iris.tab")

    def test_locate_wildcard_extension(self):
        tempdir = tempfile.mkdtemp()
        with self.assertRaises(OSError):
            FileFormat.locate("t.wild9", search_dirs=[tempdir])
        fn = os.path.join(tempdir, "t.wild8")
        with open(fn, "wt") as f:
            f.write("\n")
        location = FileFormat.locate("t.wild8", search_dirs=[tempdir])
        self.assertEqual(location, fn)
        # test extension adding
        location = FileFormat.locate("t", search_dirs=[tempdir])
        self.assertEqual(location, fn)
        shutil.rmtree(tempdir)


class TestReader(unittest.TestCase):

    def setUp(self):
        Variable._clear_all_caches()
        data.table.dataset_dirs.append(test_dirname())

    def tearDown(self):
        data.table.dataset_dirs.remove(test_dirname())

    def test_open_bad_pickle(self):
        """
        Raise TypeError when PickleReader reads a pickle
        file without a table (and it suppose to be there).
        GH-2232
        """
        reader = PickleReader("")
        with unittest.mock.patch("pickle.load", return_value=None):
            self.assertRaises(TypeError, reader.read, "foo")

    def test_empty_columns(self):
        """Can't read files with more columns then headers. GH-1417"""
        samplefile = """\
        a, b
        1, 0,
        1, 2,
        """
        c = io.StringIO(samplefile)
        with self.assertWarns(UserWarning) as cm:
            table = CSVReader(c).read()
        self.assertEqual(len(table.domain.attributes), 2)
        self.assertEqual(cm.warning.args[0],
                         "Columns with no headers were removed.")

    def test_type_annotations(self):
        class FooFormat(FileFormat):
            write_file = Mock()

        FooFormat.write('test_file', None)
        FooFormat.write_file.assert_called_with('test_file', None)

        FooFormat.OPTIONAL_TYPE_ANNOTATIONS = True
        FooFormat.write('test_file', None)
        FooFormat.write_file.assert_called_with('test_file', None, True)

        FooFormat.write('test_file', None, False)
        FooFormat.write_file.assert_called_with('test_file', None, False)

        FooFormat.OPTIONAL_TYPE_ANNOTATIONS = False
        FooFormat.write('test_file', None)
        FooFormat.write_file.assert_called_with('test_file', None)

    @patch('csv.DictWriter.writerow')
    def test_header_call(self, writer):
        CSVReader.write_headers(writer, Table("iris"), False)
        self.assertEqual(len(writer.call_args_list), 1)

        writer.reset_mock()
        CSVReader.write_headers(writer, Table("iris"), True)
        self.assertEqual(len(writer.call_args_list), 3)

    def test_load_pickle(self):
        """
        This function tests whether pickled files in older Orange loads
        correctly with newer version of Orange.
        """
        # load pickles created with Orange 3.20
        # in next version there is a change in variables.py - line 738
        # which broke back compatibility - tests were introduced after the fix
        data1 = Table("datasets/sailing-orange-3-20.pkl")
        data2 = Table("datasets/sailing-orange-3-20.pkl.gz")

        # load pickles created with Orange 3.21
        data3 = Table("datasets/sailing-orange-3-21.pkl")
        data4 = Table("datasets/sailing-orange-3-21.pkl.gz")

        examples_count = 20
        self.assertEqual(examples_count, len(data1))
        self.assertEqual(examples_count, len(data2))
        self.assertEqual(examples_count, len(data3))
        self.assertEqual(examples_count, len(data4))

        attributes_count = 3
        self.assertEqual(attributes_count, len(data1.domain.attributes))
        self.assertEqual(attributes_count, len(data2.domain.attributes))
        self.assertEqual(attributes_count, len(data3.domain.attributes))
        self.assertEqual(attributes_count, len(data4.domain.attributes))
