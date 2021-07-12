#!/bin/bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache License.
#
# Run fio against Azure NFS share.
# In this script, we want to bench-mark device IO performance on a mounted folder.

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

RunFIO() {
	UpdateTestState $ICA_TESTRUNNING
	FILEIO="--size=${fileSize} --direct=1 --ioengine=libaio --filename=fiodata --overwrite=1"

	HOMEDIR=$HOME
	mv $HOMEDIR/FIOLog/ $HOMEDIR/FIOLog-$(date +"%m%d%Y-%H%M%S")/
	LOGDIR="${HOMEDIR}/FIOLog"
	JSONFILELOG="${LOGDIR}/jsonLog"
	IOSTATLOGDIR="${LOGDIR}/iostatLog"
	LOGFILE="${LOGDIR}/fio-test.log.txt"

	mkdir $HOMEDIR/FIOLog
	mkdir $HOMEDIR/FIOLog/jsonLog
	mkdir $HOMEDIR/FIOLog/iostatLog
	mkdir $HOMEDIR/FIOLog/blktraceLog


	io_increment=128
	echo "Test log created at: ${LOGFILE}"
	echo "===================================== Starting Run $(date +"%x %r %Z") ================================" >> $LOGFILE

	chmod 666 $LOGFILE
	echo "Preparing Files: $FILEIO"
	echo "Preparing Files: $FILEIO" >> $LOGFILE
	LogMsg "Preparing Files: $FILEIO"
	rm fiodata
	echo "--- Kernel Version Information ---" >> $LOGFILE
	uname -a >> $LOGFILE
	cat /proc/version >> $LOGFILE
	cat /etc/*-release >> $LOGFILE
	echo "--- PCI Bus Information ---" >> $LOGFILE
	lspci >> $LOGFILE
	echo "--- Drive Mounting Information ---" >> $LOGFILE
	mount >> $LOGFILE
	echo "--- Disk Usage Before Generating New Files ---" >> $LOGFILE
	df -h >> $LOGFILE
	fio --cpuclock-test >> $LOGFILE
	fio $FILEIO --readwrite=read --bs=1M --runtime=1 --iodepth=128 --numjobs=8 --name=prepare
	echo "--- Disk Usage After Generating New Files ---" >> $LOGFILE
	df -h >> $LOGFILE
	echo "=== End Preparation  $(date +"%x %r %Z") ===" >> $LOGFILE
	LogMsg "Preparing Files: $FILEIO: Finished."
	for testmode in "${modes[@]}"; do
		io=$startIO
		while [ $io -le $maxIO ]; do
			Thread=$startThread
			while [ $Thread -le $maxThread ]; do
				if [ $Thread -ge 8 ]; then
					numjobs=8
				else
					numjobs=$Thread
				fi
				iostatfilename="${IOSTATLOGDIR}/iostat-fio-${testmode}-${io}K-${Thread}td.txt"
				nohup iostat -x 5 -t -y > $iostatfilename &
				echo "-- iteration ${iteration} ----------------------------- ${testmode} test, ${io}K bs, ${Thread} threads, ${numjobs} jobs, 5 minutes ------------------ $(date +"%x %r %Z") ---" >> $LOGFILE
				LogMsg "Running ${testmode} test, ${io}K bs, ${Thread} threads ..."
				jsonfilename="${JSONFILELOG}/fio-result-${testmode}-${io}K-${Thread}td.json"
				fio $FILEIO --readwrite=$testmode --bs=${io}K --runtime=$ioruntime --iodepth=$Thread --numjobs=$numjobs --output-format=json --output=$jsonfilename --name="iteration"${iteration} >> $LOGFILE
				iostatPID=$(ps -ef | awk '/iostat/ && !/awk/ { print $2 }')
				kill -9 $iostatPID
				Thread=$(( Thread*2 ))
				iteration=$(( iteration+1 ))
			done
			io=$(( io * io_increment ))
		done
	done
	####################################
	echo "===================================== Completed Run $(date +"%x %r %Z") script generated 2/9/2015 4:24:44 PM ================================" >> $LOGFILE
	rm fiodata

	compressedFileName="${HOMEDIR}/FIOTest-$(date +"%m%d%Y-%H%M%S").tar.gz"
	LogMsg "INFO: Please wait...Compressing all results to ${compressedFileName}..."
	tar -cvzf $compressedFileName $LOGDIR/

	echo "Test logs are located at ${LOGDIR}"
	UpdateTestState $ICA_TESTCOMPLETED
}

############################################################
#	Main body
############################################################

install_nfs_package
check_exit_status "install nfs package." exit
mkdir -p /mount/nfsshare
LogMsg "Make folder /mount/nfsshare."
mount -t nfs $nfsshare /mount/nfsshare -o rw,vers=$nfsversion,sec=sys,nconnect=$nconnect
LogMsg "Run mount -t nfs $nfsshare /mount/nfsshare -o rw,vers=$nfsversion,sec=sys,nconnect=$nconnect"
check_exit_status "Execute mount -t nfs $nfsshare /mount/nfsshare -o rw,vers=$nfsversion,sec=sys,nconnect=$nconnect" exit
pushd /mount/nfsshare
install_fio
RunFIO
popd