#!/bin/bash
#######################################################################
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache License.
#
# nfs_share.sh
# Description:
#    to do
# Supported Distros:
#    to do
#######################################################################
CONSTANTS_FILE="./constants.sh"
. ${CONSTANTS_FILE} || {
	echo "ERROR: unable to source constants.sh!"
	echo "TestAborted" > state.txt
	exit 1
}
UTIL_FILE="./utils.sh"
. ${UTIL_FILE} || {
	echo "ERROR: unable to source utils.sh!"
	echo "TestAborted" > state.txt
	exit 2
}
# Source constants file and initialize most common variables
UtilsInit
install_nfs_package
check_exit_status "install nfs package." exit
mkdir -p /mount/nfsshare
LogMsg "Make folder /mount/nfsshare."
mount -t nfs $nfsshare /mount/nfsshare -o rw,vers=$nfsversion,sec=sys,nconnect=$nconnect
LogMsg "Run mount -t nfs $nfsshare /mount/nfsshare -o rw,vers=$nfsversion,sec=sys,nconnect=$nconnect"
check_exit_status "Execute mount -t nfs $nfsshare /mount/nfsshare -o rw,vers=$nfsversion,sec=sys,nconnect=$nconnect" exit
pushd /mount/nfsshare
wget $tarfile
file_name=$(echo ${tarfile##*/})
find_result=$(find . -name $file_name)
if [ -z "$find_result" ]; then
      LogErr "Not find tar file $file_name."
      SetTestStateFailed
      exit 0
else
      LogMsg "Find the file $file_name."
fi
tar -xvf $file_name
check_exit_status "Execute tar -xvf $file_name" exit
popd
umount /mount/nfsshare
check_exit_status "umount /mount/nfsshare" exit
SetTestStateCompleted
