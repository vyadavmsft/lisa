#
# This script converts the test case XMLs from LISAv2 into test stubs for
# the Pytest version of LISAv3.  It tries its best to generate pytest marks
# with the correct types, the right categories, etc.  All generated stubs
# are marked with a @skip decorator.
#
# Usage: run the script from any directory under the LISAv2 directory tree;
# the script will be able to find the test case XMLs and produce the test
# harness in the pytest/testcases directory.  It will overwrite files that
# are already present in that directory, so use this with caution (and Git,
# so you know which files were changed).
#

from collections import defaultdict
import xml.etree.ElementTree as ET
import sys
import os
import re


def convert_camel_to_snake(camel: str) -> str:
    snake: str = camel

    # TLASomeWordL -> TLA_SomeWordL
    snake = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', snake)
    # TLA_SomeWordL -> TLASome_Word_L
    snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', snake)

    snake = snake.lower()

    return snake


def convert_test_name(name: str) -> str:
    return name.strip().lower().replace('-', '_')


def find_test_case_xml_dirs() -> str:
    def recurse(d):
        if os.path.realpath(d) == '/':
            return None

        test_case_dir: str = os.path.join(d, 'XML', 'TestCases')
        if os.path.exists(test_case_dir):
            return test_case_dir

        return recurse(os.path.join(d, '..'))

    return os.path.realpath(recurse('.'))


def convert_node_to_dict(root_node):
    def traverse(node, output):
        if node is None:
            return output

        if not node:
            output[node.tag] = node.text
            return output

        output[node.tag] = {}

        for child in node:
            children_dict = traverse(child, {})

            if child.tag not in output[node.tag]:
                output[node.tag].update(children_dict)
                continue

            if not isinstance(output[node.tag][child.tag], list):
                output[node.tag][child.tag] = [output[node.tag][child.tag]]
            output[node.tag][child.tag].append(children_dict[child.tag])

        return output

    return traverse(root_node, {})


def snakeify_dict_keys(input):
    output = {}

    for key, value in input.items():
        key = convert_camel_to_snake(key)

        if isinstance(value, dict):
            value = snakeify_dict_keys(value)

        output[key] = value

    return output


def attrib_is_list(attrib: str) -> bool:
    return attrib.endswith('s') or attrib in {'platform'}


def compute_decorators(case):
    output = defaultdict(lambda: {})

    for key, value in case.items():
        try:
            value = int(value)
        except (TypeError, ValueError):
            if ',' in value and attrib_is_list(key):
                value = value.split(',')

        if key in {'platform', 'category', 'area', 'tags', 'priority'}:
            output['lisa'][key] = value
            continue

        if key == 'setup_config':
            deploy = {}
            for key, value in value.items():
                if key == 'setup_type':
                    deploy['setup'] = value
                elif key == 'override_vm_size':
                    deploy['vm_size'] = value
                elif key in {'setup_script'}:
                    continue
                else:
                    deploy[key] = value
            output['deploy'] = deploy
            continue

    output['skip']['reason'] = 'Test stub not implemented'

    return output


def compute_files_to_copy(case):
    files = case.get('files', '')

    if isinstance(files, str):
        files = files.strip()
        return files.split(',') if files else []

    if isinstance(files, list):
        return files

    assert RuntimeError("not reached")


def ensure_value_is_list(attrib: str, value: str):
    if attrib_is_list(attrib):
        if not isinstance(value, list):
            return [value]

    return value


def convert_case(xml_name: str) -> str:
    root = ET.parse(xml_name).getroot()

    if root.tag != 'TestCases':
        raise RuntimeError(f"File {xml_name} is not a test case definition XML!")

    simple_xml_name = xml_name.split('/')[-1]
    output = [
        f'"""Runs \'{simple_xml_name}\' using Pytest."""',
        'import conftest',
        'import pytest',
        'from node_plugin import None',
        '',
        '',
    ]
    for case in root:
        if case.tag != 'test':
            raise RuntimeError(f"Test case node is invalid: invalid XML tag <{case.tag}> found")

        case_dict = convert_node_to_dict(case)['test']
        case_dict = snakeify_dict_keys(case_dict)

        for mark, attribs in compute_decorators(case_dict).items():
            output.append(f'@pytest.mark.{mark}(')
            for attrib, value in attribs.items():
                value = ensure_value_is_list(attrib, value)

                if isinstance(value, str):
                    output.append(f'    {attrib}=\'{value}\',')
                else:
                    output.append(f'    {attrib}={value},')
            output.append(')')

        test_name = convert_test_name(case_dict['test_name'])
        output.append(f'def test_{test_name}(node: Node) -> None:')
        files_to_copy = compute_files_to_copy(case_dict)
        if files_to_copy:
            output.append('    for f in [')
            for file_to_copy in files_to_copy:
                file_to_copy = file_to_copy.split('\\')[-1]
                output.append(f'        "{file_to_copy}",')
            output.append('    ]:')
            output.append('        node.put(conftest.LINUX_SCRIPTS / f)')
            output.append('        node.run(f"chmod +x {f}")')

        output.append('    assert node.cat("state.txt") == "TestCompleted"')

        output.append('')
        output.append('')

    return '\n'.join(output)


def get_stub_dir_from_test_case_dir(test_cases_dir: str) -> str:
    return os.path.realpath(os.path.join(test_cases_dir, '..', '..', 'pytest', 'testsuites'))


def get_harness_name(stub_dir: str, file_name: str) -> str:
    file_name = file_name.replace('.xml', '')

    if '-' in file_name:
        first, second = file_name.split('-')
        first = first.replace('Tests', '')
        second = convert_camel_to_snake(second)
        file_name = f'{first}_{second}'
    else:
        file_name = convert_camel_to_snake(file_name)

    file_name = file_name.lower()
    return os.path.join(stub_dir, f'test_{file_name}.py')


if __name__ == '__main__':
    test_cases_dir: str = find_test_case_xml_dirs()

    if not test_cases_dir:
        print("Could not find XML test cases directory. Are you running this inside a LISA checkout?")
        sys.exit(1)

    stub_dir: str = get_stub_dir_from_test_case_dir(test_cases_dir)

    print(f"Importing XML test case definitions from directory {test_cases_dir}")
    print(f"Saving stub harnesses to {stub_dir}")

    for dir_path, dir_names, file_names in os.walk(test_cases_dir):
        for file_name in file_names:
            as_python: str = convert_case(os.path.join(dir_path, file_name))
            harness_name: str = get_harness_name(stub_dir, file_name)
            with open(harness_name, 'w') as f:
                print(f"Generated stub: {harness_name}")
                f.write(as_python)
