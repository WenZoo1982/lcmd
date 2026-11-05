
#requires -Version 5.1

<#
.SYNOPSIS
    LCMD Windows 安装环境与路径只读识别。

.DESCRIPTION
    本脚本当前仅执行只读检查：
    - 检查发行包结构
    - 识别固定主程序安装目录
    - 验证安装身份标记
    - 识别配置文件及知识库路径
    - 验证候选知识库目录

    不执行安装、升级、复制、删除、配置写入或注册表写入。
#>

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:ProductId = "WenZoo.LCMD"
$script:MarkerVersion = 1
$script:RegistryPath = "HKCU:\Software\WenZoo\LCMD"

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title
    )

    Write-Host ""
    Write-Host "========== $Title =========="
}

function ConvertTo-NormalizedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "路径为空。"
    }

    if (-not [System.IO.Path]::IsPathRooted($Path)) {
        throw "路径不是绝对路径：$Path"
    }

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($fullPath)

    if ($fullPath.Length -gt $root.Length) {
        $fullPath = $fullPath.TrimEnd([char[]]@(92, 47))
    }

    return $fullPath
}

function Test-DirectoryEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $firstItem = Get-ChildItem `
        -LiteralPath $Path `
        -Force `
        -ErrorAction Stop |
        Select-Object -First 1

    return ($null -eq $firstItem)
}

function Test-KnowledgeDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    try {
        $normalizedPath = ConvertTo-NormalizedPath -Path $Path
    }
    catch {
        return [pscustomobject]@{
            State = "INVALID_PATH"
            Path = $Path
            Reason = $_.Exception.Message
        }
    }

    try {
        if (-not (Test-Path -LiteralPath $normalizedPath -ErrorAction Stop)) {
            return [pscustomobject]@{
                State = "NOT_EXISTS"
                Path = $normalizedPath
                Reason = "目录不存在。"
            }
        }

        if (-not (Test-Path -LiteralPath $normalizedPath -PathType Container -ErrorAction Stop)) {
            return [pscustomobject]@{
                State = "NOT_DIRECTORY"
                Path = $normalizedPath
                Reason = "指定路径不是目录。"
            }
        }

        if (Test-DirectoryEmpty -Path $normalizedPath) {
            return [pscustomobject]@{
                State = "EMPTY_DIRECTORY"
                Path = $normalizedPath
                Reason = "目录存在，但没有任何内容。"
            }
        }
    }
    catch {
        return [pscustomobject]@{
            State = "INACCESSIBLE"
            Path = $normalizedPath
            Reason = $_.Exception.Message
        }
    }

    $null = & $script:Exe "--internal-validate-knowledge" $normalizedPath
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        return [pscustomobject]@{
            State = "VALID_KNOWLEDGE"
            Path = $normalizedPath
            Reason = "知识库结构验证通过。"
        }
    }

    return [pscustomobject]@{
        State = "INVALID_NONEMPTY_DIRECTORY"
        Path = $normalizedPath
        Reason = "目录非空，但不是有效的 LCMD 知识库。"
    }
}

function Test-InstallMarker {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InstallDirectory
    )

    $markerFile = Join-Path $InstallDirectory ".lcmd-install.json"

    if (-not (Test-Path -LiteralPath $markerFile -PathType Leaf)) {
        throw "安装身份标记不存在：$markerFile"
    }

    try {
        $markerText = Get-Content `
            -LiteralPath $markerFile `
            -Raw `
            -Encoding UTF8

        $marker = $markerText | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "安装身份标记无法读取或 JSON 格式无效：$($_.Exception.Message)"
    }

    if ($null -eq $marker -or $marker -is [array]) {
        throw "安装身份标记的数据结构无效。"
    }

    $requiredFields = @(
        "product",
        "marker_version",
        "main_version",
        "install_dir"
    )

    $actualFields = @(
        $marker.PSObject.Properties |
            ForEach-Object { $_.Name }
    )

    if ($actualFields.Count -ne $requiredFields.Count) {
        throw "安装身份标记字段数量不正确。"
    }

    foreach ($field in $requiredFields) {
        if ($actualFields -cnotcontains $field) {
            throw "安装身份标记缺少字段或字段名称不正确：$field"
        }
    }

    if ($marker.product -isnot [string]) {
        throw "安装身份标记 product 字段类型无效。"
    }

    if ($marker.product -cne $script:ProductId) {
        throw "产品标识不匹配：$($marker.product)"
    }

    if ($marker.marker_version -isnot [int]) {
        throw "marker_version 必须是整数。"
    }

    if ($marker.marker_version -ne $script:MarkerVersion) {
        throw "不支持的安装标记格式版本：$($marker.marker_version)"
    }

    if ($marker.main_version -isnot [string]) {
        throw "main_version 字段类型无效。"
    }

    if ($marker.main_version -notmatch '^\d+\.\d+\.\d+$') {
        throw "主程序版本号格式无效：$($marker.main_version)"
    }

    if ($marker.install_dir -isnot [string]) {
        throw "install_dir 字段类型无效。"
    }

    try {
        $recordedDirectory = ConvertTo-NormalizedPath -Path $marker.install_dir
        $expectedDirectory = ConvertTo-NormalizedPath -Path $InstallDirectory
    }
    catch {
        throw "安装目录身份验证失败：$($_.Exception.Message)"
    }

    if ($recordedDirectory -ine $expectedDirectory) {
        throw "安装身份标记记录的目录与固定安装目录不一致。"
    }

    return $marker
}

function Get-InstallDirectoryState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InstallDirectory
    )

    if (-not (Test-Path -LiteralPath $InstallDirectory)) {
        return [pscustomobject]@{
            State = "NOT_EXISTS"
            MainVersion = $null
            Reason = "固定安装目录不存在。"
        }
    }

    if (-not (Test-Path -LiteralPath $InstallDirectory -PathType Container)) {
        return [pscustomobject]@{
            State = "UNKNOWN_INVALID"
            MainVersion = $null
            Reason = "固定安装路径已存在，但不是目录。"
        }
    }

    if (Test-DirectoryEmpty -Path $InstallDirectory) {
        return [pscustomobject]@{
            State = "EMPTY_DIRECTORY"
            MainVersion = $null
            Reason = "固定安装目录存在，但为空。"
        }
    }

    try {
        $marker = Test-InstallMarker -InstallDirectory $InstallDirectory
    }
    catch {
        return [pscustomobject]@{
            State = "UNKNOWN_INVALID"
            MainVersion = $null
            Reason = $_.Exception.Message
        }
    }

    $installedExe = Join-Path $InstallDirectory "lcmd.exe"
    $internalDirectory = Join-Path $InstallDirectory "_internal"

    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) {
        return [pscustomobject]@{
            State = "UNKNOWN_INVALID"
            MainVersion = $null
            Reason = "安装目录缺少 lcmd.exe。"
        }
    }

    if (-not (Test-Path -LiteralPath $internalDirectory -PathType Container)) {
        return [pscustomobject]@{
            State = "UNKNOWN_INVALID"
            MainVersion = $null
            Reason = "安装目录缺少 _internal 目录。"
        }
    }

    if (Test-DirectoryEmpty -Path $internalDirectory) {
        return [pscustomobject]@{
            State = "UNKNOWN_INVALID"
            MainVersion = $null
            Reason = "_internal 目录为空。"
        }
    }

    return [pscustomobject]@{
        State = "VALID_LCMD_INSTALL"
        MainVersion = $marker.main_version
        Reason = "安装标记和 onedir 关键文件均验证通过。"
    }
}

function Get-RegistryKnowledgePath {
    if (-not (Test-Path -LiteralPath $script:RegistryPath)) {
        return $null
    }

    try {
        $registryItem = Get-ItemProperty `
            -LiteralPath $script:RegistryPath `
            -Name "KnowledgeDir" `
            -ErrorAction Stop

        $value = $registryItem.KnowledgeDir

        if ($value -isnot [string]) {
            return $null
        }

        if ([string]::IsNullOrWhiteSpace($value)) {
            return $null
        }

        return $value
    }
    catch {
        return $null
    }
}

function Get-ConfigKnowledgePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigFile
    )

    $inspectOutput = @(
        & $script:Exe "--internal-inspect-config" $ConfigFile
    )

    $inspectExitCode = $LASTEXITCODE

    if ($inspectExitCode -ne 0) {
        throw "现有配置无法读取，停止识别。"
    }

    $jsonText = ($inspectOutput -join [Environment]::NewLine).Trim()

    try {
        $result = $jsonText | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "配置检查接口没有返回有效 JSON。"
    }

    if ($null -eq $result -or $result.status -cne "OK") {
        throw "配置检查接口返回状态异常。"
    }

    if ($result.knowledge_path -isnot [string]) {
        throw "配置中的知识库路径无效。"
    }

    if ([string]::IsNullOrWhiteSpace($result.knowledge_path)) {
        throw "配置中的知识库路径为空。"
    }

    $null = & $script:Exe "--internal-validate-config" $ConfigFile
    $validateExitCode = $LASTEXITCODE

    if ($validateExitCode -ne 0) {
        throw "现有配置或其知识库验证失败，停止识别，不回退注册表或默认路径。"
    }

    return ConvertTo-NormalizedPath -Path $result.knowledge_path
}

function Select-FirstInstallKnowledgePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DefaultKnowledgePath
    )

    Write-Section "检查注册表辅助路径"

    $registryKnowledgePath = Get-RegistryKnowledgePath

    if ($null -ne $registryKnowledgePath) {
        Write-Host "注册表记录路径：$registryKnowledgePath"

        $registryState = Test-KnowledgeDirectory -Path $registryKnowledgePath

        Write-Host "注册表路径状态：$($registryState.State)"

        if ($registryState.State -eq "VALID_KNOWLEDGE") {
            return [pscustomobject]@{
                Path = $registryState.Path
                Source = "REGISTRY"
                State = $registryState.State
                Reason = $registryState.Reason
            }
        }

        Write-Warning "注册表路径不是有效 LCMD 知识库，将继续检查默认目录。"
    }
    else {
        Write-Host "没有可用的注册表知识库路径记录。"
    }

    Write-Section "检查默认知识库路径"

    $defaultState = Test-KnowledgeDirectory -Path $DefaultKnowledgePath

    Write-Host "默认知识库路径：$($defaultState.Path)"
    Write-Host "默认路径状态：$($defaultState.State)"

    switch ($defaultState.State) {
        "NOT_EXISTS" {
            return [pscustomobject]@{
                Path = $defaultState.Path
                Source = "DEFAULT"
                State = $defaultState.State
                Reason = $defaultState.Reason
            }
        }

        "EMPTY_DIRECTORY" {
            return [pscustomobject]@{
                Path = $defaultState.Path
                Source = "DEFAULT"
                State = $defaultState.State
                Reason = $defaultState.Reason
            }
        }

        "VALID_KNOWLEDGE" {
            return [pscustomobject]@{
                Path = $defaultState.Path
                Source = "DEFAULT"
                State = $defaultState.State
                Reason = $defaultState.Reason
            }
        }

        default {
            throw "默认知识库目录存在异常，停止识别以保护现有内容：$($defaultState.Reason)"
        }
    }
}

try {
    Write-Section "检查发行包"

    $script:PackageRoot = ConvertTo-NormalizedPath -Path $PSScriptRoot

    $script:Exe = Join-Path $script:PackageRoot "app\lcmd.exe"
    $packageInternal = Join-Path $script:PackageRoot "app\_internal"
    $packageKnowledge = Join-Path $script:PackageRoot "knowledge"
    $packageIntegrity = Join-Path $script:PackageRoot "knowledge-integrity.json"

    if (-not (Test-Path -LiteralPath $script:Exe -PathType Leaf)) {
        throw "发行包缺少 app\lcmd.exe。"
    }

    if (-not (Test-Path -LiteralPath $packageInternal -PathType Container)) {
        throw "发行包缺少 app\_internal 目录。"
    }

    if (Test-DirectoryEmpty -Path $packageInternal) {
        throw "发行包 app\_internal 目录为空。"
    }

    if (-not (Test-Path -LiteralPath $packageKnowledge -PathType Container)) {
        throw "发行包缺少 knowledge 目录。"
    }

    if (-not (Test-Path -LiteralPath $packageIntegrity -PathType Leaf)) {
        throw "发行包缺少 knowledge-integrity.json。"
    }

    $null = & $script:Exe "--internal-validate-knowledge" $packageKnowledge
    $packageKnowledgeExit = $LASTEXITCODE

    if ($packageKnowledgeExit -ne 0) {
        throw "发行包自带知识库验证失败。"
    }

    Write-Host "发行包根目录：$script:PackageRoot"
    Write-Host "发行包结构：有效"
    Write-Host "发行包知识库：验证通过"

    Write-Section "识别固定安装目录"

    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "无法取得 LOCALAPPDATA 环境变量。"
    }

    $programsDirectory = Join-Path $env:LOCALAPPDATA "Programs"
    $installDirectory = Join-Path $programsDirectory "LCMD"

    $installState = Get-InstallDirectoryState -InstallDirectory $installDirectory

    Write-Host "固定安装目录：$installDirectory"
    Write-Host "安装目录状态：$($installState.State)"
    Write-Host "识别说明：$($installState.Reason)"

    if ($installState.State -eq "UNKNOWN_INVALID") {
        throw "固定安装目录包含未知或无效内容。为防止覆盖其他文件，停止操作。"
    }

    if ($installState.State -eq "VALID_LCMD_INSTALL") {
        Write-Host "已安装主程序版本：$($installState.MainVersion)"
    }

    Write-Section "识别配置文件"

    $configDirectory = Join-Path $env:LOCALAPPDATA "lcmd"
    $configFile = Join-Path $configDirectory "config.toml"
    $defaultKnowledgePath = Join-Path $configDirectory "knowledge"

    Write-Host "配置文件路径：$configFile"

    if (Test-Path -LiteralPath $configFile) {
        if (-not (Test-Path -LiteralPath $configFile -PathType Leaf)) {
            throw "配置文件路径存在，但不是普通文件。"
        }

        Write-Host "配置文件状态：EXISTS"

        $selectedKnowledgePath = Get-ConfigKnowledgePath -ConfigFile $configFile

        $knowledgeSelection = [pscustomobject]@{
            Path = $selectedKnowledgePath
            Source = "CONFIG"
            State = "VALID_KNOWLEDGE"
            Reason = "现有配置及其知识库验证通过。"
        }
    }
    else {
        Write-Host "配置文件状态：NOT_EXISTS"

        $knowledgeSelection = Select-FirstInstallKnowledgePath `
            -DefaultKnowledgePath $defaultKnowledgePath
    }

    Write-Section "识别结果"

    Write-Host "INSTALL_DIR_STATE=$($installState.State)"
    Write-Host "INSTALL_DIR=$installDirectory"

    if ($null -ne $installState.MainVersion) {
        Write-Host "INSTALLED_MAIN_VERSION=$($installState.MainVersion)"
    }

    Write-Host "CONFIG_FILE=$configFile"
    Write-Host "KNOWLEDGE_PATH_SOURCE=$($knowledgeSelection.Source)"
    Write-Host "KNOWLEDGE_PATH_STATE=$($knowledgeSelection.State)"
    Write-Host "KNOWLEDGE_PATH=$($knowledgeSelection.Path)"
    Write-Host "KNOWLEDGE_REASON=$($knowledgeSelection.Reason)"

    Write-Host ""
    Write-Host "INSTALL_ENVIRONMENT=PASS"
    Write-Host "MODE=READ_ONLY"
    Write-Host "本脚本没有执行安装、升级或任何用户数据修改。"

    exit 0
}
catch {
    Write-Host ""
    Write-Host "INSTALL_ENVIRONMENT=ERROR" -ForegroundColor Red
    Write-Host "停止原因：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "MODE=READ_ONLY"
    exit 1
}
