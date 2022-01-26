# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import List, Optional

from lisa import RemoteNode
from lisa.schema import Node
from lisa.tools import Qemu, Wget
from lisa.tools.df import Df, PartitionInfo
from lisa.util import SkippedException

NESTED_VM_IMAGE_NAME = "image.qcow2"
NESTED_VM_TEST_FILE_NAME = "message.txt"
NESTED_VM_TEST_FILE_CONTENT = "Message from L1 vm!!"
NESTED_VM_TEST_PUBLIC_FILE_URL = "http://www.github.com"
NESTED_VM_REQUIRED_DISK_SIZE_IN_GB = 6


def connect_nested_vm(
    host: RemoteNode,
    guest_username: str,
    guest_password: str,
    guest_port: int,
    guest_image_url: str,
    image_name: str = NESTED_VM_IMAGE_NAME,
    image_size: int = NESTED_VM_REQUIRED_DISK_SIZE_IN_GB,
    disks: Optional[List[str]] = None,
) -> RemoteNode:
    image_folder_path = get_partition_for_nested_image(host, image_size)

    host.tools[Wget].get(
        url=guest_image_url,
        file_path=image_folder_path,
        filename=image_name,
        sudo=True,
    )

    # start nested vm
    host.tools[Qemu].create_vm(guest_port, f"{image_folder_path}/{image_name}", disks)

    # setup connection to nested vm
    nested_vm = RemoteNode(Node(name="L2-vm"), 0, "L2-vm")
    nested_vm.set_connection_info(
        public_address=host.public_address,
        username=guest_username,
        password=guest_password,
        public_port=guest_port,
        port=guest_port,
    )

    return nested_vm


def get_partition_for_nested_image(node: RemoteNode, size: int) -> str:
    home_partition = node.tools[Df].get_partition_by_mountpoint("/home")
    if home_partition and check_partition_capacity(home_partition, size):
        return home_partition.mountpoint

    mnt_partition = node.tools[Df].get_partition_by_mountpoint("/mnt")
    if mnt_partition and check_partition_capacity(mnt_partition, size):
        return mnt_partition.mountpoint

    raise SkippedException(
        "No partition with Required disk space of " f"{size}GB found"
    )


def check_partition_capacity(
    partition: PartitionInfo,
    size: int,
) -> bool:
    # check if the partition has enough space to download nested image file
    unused_partition_size_in_gb = (partition.total_blocks - partition.used_blocks) / (
        1024 * 1024
    )
    if unused_partition_size_in_gb > size:
        return True

    return False
