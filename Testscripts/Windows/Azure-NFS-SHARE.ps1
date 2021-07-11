# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache License.
param([String] $TestParams, [object] $AllVMData)
$ErrorActionPreference = "Stop"
function Main {
    param (
        $TestParams, $AllVMData
    )
    # Create test result
    $currentTestResult = Create-TestResultObject
    $resultArr = @()
    try {
        $testScript = "nfs_share.sh"
        $testResult = $null
        $resourceGroupName = $AllVMData.ResourceGroupName
        $storageAccountName = "lisa" + $(GetRandomCharacters -Length 15)
        $location = $AllVMData.Location
        $storageAccount = New-AzStorageAccount `
            -ResourceGroupName $resourceGroupName `
            -Name $storageAccountName `
            -SkuName Premium_LRS `
            -Location $location `
            -Kind FileStorage `
            -EnableHttpsTrafficOnly $false `
            -ErrorAction SilentlyContinue
        if (!$storageAccount) {
            $testResult = $resultFail
            throw "Fail to create storage account $storageAccountName in resouce group $resourceGroupName."
        }
        $nfsShareName = "nfsshare"
        $nfsShare = New-AzRmStorageShare -StorageAccountName $storageAccountName -ResourceGroupName $resourceGroupName -Name $nfsShareName -EnabledProtocol NFS -RootSquash NoRootSquash -QuotaGiB 1024
        if (!$nfsShare) {
            $testResult = $resultFail
            throw "Fail to create nfs share in storage account $storageAccountName of resouce group $resourceGroupName."
        }

        $updateRuleSet = Update-AzStorageAccountNetworkRuleSet -ResourceGroupName $resourceGroupName -Name $storageAccountName -DefaultAction Deny
        if (!$updateRuleSet -or $updateRuleSet.DefaultAction -ne "Deny") {
            $testResult = $resultFail
            throw "Fail to set -DefaultAction as Deny for Network Rule of storage account $storageAccountName."
        }
        $vnet = Get-AzVirtualNetwork -ResourceGroupName $resourceGroupName
        if (!$vnet) {
            $testResult = $resultFail
            throw "Fail to get Virtual Network in resouce group $resourceGroupName."
        }
        $subnet = Get-AzVirtualNetworkSubnetConfig -VirtualNetwork $vnet
        if (!$subnet) {
            $testResult = $resultFail
            throw "Fail to get subnet of Virtual Network $($vnet.Name) in resouce group $resourceGroupName."
        }
        $setVnet = Get-AzVirtualNetwork -ResourceGroupName $resourceGroupName -Name $vnet.Name | Set-AzVirtualNetworkSubnetConfig -Name $subnet[0].Name `
        -AddressPrefix $subnet[0].AddressPrefix -ServiceEndpoint "Microsoft.Storage"  -WarningAction SilentlyContinue | Set-AzVirtualNetwork
        if (!$setVnet) {
            $testResult = $resultFail
            throw "Fail to set service endpoint for Virtual Network $($vnet.Name) in resouce group $resourceGroupName."
        }
        $addNetRule = Add-AzStorageAccountNetworkRule -ResourceGroupName $resourceGroupName -Name $storageAccountName -VirtualNetworkResourceId $subnet[0].Id
        if (!$addNetRule) {
            $testResult = $resultFail
            throw "Fail to set network rule for storage account $storageAccountName."
        }
        # $storageAccount.PrimaryEndPoints.File.Split("/")[-2] => storageaccountname.file.core.windows.net
        # storageaccountname.file.core.windows.net:/storageaccountname/sharename
        $share = $storageAccount.PrimaryEndPoints.File.Split("/")[-2] + ":/$storageAccountName/$nfsShareName"
        $cmdAddConstants = "echo -e `"nfsshare=$($share)`" >> constants.sh"
        Run-LinuxCmd -username $user -password $password -ip $allVMData.PublicIP -port $allVMData.SSHPort -command $cmdAddConstants | Out-Null

        Run-LinuxCmd -ip $allVMData.PublicIP -port $allVMData.SSHPort -username $user `
            -password $password -command "bash $testScript" -RunAsSudo -ignoreLinuxExitCode | Out-Null
        $state = Run-LinuxCmd -ip $allVMData.PublicIP -port $allVMData.SSHPort -username $user `
            -password $password -command "cat state.txt" -RunAsSudo -ignoreLinuxExitCode
        if ($state -notMatch "Completed") {
            Write-LogErr "$testScript failed on guest"
            $testResult = $resultFail
        } else {
            $testResult = $resultPass
        }
    } catch {
        $ErrorMessage = $_.Exception.Message
        $ErrorLine = $_.InvocationInfo.ScriptLineNumber
        Write-LogErr "$ErrorMessage at line: $ErrorLine"
    } finally {
        if (!$testResult) {
            $testResult = $resultAborted
        }
        $resultArr += $testResult
    }
    $currentTestResult.TestResult = Get-FinalResultHeader -resultarr $resultArr
    return $currentTestResult.TestResult
}
Main -TestParams (ConvertFrom-StringData $TestParams.Replace(";","`n")) -AllVMData $AllVMData
