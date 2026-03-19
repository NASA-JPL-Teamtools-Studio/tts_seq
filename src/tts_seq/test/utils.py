from difflib import Differ

def assert_files_same(input_path, output_path, expected_path):
    output = open(output_path,'r').read()
    expected = open(expected_path,'r').read()
    dd = Differ()
    result = list(dd.compare(output.splitlines(), expected.splitlines()))

    assert output == expected, "\n".join(result) + f"\n\ntkdiff {expected_path} {output_path}\n{input_path}"
