# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache License.

param([String] $TestParams,
    [object] $AllVmData)

function Main {
    Write-LogInfo "Generating constants.sh ..."
    # 
    #Sample contents of constants.sh
    # 
    # KERNEL_GIT_URL="git://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git"
    # KERNEL_GIT_BRANCH="master"
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
    Write-LogInfo "Generating constants.sh ..."
    $constantsFile = "$LogDir\constants.sh"

    foreach ($param in $currentTestData.TestParameters.param) {
        Add-Content -Value "$param" -Path $constantsFile
    }
    Write-LogInfo "constants.sh created successfully..."

    Copy-RemoteFiles -uploadTo $allVmData.PublicIP -port $allVmData.SSHPort `
        -files "$constantsFile" -username $user -password $password -upload

    Copy-RemoteFiles -uploadTo $allVmData.PublicIP -port $allVmData.SSHPort -files $currentTestData.files -username $user -password $password -upload

    #
    # Run the guest VM side script
    #
    try {
        $testJob = Run-LinuxCmd -ip $allVMData.PublicIP -port $allVMData.SSHPort `
            -username $user -password $password -command "bash UpstreamKernelBuild.sh > UpstreamKernelBuild.log 2>&1" `
            -RunInBackground -runAsSudo

        Write-LogInfo "Monitoring test run..."
        $StuckCounter = 0
        $MaxStuckAttempts = 30
        while ((Get-Job -Id $testJob).State -eq "Running") {
            $currentStatus = Run-LinuxCmd -ip $allVMData.PublicIP -port $allVMData.SSHPort `
                -username $user -password $password -command "tail -1 UpstreamKernelBuild.log" `
                -runAsSudo -runMaxAllowedTime 6000
            Write-LogInfo "Current Test Status: $currentStatus"
            if ($currentStatus -imatch "Doing forceful exit of this job") {
                $StuckCounter++
                if ( $StuckCounter -eq $MaxStuckAttempts) {
                    throw "FIO is stuck, aborting the test"
                }
            } else {
                $StuckCounter = 0
            }

            Wait-Time -seconds 30
        }

        $status = Run-LinuxCmd -ip $allVMData.PublicIP -port $allVMData.SSHPort `
            -username $user -password $password -command "cat state.txt"
        Copy-RemoteFiles -downloadFrom $allVMData.PublicIP -port $allVMData.SSHPort `
            -username $user -password $password -download `
            -downloadTo $LogDir -files "*.txt, *.log"
        
        if ($status -imatch "TestFailed") {
            Write-LogErr "Test failed."
            $testResult = "FAIL"
        }
        elseif ($status -imatch "TestAborted") {
            Write-LogErr "Test Aborted."
            $testResult = "ABORTED"
        }
        elseif ($status -imatch "TestSkipped") {
            Write-LogErr "Test Skipped."
            $testResult = "SKIPPED"
        }
        elseif ($status -imatch "TestCompleted") {
            Write-LogInfo "Test Completed."
            $testResult = "PASS"
        }
        else {
            Write-LogErr "Test execution is not successful, check test logs in VM."
            $testResult = "ABORTED"
        }
    }
    catch {
        $ErrorMessage = $_.Exception.Message
        $ErrorLine = $_.InvocationInfo.ScriptLineNumber
        Write-LogErr "EXCEPTION : $ErrorMessage at line: $ErrorLine"
        $testResult = "FAIL"
    }
    finally {
        if (!$testResult) {
            $testResult = "ABORTED"
        }
    }
    Write-LogInfo "Test result: $testResult"
    return $testResult
}

Main