# json_consistency_check

This script is used to check every json file in which the definition of a given value (e.g. port) was split into separate json files.
It counts occurrences of a given value for every json in user defined group.

These groups (of dependent json files) are defined at the bottom of this script in the main() function.


# description

Local variable "jsons_groups" is used to define groups of jsons files under test.
It is a dictionary with jsons group name (as a key) and list of its files (as its value).
These files are also defined as dictionaries to describe their "filename" and inner structure ("level_1_keys", "level_2_keys") as well as optional parameters ("check_type", "filters").

jsons_groups = {
    'some_group' : [
        {
            'filename' : 'some.json',
            'level_1_keys' : ['some_key'],
            'level_2_keys' : ['some_key'],
            'check_type' : CheckType.DEFAULT,
            'missing_value_filters' : [r'some_regex']
        }
    ]
}

Typical json structure is usually represented by the "root dictionary" in which value of the "root key" is a list of "level 1 dictionaries",
in which values of their "level 1 keys" are also lists of "level 2 dictionaries" and so on.

Therefore level_1_keys and level_2_keys variables are used to represent this json structure.
    level_1_keys parameter needs to be defined
    level_2_keys parameter is optional
    (simply put they are used to find a way to list of values to be checked)

So what is being tested?
  By default, every value (e.g. port) is expected to occur exactly once in every json file of a group.

  Example 1: default behaviour without "check_type" and "missing_value_filters" set:
      json_A          [1,2,3]         PASS
      json_B          [1,2,3]         PASS
      json_C          [1,2,3]         PASS
      ------------------------------------
      json_A          [1,2]           FAIL
      json_B          [1,2,3]         FAIL
      json_C          [1,2,3]         FAIL
      ------------------------------------
      json_A          [1,2,3,4]       FAIL
      json_B          [1,2,3]         FAIL
      json_C          [1,2,3]         FAIL
      ------------------------------------
      json_A          [1,2,3,1]       FAIL
      json_B          [1,2,3]         FAIL
      json_C          [1,2,3]         FAIL

This behaviour can be altered by using optional parameters such as "missing_value_filters" and "check_type":
- "missing_value_filters" parameter is a list of regex strings, used to match values (e.g. ports) which should be ignored during testing of current json file
- "check_type" parameter lets you check if values from tested json file (the one with "check_type" set to CheckType.IS_SUBSET) are present in other json files
      in other words - check if tested json is a subset of other json files

  Example 2A: if tested json contains [1,2,3] and other json contains [1,2,3,4,5] then test will PASS
  Example 2B: if there is another json without check_type parameter defined, then standard rules apply:
      i.e. both other jsons must contain whole range of values, available in a given jsons group and without duplicates
      so in this example they both need [1,2,3,4,5] to PASS

  Example 2A:
      tested json     [1,2,3]         PASS
      other json      [1,2,3,4,5]     PASS

  Example 2B:
      tested json     [1,2,3]         PASS
      other json      [1,2,3,4,5]     PASS
      other json      [1,2,3,4,5]     PASS
      ------------------------------------
      tested json     [1,2,3]         PASS
      other json      [1,2,3,4,5,6]   FAIL
      other json      [1,2,3,4,5]     FAIL
      ------------------------------------
      tested json     [1,2,3]         PASS
      other json      [1,2,3,4,5,5]   FAIL
      other json      [1,2,3,4,5,5]   FAIL
