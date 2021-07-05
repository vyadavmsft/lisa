#!/bin/bash
#
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache License.
# This script builds kernel from source.
# 
########################################################################################################
# Source utils.sh
set -x #e -o pipefail
. utils.sh || {
	echo "Error: unable to source utils.sh!"
	echo "TestAborted" > state.txt
	exit 0
}
# Source constants file and initialize most common variables
UtilsInit

# Constants/Globals
# Get distro information
GetDistro

if [ $DISTRO_NAME == 'rhel' ]
then
    yum update -y --disablerepo=* --enablerepo="*microsoft*"
    yum install -y gcc-toolset-9-gcc.x86_64
    source /opt/rh/gcc-toolset-9/enable
fi

# update repos
update_repos

function Main() {
    BASEDIR=$(dirname $0)
    BASEDIR=$(readlink -f $BASEDIR)

    # 
    # Getting required parameters
    # 
    # Sample contents of constants.sh:
    # 
    # KERNEL_GIT_URL="git://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git"
    # KERNEL_GIT_BRANCH="master"
    # LIS_PIPELINE_GIT_URL="https://github.com/LIS/lis-pipeline.git"
    # LIS_PIPELINE_GIT_BRANCH="master"
    # KERNEL_ARTIFACTS_PATH='upstream-kernel-artifacts'
    # INSTALL_DEPS='True'
    # THREAD_NUMBER='x3'
    # UBUNTU_VERSION='16'
    # BUILD_PATH='/mnt/tmp/upstream-kernel-build-folder'
    # KERNEL_CONFIG='Microsoft/config-azure'
    # CLEAN_ENV='True'
    # USE_CCACHE='True'
    # USE_KERNEL_FOLDER_PREFIX='True'
    # CREATE_CHANGELOG='False'
    # KERNEL_DEBUG='False'
    # 
    if [ -f constants.sh ]
    then
        LogMsg "Sourcing constants.sh .. "
        source constants.sh
    else
		LogErr "cannot find constants.sh!"
        exit 1
    fi

    # install git if not installed already
    which git
    if [ $? -ne 0 ]
    then
        install_package git
    fi

    # cloning scripts required to build kernel package
    #
    if [ -d lis-pipeline ]
    then 
        echo rm -rf lis-pipeline
    else
        git clone --single-branch --branch ${LIS_PIPELINE_GIT_BRANCH} ${LIS_PIPELINE_GIT_URL}
    fi
    
    if [ $? != 0 ]
    then
        LogErr "Failed to clone repo: ${LIS_PIPELINE_GIT_BRANCH} branch: ${LIS_PIPELINE_GIT_URL}"
        exit 1
    else
        LogMsg "Succesfully cloned repo: ${LIS_PIPELINE_GIT_BRANCH} branch: ${LIS_PIPELINE_GIT_URL}"
    fi

    # 
    # Existance of '/etc/kernel-img.conf' file is blocking for user input during installation 
    # of 'kernel-package'
    if [ -f /etc/kernel-img.conf ]
    then 
        mv /etc/kernel-img.conf /etc/kernel-img.conf.bkp
    fi
    
    pushd $BASEDIR/lis-pipeline/
    #scripts/package_building/kernel_versions.ini
    pushd scripts/package_building
    #--destination_path "${BUILD_NUMBER}-${BRANCH_NAME}-${KERNEL_ARTIFACTS_PATH}" \


    LogMsg "Building artifacts..."
    bash build_artifacts.sh \
    --git_url "${KERNEL_GIT_URL}" \
    --git_branch "${KERNEL_GIT_BRANCH}" \
    --destination_path "${KERNEL_ARTIFACTS_PATH}" \
    --install_deps "${INSTALL_DEPS}" \
    --thread_number "${THREAD_NUMBER}" \
    --debian_os_version "${UBUNTU_VERSION}" \
    --build_path "${BUILD_PATH}" \
    --kernel_config "${KERNEL_CONFIG}" \
    --clean_env "${CLEAN_ENV}" \
    --use_ccache "${USE_CCACHE}" \
    --use_kernel_folder_prefix "${USE_KERNEL_FOLDER_PREFIX}" \
    --create_changelog "${CREATE_CHANGELOG}" \
    --enable_kernel_debug "${KERNEL_DEBUG}"

    if [ $? != 0 ]
    then
        LogErr "Failed: build_artifacts"
        exit 1
    else
        LogMsg "Succesful: build_artifacts"
    fi
    popd
 
# 
# srm@smyakam-u18:~/lis-pipeline/scripts/package_building/upstream-kernel-artifacts/linux-next-5.13.0-2a8927f-25062021/deb$ ls
# linux-next-headers-5.13.0-rc7-2a8927f0efb6_25062021_amd64.deb
# linux-next-hyperv-daemons_5.13.0-rc7_amd64.deb
# linux-next-hyperv-tools_5.13.0_all.deb
# linux-next-image-5.13.0-rc7-2a8927f0efb6-dbg_25062021_amd64.deb
# linux-next-image-5.13.0-rc7-2a8927f0efb6_25062021_amd64.deb
# linux-next-perf_5.13.0.deb
# linux-next-source-5.13.0-rc7-2a8927f0efb6_25062021_all.deb
# meta_packages
# srm@smyakam-u18:~/lis-pipeline/scripts/package_building/upstream-kernel-artifacts/linux-next-5.13.0-2a8927f-25062021/deb$

	LogMsg "Main function of setup completed"
}

Main
SetTestStateCompleted
exit 0
