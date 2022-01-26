# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Any, Dict

from assertpy import assert_that

from lisa import RemoteNode, TestCaseMetadata, TestSuite, TestSuiteMetadata
from lisa.operating_system import Debian, Fedora, Suse
from lisa.tools import Cat, Echo, Lscpu, Sshpass, Wget
from lisa.util import SkippedException
from microsoft.testsuites.nested.common import (
    NESTED_VM_TEST_FILE_CONTENT,
    NESTED_VM_TEST_FILE_NAME,
    NESTED_VM_TEST_PUBLIC_FILE_URL,
    connect_nested_vm,
)


@TestSuiteMetadata(
    area="nested",
    category="functional",
    description="""
    This test suite is used to run nested vm related tests.
    """,
)
class Nested(TestSuite):
    @TestCaseMetadata(
        description="""
        This test case will run basic tests on provisioned L2 vm.
        Steps:
        1. Create L2 VM with Qemu.
        2. Verify that files can be copied from L1 VM to L2 VM.
        3. Verify that files from internet can be downloaded to L2 VM.
        """,
        priority=1,
    )
    def verify_nested_kvm_basic(
        self, node: RemoteNode, variables: Dict[str, Any]
    ) -> None:
        # verify that virtualization is enabled in hardware
        is_virtualization_enabled = node.tools[Lscpu].is_virtualization_enabled()
        if not is_virtualization_enabled:
            raise SkippedException("Virtualization is not enabled in hardware")

        # verify os compatibility
        if not (
            isinstance(node.os, Debian)
            or isinstance(node.os, Fedora)
            or isinstance(node.os, Suse)
        ):
            raise SkippedException(
                f"{node.os} is not supported. Currently the test could be "
                "run on Debian, Fedora and Suse distros."
            )

        # fetch nested vm test variables
        nested_image_username = variables.get("nested_image_username", "")
        nested_image_password = variables.get("nested_image_password", "")
        nested_image_port = 60024
        nested_image_url = variables.get("nested_image_url", "")

        if not nested_image_username:
            raise SkippedException("Nested image username should not be empty")

        if not nested_image_password:
            raise SkippedException("Nested image password should not be empty")

        if not nested_image_url:
            raise SkippedException("Nested image url should not be empty")

        # get l2 vm
        l2_vm = connect_nested_vm(
            node,
            nested_image_username,
            nested_image_password,
            nested_image_port,
            nested_image_url,
        )

        # verify file is correctly copied from L1 VM to L2 VM
        node.tools[Echo].write_to_file(
            NESTED_VM_TEST_FILE_CONTENT,
            node.get_pure_path(NESTED_VM_TEST_FILE_NAME),
        )
        node.tools[Sshpass].copy(
            NESTED_VM_TEST_FILE_NAME,
            NESTED_VM_TEST_FILE_NAME,
            node.public_address,
            nested_image_username,
            nested_image_password,
            nested_image_port,
        )

        uploaded_message = l2_vm.tools[Cat].read(NESTED_VM_TEST_FILE_NAME)
        assert_that(
            uploaded_message,
            "Content of the file uploaded to L2 vm from L1 should match",
        ).is_equal_to(NESTED_VM_TEST_FILE_CONTENT)

        # verify that files could be downloaded from internet on L2 VM
        l2_vm.tools[Wget].get(NESTED_VM_TEST_PUBLIC_FILE_URL)
