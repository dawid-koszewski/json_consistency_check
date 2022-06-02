#!/usr/bin/python3

# =====================================================================================================================================
# This script is used to check every json file in which the definition of a given value (e.g. port) was split into separate json files.
# It counts occurrences of a given value for every json in user defined group.
#
# These groups (of dependent json files) are defined at the bottom of this script in the main() function.
#
# Author: Dawid Koszewski
# Created: 2022.02.22
# =====================================================================================================================================

import sys
import os
import json
import re
import enum
import unittest
from unittest.mock import patch


def get_path_from_argument():
    path = "."
    try:
        path = sys.argv[1]
    except Exception:
        print("\nPlease provide path to json files as first parameter (if no parameter is provided, script will start searching in current working directory)\n")
    return path


class CheckType(enum.Enum):
    DEFAULT = 0
    IS_SUBSET = 1


class JsonFileError(enum.Enum):
    NO_FILE = 0
    FILE_EMPTY = 1
    FIELD_EMPTY = 2


class JsonGroupError(enum.Enum):
    WRONG_KEYS = 0
    MISSING_NESTED_KEY = 1


class FileOperations:
    @staticmethod
    def read_file(path_to_file):
        file_content = None
        try:
            f = open(path_to_file, 'r')
            try:
                file_content = f.read()
            except (OSError, IOError) as e:
                print("read_file: %s: %s" % (path_to_file, e))
            f.close()
        except Exception as e:
            # print("read_file: %s: %s" % (path_to_file, e))
            pass
        return file_content


class JsonData:
    __json_data = None

    def __init__(self, json_data):
        self.__json_data = json_data

    def __add_item_to_items_list(self, items_list, item):
        if type(item) is list:
            # items_list.extend(item)
            for i in item:
                self.__add_item_to_items_list(items_list, i) # to cover case of nested sublists
        else:
            items_list.append(item)

    def __analyse_list(self, items_list, level_keys, lvl_counter, cur_lvl):
        for cur_lvl_item in cur_lvl:
            self.__analyse_level(items_list, level_keys, lvl_counter, cur_lvl_item)

    def __jump_to_next_level(self, items_list, level_keys, lvl_counter, cur_lvl, next_lvl_keys):
        lvl_counter += 1
        if next_lvl_keys:
            for next_lvl_key in next_lvl_keys:
                next_lvl = cur_lvl.get(next_lvl_key, None)
                self.__analyse_level(items_list, level_keys, lvl_counter, next_lvl)

    def __analyse_dict(self, items_list, level_keys, lvl_counter, cur_lvl):
        next_lvl_keys = level_keys.get(lvl_counter, None)
        if not next_lvl_keys:
            self.__add_item_to_items_list(items_list, JsonGroupError.MISSING_NESTED_KEY)
        else:
            self.__jump_to_next_level(items_list, level_keys, lvl_counter, cur_lvl, next_lvl_keys)

    def __analyse_level(self, items_list, level_keys, lvl_counter, cur_lvl):
        if cur_lvl is None:
            self.__add_item_to_items_list(items_list, JsonGroupError.WRONG_KEYS)
        elif not cur_lvl:
            self.__add_item_to_items_list(items_list, JsonFileError.FIELD_EMPTY)
        elif type(cur_lvl) is dict:
            self.__analyse_dict(items_list, level_keys, lvl_counter, cur_lvl)
        elif type(cur_lvl) is list:
            self.__analyse_list(items_list, level_keys, lvl_counter, cur_lvl)
        else:
            self.__add_item_to_items_list(items_list, cur_lvl)

    def get_json_values_list(self, level_keys):
        items_list = []
        lvl_counter = 1
        cur_lvl = self.__json_data

        if cur_lvl is None:
            self.__add_item_to_items_list(items_list, JsonFileError.NO_FILE)
        elif not cur_lvl:
            self.__add_item_to_items_list(items_list, JsonFileError.FILE_EMPTY)
        else:
            self.__analyse_level(items_list, level_keys, lvl_counter, cur_lvl)

        return items_list


class JsonFile:
    __path_to_file = None
    __file_content = None
    __json_data = None

    def __read_json_file(self):
        self.__file_content = FileOperations.read_file(self.__path_to_file)

    def __read_json_data(self):
        json_data = None

        if self.__file_content:
            try:
                json_data = json.loads(self.__file_content)
            except Exception:
                try:
                    # fix orphaned semicolons - for example: { [ 1, 2, 3, ], }
                    self.__file_content = re.sub(r',(\s*\r*\n*)(\s*)(]|})', r'\1\2\3', self.__file_content)
                    # add double quotes to enum values and hexadecimals - for example: "type" : TYPE
                    self.__file_content = re.sub(r'(\"?)([A-Za-z0-9._-]+)(\"?)', r'"\2"', self.__file_content)
                    json_data = json.loads(self.__file_content)
                except Exception as e:
                    print("\n__read_json_data: Failed to load json data: %s: %s\n" % (self.__path_to_file, e))

        self.__json_data = JsonData(json_data)

    def get_json_data(self, path_to_dir, filename):
        self.__path_to_file = os.path.join(path_to_dir, filename)
        if not self.__file_content:
            self.__read_json_file()
        if not self.__json_data:
            self.__read_json_data()
        return self.__json_data


class JsonValuesCounter:
    __jsons_group = None
    __filename = None

    def __init__(self, jsons_group, filename):
        self.__jsons_group = jsons_group
        self.__filename = filename

    def __get_all_files_counter(self):
        all_files_counter = {}
        for json_file in self.__jsons_group:
            filename = json_file.get('filename')
            all_files_counter[filename] = 0
        return all_files_counter

    def count_values(self, all_values_counter, json_values_list):
        for value in json_values_list:
            all_values_counter.setdefault(value, self.__get_all_files_counter())
            all_values_counter[value][self.__filename] += 1


class DirectoryAnalyzer:
    __path_to_dir = None
    __jsons_group = None
    __all_values_counter = None
    __table_name = None
    __first_column_width = None
    __files_missing_values = None
    __files_other_issues = None

    def __init__(self, path_to_dir, jsons_group):
        self.__path_to_dir = path_to_dir
        self.__jsons_group = jsons_group
        self.__all_values_counter = {}
        self.__table_name = "occurrence of value in files:"
        self.__first_column_width = max(len(self.__table_name), 35)
        self.__files_missing_values = dict()
        self.__files_other_issues = dict()

    def __is_value_in_missing_value_filters(self, value, missing_value_filters):
        if missing_value_filters:
            for missing_value_filter in missing_value_filters:
                if re.search(missing_value_filter, str(value)):
                    return True
        return False

    def __is_value_in_json_error_filters(self, value, json_error_filters):
        if json_error_filters:
            if value in json_error_filters:
                return True
        return False

    def __is_mismatch(self, value, all_files_counter, json_error_in_values):
        mismatch = False
        for json_file in self.__jsons_group:
            filename = json_file.get('filename')
            check_type = json_file.get('check_type', CheckType.DEFAULT)
            expected_occurrence = int(json_file.get('expected_occurrence', 1))
            missing_value_filters = json_file.get('missing_value_filters', None)
            json_error_filters = json_file.get('json_error_filters', None)

            self.__files_missing_values.setdefault(filename, [])
            self.__files_other_issues.setdefault(filename, [])

            if isinstance(value, JsonFileError) or isinstance(value, JsonGroupError):
                if self.__is_value_in_json_error_filters(value, json_error_filters):
                    pass
                elif all_files_counter[filename] == 0:
                    pass
                else:
                    self.__files_other_issues[filename].append(str(value))
                    mismatch = True
            else:
                if self.__is_value_in_missing_value_filters(value, missing_value_filters):
                    pass
                elif all_files_counter[filename] == 0 and json_error_in_values:
                    pass
                elif all_files_counter[filename] == 0 and check_type == CheckType.IS_SUBSET:
                    pass
                elif all_files_counter[filename] == expected_occurrence:
                    pass
                else:
                    self.__files_missing_values[filename].append(str(value))
                    mismatch = True
        return mismatch

    def __print_summary(self):
        print()
        for filename, other_issues in self.__files_other_issues.items():
            if other_issues:
                print('Error: %s has issues: %s' % (filename, other_issues))
        for filename, missing_values in self.__files_missing_values.items():
            if missing_values:
                print('Error: %s has missing values: %s' % (filename, missing_values))
        print("----------------------------------------------------------------------\n\n")

    def __print_line(self, value, all_files_counter):
        value_line = '%%-%ds |' % (self.__first_column_width) % ('\"%s\"' % value)
        for json_file in self.__jsons_group:
            filename = json_file.get('filename')
            value_line += (' %%%dd |' % (len(filename)) % (all_files_counter[filename]))
        print(value_line)

    def __print_title(self):
        title = '%%-%ds |' % (self.__first_column_width) % (self.__table_name)
        for json_file in self.__jsons_group:
            filename = json_file.get('filename')
            title += (' %s |' % filename)
        print("Directory: %s\n" % (self.__path_to_dir))
        print(title)

    def __check_for_errors(self):
        error_in_directory = False
        json_error_in_values = False

        for json_error in JsonFileError:
            if json_error in self.__all_values_counter:
                json_error_in_values = True

        for json_error in JsonGroupError:
            if json_error in self.__all_values_counter:
                json_error_in_values = True

        for value, all_files_counter in self.__all_values_counter.items():
            if self.__is_mismatch(value, all_files_counter, json_error_in_values):
                if not error_in_directory:
                    error_in_directory = True
                    self.__print_title()
                self.__print_line(value, all_files_counter)

        if error_in_directory:
            self.__print_summary()

        return error_in_directory

    def detect_inconsistencies(self):
        for json_file in self.__jsons_group:
            filename = json_file.get('filename')
            level_keys = json_file.get('level_keys')

            json_file = JsonFile()
            json_data = json_file.get_json_data(self.__path_to_dir, filename)
            json_values_list = json_data.get_json_values_list(level_keys)
            json_values_counter = JsonValuesCounter(self.__jsons_group, filename)
            json_values_counter.count_values(self.__all_values_counter, json_values_list)

        return self.__check_for_errors()


class JsonsGroupAnalyzer:
    __jsons_group = None
    __path_to_json_files = None
    __do_not_print_these_paths = None
    __ignored_paths = None

    def __init__(self, jsons_group, path_to_json_files, do_not_print_these_paths):
        self.__jsons_group = jsons_group
        self.__path_to_json_files = path_to_json_files
        self.__do_not_print_these_paths = do_not_print_these_paths
        self.__ignored_paths = []

    def __print_ignored_paths(self):
        for path in self.__ignored_paths:
            print(path)

    def __add_to_ignored_paths(self, path_name, path_to_dir):
        if not self.__is_path_matching(path_to_dir, self.__do_not_print_these_paths):
            self.__ignored_paths.append("%s: %s" % (path_name, path_to_dir))

    def __is_path_matching(self, path, paths_matcher):
        if paths_matcher:
            for path_matcher in paths_matcher:
                if re.search(path_matcher, str(path)):
                    return True
        return False

    def traverse_directory_tree(self, include_paths, exclude_paths):
        mismatch_detected = False

        for path_to_dir, subdirs, files in os.walk(self.__path_to_json_files):
            if self.__is_path_matching(path_to_dir, exclude_paths):
                self.__add_to_ignored_paths("excluded path", path_to_dir)
            elif self.__is_path_matching(path_to_dir, include_paths):
                directory_analyzer = DirectoryAnalyzer(path_to_dir, self.__jsons_group)
                if directory_analyzer.detect_inconsistencies():
                    mismatch_detected = True
            else:
                self.__add_to_ignored_paths("omitted path", path_to_dir)
        self.__print_ignored_paths()

        return mismatch_detected


class AllJsonsGroupsAnalyzer:
    __jsons_groups = None
    __path_to_json_files = None
    __do_not_print_these_paths = None

    def __init__(self, jsons_groups, path_to_json_files, do_not_print_these_paths):
        self.__jsons_groups = jsons_groups
        self.__path_to_json_files = path_to_json_files
        self.__do_not_print_these_paths = do_not_print_these_paths

    def __get_jsons_group_paths(self, jsons_group_name):
        jsons_group_name_paths = jsons_group_name + '_paths'
        jsons_group_paths = self.__jsons_groups.get(jsons_group_name_paths, None)
        include_paths = []
        exclude_paths = []

        if jsons_group_paths:
            for paths in jsons_group_paths:
                include_paths.extend(paths.get('include_paths', []))
                exclude_paths.extend(paths.get('exclude_paths', []))

        if not include_paths:
            include_paths = [r'.*']
        if not exclude_paths:
            exclude_paths = [r'\.git']

        return include_paths, exclude_paths

    def __check_jsons_group(self, jsons_group_name, jsons_group):
        print("\n\n======================================================================")
        print("======================================================================")
        print("======================================================================")
        print("Checking values definitions consistency for jsons group \"%s\"...\n\n" % (jsons_group_name))

        jsons_group_analyzer = JsonsGroupAnalyzer(jsons_group, self.__path_to_json_files, self.__do_not_print_these_paths)
        include_paths, exclude_paths = self.__get_jsons_group_paths(jsons_group_name)
        mismatch_detected = jsons_group_analyzer.traverse_directory_tree(include_paths, exclude_paths)

        if mismatch_detected:
            print("\n\nJsons group \"%s\": values definitions mismatch [ERROR]\n" % (jsons_group_name))
        else:
            print("\n\nJsons group \"%s\": values definitions valid [OK]\n" % (jsons_group_name))

        return mismatch_detected

    def check_definitions_consistency(self):
        result = 0

        for jsons_group_name, jsons_group in self.__jsons_groups.items():
            if jsons_group_name.endswith('_paths'):
                pass
            else:
                result += self.__check_jsons_group(jsons_group_name, jsons_group)

        return result


#========================
#=== UNIT TESTS BEGIN ===
#========================

class ConsistencyCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):

# used in Example 1:
        cls.jsons_group_1 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1'],
                    2 : ['A2']
                }
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1'],
                    2 : ['B2']
                }
            },
            {
                'filename' : 'fileC.json',
                'level_keys' : {
                    1 : ['C1'],
                    2 : ['C2']
                }
            }
        ]

# used in Example 2A:
        cls.jsons_group_2a = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1'],
                    2 : ['A2']
                },
                'check_type' : CheckType.IS_SUBSET
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1'],
                    2 : ['B2']
                }
            }
        ]

# used in Example 2B:
        cls.jsons_group_2 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1'],
                    2 : ['A2']
                },
                'check_type' : CheckType.IS_SUBSET
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1'],
                    2 : ['B2']
                }
            },
            {
                'filename' : 'fileC.json',
                'level_keys' : {
                    1 : ['C1'],
                    2 : ['C2']
                }
            }
        ]

# used in Example 3:
        cls.jsons_group_3 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1'],
                    2 : ['A2'],
                    3 : ['A3']
                }
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1'],
                    2 : ['B2'],
                    3 : ['B3']
                }
            }
        ]

# used in Example 4:
        cls.jsons_group_4 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1']
                }
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1']
                }
            }
        ]

# used in Example 5:
        cls.jsons_group_5 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1'],
                    2 : ['A2']
                }
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1'],
                    2 : ['B2']
                }
            }
        ]

# used in Example 6:
        cls.jsons_group_6 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1']
                }
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1']
                },
                'check_type' : CheckType.IS_SUBSET,
            },
            {
                'filename' : 'fileC.json',
                'level_keys' : {
                    1 : ['C1']
                },
                'check_type' : CheckType.IS_SUBSET,
                'json_error_filters' : [JsonFileError.NO_FILE]
            },
            {
                'filename' : 'fileD.json',
                'level_keys' : {
                    1 : ['D1']
                },
                'check_type' : CheckType.IS_SUBSET,
                'json_error_filters' : [JsonFileError.NO_FILE]
            }
        ]

# used in Example 7:
        cls.jsons_group_7 = [
            {
                'filename' : 'fileA.json',
                'level_keys' : {
                    1 : ['A1']
                }
            },
            {
                'filename' : 'fileB.json',
                'level_keys' : {
                    1 : ['B1']
                },
                'missing_value_filters' : [r'4', r'5']
            }
        ]

    def setUp(self):
        super().setUp()
        self.path_to_dir = unittest.TestCase.id(self)

    @classmethod
    def mock_get_json_data(cls, filename, listA = None, listB = None, listC = None, listD = None):
        if   filename == 'fileA.json' and listA is not None: return JsonData({ "A1" : listA })
        elif filename == 'fileB.json' and listB is not None: return JsonData({ "B1" : listB })
        elif filename == 'fileC.json' and listC is not None: return JsonData({ "C1" : listC })
        elif filename == 'fileD.json' and listD is not None: return JsonData({ "D1" : listD })
        else: return JsonData(None)

# Example 1:
    @patch('__main__.JsonFile')
    def test_group_1_2levelnest____fileA_fileB_fileC_the_same____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_1)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_1_2levelnest____fileA_one_missing_value____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_1)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_1_2levelnest____fileA_one_extra_value____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}, {"A2" : 4}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_1)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_1_2levelnest____fileA_repeated_extra_value____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}, {"A2" : 1}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_1)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

# Example 2A:
    @patch('__main__.JsonFile')
    def test_group_2_2levelnest_check_type_is_subset____fileA_two_missing_values____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}, {"B2" : 4}, {"B2" : 5}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_2a)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

# Example 2B:
    @patch('__main__.JsonFile')
    def test_group_2_2levelnest_check_type_is_subset____fileA_two_missing_values_fileB_fileC_the_same____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}, {"B2" : 4}, {"B2" : 5}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}, {"C2" : 4}, {"C2" : 5}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_2)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_2_2levelnest_check_type_is_subset____fileA_two_missing_values_fileB_one_extra_value____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}, {"B2" : 4}, {"B2" : 5}, {"B2" : 6}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}, {"C2" : 4}, {"C2" : 5}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_2)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_2_2levelnest_check_type_is_subset____fileA_two_missing_values_fileB_and_fileC_repeated_extra_values____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}, {"A2" : 2}, {"A2" : 3}],
            [{"B2" : 1}, {"B2" : 2}, {"B2" : 3}, {"B2" : 4}, {"B2" : 5}, {"B2" : 5}],
            [{"C2" : 1}, {"C2" : 2}, {"C2" : 3}, {"C2" : 4}, {"C2" : 5}, {"C2" : 5}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_2)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

# Example 3:
    @patch('__main__.JsonFile')
    def test_group_3_3levelnest____fileA_fileB_the_same____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : [{"A3" : 1}]}, {"A2" : [{"A3" : 2}]}, {"A2" : [{"A3" : 3}]}],
            [{"B2" : [{"B3" : 1}]}, {"B2" : [{"B3" : 2}]}, {"B2" : [{"B3" : 3}]}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_3)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_3_3levelnest____fileA_one_missing_value____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : [{"A3" : 1}]}, {"A2" : [{"A3" : 2}]}],
            [{"B2" : [{"B3" : 1}]}, {"B2" : [{"B3" : 2}]}, {"B2" : [{"B3" : 3}]}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_3)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

# Example 4:
    @patch('__main__.JsonFile')
    def test_group_4_1levelnest____fileA_fileB_the_same____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_4)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_4_1levelnest____fileB_one_extra_value____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [1, 2]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_4)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

# Example 5:
    @patch('__main__.JsonFile')
    def test_group_5_2levelnest____fileB_NO_FILE____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_5)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_5_2levelnest____fileA_fileB_FILE_EMPTY____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : JsonData({ })

        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_5)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_5_2levelnest____fileB_FIELD_EMPTY____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}],
            []
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_5)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_5_2levelnest____fileB_WRONG_KEYS____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : 1}],
            [{"Y2" : 1}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_5)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_5_2levelnest____fileA_fileB_MISSING_NESTED_KEY____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [{"A2" : [{"A3" : 1}]}],
            [{"B2" : [{"B3" : 1}]}]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_5)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

# Example 6:
    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileA_fileB_fileC_fileD_the_same____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [1],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileA_JsonFileError_NO_FILE_no_filter____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [JsonFileError.NO_FILE],
            [1],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileB_JsonFileError_NO_FILE_no_filter____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [JsonFileError.NO_FILE],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertTrue(directory_analyzer.detect_inconsistencies())


    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileB_JsonFileError_FILE_EMPTY_no_filter____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [JsonFileError.FILE_EMPTY],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileB_JsonFileError_FIELD_EMPTY_no_filter____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [JsonFileError.FIELD_EMPTY],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileB_JsonGroupError_WRONG_KEYS_no_filter____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [JsonGroupError.WRONG_KEYS],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileB_JsonGroupError_MISSING_NESTED_KEY_no_filter____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [JsonGroupError.MISSING_NESTED_KEY],
            [1],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileC_JsonFileError_NO_FILE____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [1],
            [JsonFileError.NO_FILE],
            [1]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_6_1levelnest____fileD_JsonFileError_NO_FILE____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1],
            [1],
            [1],
            [JsonFileError.NO_FILE]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_6)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

# Example 7:
    @patch('__main__.JsonFile')
    def test_group_7_1levelnest____fileA_fileB_the_same____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1,2,3],
            [1,2,3]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_7)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_7_1levelnest____fileB_using_missing_value_filters____passed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1,2,3,4,5],
            [1,2,3]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_7)
        self.assertFalse(directory_analyzer.detect_inconsistencies())

    @patch('__main__.JsonFile')
    def test_group_7_1levelnest____fileA_not_using_missing_value_filters____failed(self, mock_JsonFile):
        mock_JsonFile().get_json_data.side_effect = lambda path_to_dir, filename : self.mock_get_json_data(filename,
            [1,2,3],
            [1,2,3,4,5]
        )
        directory_analyzer = DirectoryAnalyzer(self.path_to_dir, self.jsons_group_7)
        self.assertTrue(directory_analyzer.detect_inconsistencies())

#======================
#=== UNIT TESTS END ===
#======================


# Local variable "jsons_groups" is used to define groups of jsons files under test.
# It is a dictionary with jsons group name (as a key) and list of its files (as its value).
# These files are also defined as dictionaries to describe their "filename" and inner structure ("level_1_keys", "level_2_keys") as well as optional parameters ("check_type", "filters").
#
# jsons_groups = {
#     'some_group' : [
#         {
#             'filename' : 'some.json',
#             'level_1_keys' : ['some_key'],
#             'level_2_keys' : ['some_key'],
#             'check_type' : CheckType.DEFAULT,
#             'missing_value_filters' : [r'some_regex']
#         }
#     ]
# }
#
# Typical json structure is usually represented by the "root dictionary" in which value of the "root key" is a list of "level 1 dictionaries",
# in which values of their "level 1 keys" are also lists of "level 2 dictionaries" and so on.
#
# Therefore level_1_keys and level_2_keys variables are used to represent this json structure.
#     level_1_keys parameter needs to be defined
#     level_2_keys parameter is optional
#     (simply put they are used to find a way to list of values to be checked)
#
# So what is being tested?
#   By default, every value (e.g. port) is expected to occur exactly once in every json file of a group.
#
#   Example 1: default behaviour without "check_type" and "missing_value_filters" set:
#       json_A          [1,2,3]         PASS
#       json_B          [1,2,3]         PASS
#       json_C          [1,2,3]         PASS
#       ------------------------------------
#       json_A          [1,2]           FAIL
#       json_B          [1,2,3]         FAIL
#       json_C          [1,2,3]         FAIL
#       ------------------------------------
#       json_A          [1,2,3,4]       FAIL
#       json_B          [1,2,3]         FAIL
#       json_C          [1,2,3]         FAIL
#       ------------------------------------
#       json_A          [1,2,3,1]       FAIL
#       json_B          [1,2,3]         FAIL
#       json_C          [1,2,3]         FAIL
#
# This behaviour can be altered by using optional parameters such as "missing_value_filters" and "check_type":
# - "missing_value_filters" parameter is a list of regex strings, used to match values (e.g. ports) which should be ignored during testing of current json file
# - "check_type" parameter lets you check if values from tested json file (the one with "check_type" set to CheckType.IS_SUBSET) are present in other json files
#       in other words - check if tested json is a subset of other json files
#
#   Example 2A: if tested json contains [1,2,3] and other json contains [1,2,3,4,5] then test will PASS
#   Example 2B: if there is another json without check_type parameter defined, then standard rules apply:
#       i.e. both other jsons must contain whole range of values, available in a given jsons group and without duplicates
#       so in this example they both need [1,2,3,4,5] to PASS
#
#   Example 2A:
#       tested json     [1,2,3]         PASS
#       other json      [1,2,3,4,5]     PASS
#
#   Example 2B:
#       tested json     [1,2,3]         PASS
#       other json      [1,2,3,4,5]     PASS
#       other json      [1,2,3,4,5]     PASS
#       ------------------------------------
#       tested json     [1,2,3]         PASS
#       other json      [1,2,3,4,5,6]   FAIL
#       other json      [1,2,3,4,5]     FAIL
#       ------------------------------------
#       tested json     [1,2,3]         PASS
#       other json      [1,2,3,4,5,5]   FAIL
#       other json      [1,2,3,4,5,5]   FAIL


def main():
    jsons_groups = {
# ====== jsons_group_1 ======================================================================
        'jsons_group_1' : [
            {
                'filename' : 'configuration.json',
                'level_keys' : {
                    1 : ['config'],
                    2 : ['port']
                }
            },
            {
                'filename' : 'settings.json',
                'level_keys' : {
                    1 : ['settings'],
                    2 : ['port']
                },
                'check_type' : CheckType.IS_SUBSET,
                'expected_occurrence' : 4,
                'missing_value_filters' : [r'^port1$', r'^port2$'],
                'json_error_filters' : [JsonFileError.FIELD_EMPTY],
            },
            {
                'filename' : 'parameters.json',
                'level_keys' : {
                    1 : ['parameters'],
                    2 : ['port']
                }
            }
        ],
        'jsons_group_1_paths' : [
            {
                'include_paths' : [
                    r'^\.(/|\\)directory(/|\\)[^/\\]*$'                     # this regex matches only paths like: ./directory/<subdir>
                                                                            # in general it is safer to include as much as possible, and then specify exclude paths
                                                                            # i.e. if you include here only one directory and someone will add another directory to repository
                                                                            # but will forget to also include it here - then that directory will not be checked
                ],
                'exclude_paths' : [
                    r'subdirA',
                    r'subdirB.some_nested_dir'
                ]
            }
        ] # ,
# ====== next jsons_group... ======================================================================
    }

    do_not_print_these_paths = [
        r'^\.[/\\]?$',                  # root dir
        r'\.git',                       # .git
        r'\.vscode'                     # .vscode
    ]

    path_to_json_files = get_path_from_argument()
    all_jsons_groups_analyzer = AllJsonsGroupsAnalyzer(jsons_groups, path_to_json_files, do_not_print_these_paths)
    return all_jsons_groups_analyzer.check_definitions_consistency()


if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    runner = unittest.TextTestRunner(buffer=True, stream=open(os.devnull, 'w')) # when you need to DEBUG unit tests use TextTestRunner() without parameters

    tests = loader.loadTestsFromTestCase(ConsistencyCheckTest)
    suite.addTests(tests)
    result = runner.run(suite)
    self_test_result = not result.wasSuccessful()

    if self_test_result > 0:
        print("\n======================================================================")
        print("========================== SELF TEST FAILED ==========================")
        print("======================================================================\n")

    main_test_result = main()

    if main_test_result > 0:
        print("\n\nSUMMARY: Values definitions consistency check ERROR!\n")
    else:
        print("\n\nSUMMARY: Values definitions consistency check OK!\n")

    if self_test_result > 0:
        print("\nSELF TEST FAILED!!!\n")

    sys.exit(self_test_result + main_test_result)
