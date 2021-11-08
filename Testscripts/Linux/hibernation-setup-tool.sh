#!/bin/bash
#
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache License.
# This script will set up hibernation configuration in the VM.
########################################################################################################
# Source utils.sh
. utils.sh || {
	echo "Error: unable to source utils.sh!"
	echo "TestAborted" > state.txt
	exit 0
}
# Source constants file and initialize most common variables
UtilsInit

install_package "git make gcc"
git clone https://github.com/microsoft/hibernation-setup-tool
pushd hibernation-setup-tool
make; make install
if [[ $? -ne 0 ]]; then
	SetTestStateFailed
	exit 0
fi
systemctl start hibernation-setup-tool
wait_for_server=120
while [ $wait_for_server -gt 0 ]; do
	journalctl -u hibernation-setup-tool -b | grep -i "Swap file for VM hibernation set up successfully"
	if [[ $? -eq 0 ]]; then
		break
	fi
	sleep 5
	wait_for_server=$(($wait_for_server - 5))
done
journalctl -u hibernation-setup-tool -b | grep -i "Swap file for VM hibernation set up successfully"
if [[ $? -ne 0 ]]; then
	SetTestStateFailed
	exit 0
fi
SetTestStateCompleted
exit 0
