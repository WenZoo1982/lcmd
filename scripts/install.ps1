
#requires -Version 5.1

<#
.SYNOPSIS
    LCMD Windows 首次安装程序。

.DESCRIPTION
    - 固定安装主程序到 %LOCALAPPDATA%\Programs\LCMD
    - 自动选择知识库路径，不提供自定义路径
    - 验证发行包知识库文件清单及 SHA-256
    - 保留已有有效知识库
    - 初始化配置并保留已有有效配置中的 platform/language
    - 写入安装身份标记及注册表辅助路径
    - 配置当前用户 PATH
    - 不执行升级、卸载、回滚或完整中断恢复
#>

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:ProductId = "WenZoo.LCMD"
$script:MarkerVersion = 1


$script:PackageRoot = $null
$script:Exe = $null
$script:PackageKnowledge = $null
$script:PackageIntegrity = $null
$script:MainVersion = $null
$script:DetectedLanguage = $null

$script:InstallDirectory = $null
$script:ConfigDirectory = $null
$script:ConfigFile = $null
$script:KnowledgePath = $null
$script:KnowledgeSource = $null

$script:AppStageDirectory = $null
$script:KnowledgeStageDirectory = $null

$script:CompletedStages = @()
$script:ExitCode = 0

function Write-Section {
    param([string]$Title)

    Write-Host ""
    Write-Host "========== $Title ==========" -ForegroundColor Cyan
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

function Test-JsonInteger {
    param([object]$Value)

    return (
        $Value -is [byte] -or
        $Value -is [sbyte] -or
        $Value -is [int16] -or
        $Value -is [uint16] -or
        $Value -is [int32] -or
        $Value -is [uint32] -or
        $Value -is [int64] -or
        $Value -is [uint64]
    )
}

function Test-DirectoryEmpty {
    param([string]$Path)

    $firstItem = Get-ChildItem -LiteralPath $Path -Force -ErrorAction Stop |
        Select-Object -First 1

    return ($null -eq $firstItem)
}

function Test-PathReparsePoints {
    param([string]$Path)

    $rootItem = Get-Item -LiteralPath $Path -Force -ErrorAction Stop

    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        return $true
    }

    $children = @(
        Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction Stop
    )

    foreach ($item in $children) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            return $true
        }
    }

    return $false
}

function Invoke-InstallStage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [int]$MinimumMilliseconds,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Section $Name

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    # 操作失败时立即抛出异常，不等待阶段最短显示时间。
    $result = & $Action

    $stopwatch.Stop()

    $remaining = $MinimumMilliseconds - [int]$stopwatch.ElapsedMilliseconds

    if ($remaining -gt 0) {
        Start-Sleep -Milliseconds $remaining
    }

    Write-Host "阶段完成：$Name" -ForegroundColor Green
    $script:CompletedStages += $Name

    return $result
}

function Get-ExecutableVersion {
    param([string]$Executable)

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "主程序文件不存在：$Executable"
    }

    $output = @(& $Executable "--version" 2>&1)
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "无法读取主程序版本。程序输出：$($output -join ' ')"
    }

    $versionText = ($output -join [Environment]::NewLine).Trim()

    # 只提取 LCMD 主程序版本，不匹配知识库版本。
    # 同时兼容中文全角冒号和英文半角冒号。
    $matches = [regex]::Matches(
        $versionText,
        '(?im)^\s*LCMD\s*[:：]\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$'
    )

    if ($matches.Count -ne 1) {
        throw "无法唯一识别 LCMD 主程序版本：$versionText"
    }

    return $matches[0].Groups[1].Value
}

function Test-InstallMarker {
    param([string]$InstallDirectory)

    $markerFile = Join-Path $InstallDirectory ".lcmd-install.json"

    if (-not (Test-Path -LiteralPath $markerFile -PathType Leaf)) {
        throw "安装身份标记不存在。"
    }

    $markerItem = Get-Item -LiteralPath $markerFile -Force

    if (($markerItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "安装身份标记不能是重解析点。"
    }

    try {
        $marker = Get-Content -LiteralPath $markerFile -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "安装身份标记无法读取：$($_.Exception.Message)"
    }

    if ($null -eq $marker -or $marker -is [array]) {
        throw "安装身份标记结构无效。"
    }

    $requiredFields = @(
        "product",
        "marker_version",
        "main_version",
        "install_dir"
    )

    $actualFields = @(
        $marker.PSObject.Properties | ForEach-Object { $_.Name }
    )

    if ($actualFields.Count -ne 4) {
        throw "安装身份标记字段数量不正确。"
    }

    foreach ($field in $requiredFields) {
        if ($actualFields -cnotcontains $field) {
            throw "安装身份标记缺少字段：$field"
        }
    }

    if ($marker.product -isnot [string] -or
        $marker.product -cne $script:ProductId) {
        throw "安装身份标记产品标识不匹配。"
    }

    if (-not (Test-JsonInteger -Value $marker.marker_version) -or
        $marker.marker_version -ne $script:MarkerVersion) {
        throw "安装身份标记版本不受支持。"
    }

    if ($marker.main_version -isnot [string] -or
        $marker.main_version -notmatch '^\d+\.\d+\.\d+$') {
        throw "安装身份标记主程序版本无效。"
    }

    if ($marker.install_dir -isnot [string]) {
        throw "安装身份标记安装路径类型无效。"
    }

    $recorded = ConvertTo-NormalizedPath -Path $marker.install_dir
    $expected = ConvertTo-NormalizedPath -Path $InstallDirectory

    if ($recorded -ine $expected) {
        throw "安装身份标记记录的路径与固定安装目录不一致。"
    }

    return $marker
}

function Get-InstallDirectoryState {
    param([string]$InstallDirectory)

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
            Reason = "固定安装路径不是目录。"
        }
    }

    try {
        if (Test-PathReparsePoints -Path $InstallDirectory) {
            return [pscustomobject]@{
                State = "UNKNOWN_INVALID"
                MainVersion = $null
                Reason = "安装目录包含重解析点。"
            }
        }

        if (Test-DirectoryEmpty -Path $InstallDirectory) {
            return [pscustomobject]@{
                State = "EMPTY_DIRECTORY"
                MainVersion = $null
                Reason = "固定安装目录为空。"
            }
        }

        $marker = Test-InstallMarker -InstallDirectory $InstallDirectory

        $installedExe = Join-Path $InstallDirectory "lcmd.exe"
        $internalDirectory = Join-Path $InstallDirectory "_internal"

        if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) {
            throw "安装目录缺少 lcmd.exe。"
        }

        if (-not (Test-Path -LiteralPath $internalDirectory -PathType Container)) {
            throw "安装目录缺少 _internal 目录。"
        }

        if (Test-DirectoryEmpty -Path $internalDirectory) {
            throw "_internal 目录为空。"
        }

        $actualVersion = Get-ExecutableVersion -Executable $installedExe

        if ($actualVersion -cne $marker.main_version) {
            throw "安装标记版本与实际主程序版本不一致。"
        }

        return [pscustomobject]@{
            State = "VALID_LCMD_INSTALL"
            MainVersion = $marker.main_version
            Reason = "检测到有效 LCMD 安装。"
        }
    }
    catch {
        return [pscustomobject]@{
            State = "UNKNOWN_INVALID"
            MainVersion = $null
            Reason = $_.Exception.Message
        }
    }
}

function Test-KnowledgeDirectory {
    param([string]$Path)

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
        if (-not (Test-Path -LiteralPath $normalizedPath)) {
            return [pscustomobject]@{
                State = "NOT_EXISTS"
                Path = $normalizedPath
                Reason = "目录不存在。"
            }
        }

        if (-not (Test-Path -LiteralPath $normalizedPath -PathType Container)) {
            return [pscustomobject]@{
                State = "NOT_DIRECTORY"
                Path = $normalizedPath
                Reason = "指定路径不是目录。"
            }
        }

        if (Test-PathReparsePoints -Path $normalizedPath) {
            return [pscustomobject]@{
                State = "INACCESSIBLE"
                Path = $normalizedPath
                Reason = "知识库目录包含重解析点。"
            }
        }

        if (Test-DirectoryEmpty -Path $normalizedPath) {
            return [pscustomobject]@{
                State = "EMPTY_DIRECTORY"
                Path = $normalizedPath
                Reason = "目录为空。"
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




function Select-FirstInstallKnowledgePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DefaultKnowledgePath
    )

    $defaultState = Test-KnowledgeDirectory -Path $DefaultKnowledgePath

    Write-Host "标准知识库路径：$($defaultState.Path)"
    Write-Host "目标目录状态：$($defaultState.State)"

    switch ($defaultState.State) {
        "NOT_EXISTS" {
            break
        }
        "EMPTY_DIRECTORY" {
            break
        }
        "VALID_KNOWLEDGE" {
            break
        }
        default {
            throw "标准知识库目录异常，停止安装以保护现有内容：$($defaultState.Reason)"
        }
    }

    return [pscustomobject]@{
        Path   = $defaultState.Path
        Source = "DEFAULT"
        State  = $defaultState.State
    }
}

function Get-WindowsPreferredLanguage {
    $source = @'
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class LcmdWindowsLanguageNative
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool GetUserPreferredUILanguages(
        uint dwFlags,
        out uint pulNumLanguages,
        StringBuilder pwszLanguagesBuffer,
        ref uint pcchLanguagesBuffer
    );
}
'@

    if (-not ("LcmdWindowsLanguageNative" -as [type])) {
        Add-Type -TypeDefinition $source -ErrorAction Stop
    }

    # MUI_LANGUAGE_NAME = 0x8
    $count = [uint32]0
    $bufferSize = [uint32]0

    # 第一次调用只获取所需缓冲区长度。
    $success = [LcmdWindowsLanguageNative]::GetUserPreferredUILanguages(
        0x8,
        [ref]$count,
        $null,
        [ref]$bufferSize
    )

    if (-not $success) {
        $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()

        # ERROR_INSUFFICIENT_BUFFER = 122 是预期的查询结果。
        if ($errorCode -ne 122) {
            throw "无法检测 Windows 首选 UI 语言，错误代码：$errorCode"
        }
    }

    if ($count -lt 1 -or $bufferSize -lt 2) {
        throw "Windows 首选 UI 语言列表为空。"
    }

    $buffer = New-Object System.Text.StringBuilder ([int]$bufferSize)
    $capacity = [uint32]$bufferSize

    $success = [LcmdWindowsLanguageNative]::GetUserPreferredUILanguages(
        0x8,
        [ref]$count,
        $buffer,
        [ref]$capacity
    )

    if (-not $success) {
        $errorCode = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "读取 Windows 首选 UI 语言失败，错误代码：$errorCode"
    }

    $languages = @(
        $buffer.ToString().Split([char]0) |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )

    if ($languages.Count -lt 1) {
        throw "Windows 首选 UI 语言检测结果为空。"
    }

    $language = $languages[0].Trim()

    if ($language -notmatch '^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$') {
        throw "Windows 首选 UI 语言标识格式无效：$language"
    }

    return $language
}

function Test-ReleaseIntegrity {
    param(
        [string]$KnowledgeDirectory,
        [string]$IntegrityFile
    )

    try {
        $manifest = Get-Content -LiteralPath $IntegrityFile -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "发行包完整性清单无法读取：$($_.Exception.Message)"
    }

    if ($null -eq $manifest -or $manifest -is [array]) {
        throw "发行清单结构无效。"
    }

    if (-not (Test-JsonInteger -Value $manifest.schema_version) -or
        $manifest.schema_version -ne 1) {
        throw "不支持的发行清单 schema_version。"
    }

    if ($manifest.main_version -isnot [string] -or
        $manifest.main_version -notmatch '^\d+\.\d+\.\d+$') {
        throw "发行清单中的 main_version 无效。"
    }

    if ($manifest.knowledge_version -isnot [string] -or
        $manifest.knowledge_version -notmatch '^\d+\.\d+\.\d+$') {
        throw "发行清单中的 knowledge_version 无效。"
    }

    if (-not (Test-JsonInteger -Value $manifest.file_count) -or
        $manifest.file_count -lt 1) {
        throw "发行清单 file_count 无效。"
    }

    if ($manifest.files -isnot [array] -or
        $manifest.files.Count -lt 1) {
        throw "发行清单没有有效的文件记录。"
    }

    if ($manifest.file_count -ne $manifest.files.Count) {
        throw "发行清单 file_count 与实际记录数量不一致。"
    }

    $root = ConvertTo-NormalizedPath -Path $KnowledgeDirectory
    $prefix = $root.TrimEnd('\') + '\'

    if (Test-PathReparsePoints -Path $root) {
        throw "发行包知识库包含重解析点。"
    }

    $expectedPaths = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::OrdinalIgnoreCase
    )

    foreach ($record in $manifest.files) {
        if ($null -eq $record -or
            $record -is [array] -or
            $record.path -isnot [string] -or
            -not (Test-JsonInteger -Value $record.size) -or
            $record.size -lt 0 -or
            $record.sha256 -isnot [string]) {
            throw "发行清单包含无效文件记录。"
        }

        $relativePath = $record.path.Replace('/', '\')

        if ([string]::IsNullOrWhiteSpace($relativePath) -or
            [System.IO.Path]::IsPathRooted($relativePath) -or
            $relativePath.Contains(':')) {
            throw "发行清单包含不安全路径：$($record.path)"
        }

        $segments = @($relativePath -split '\\')

        foreach ($segment in $segments) {
            if ([string]::IsNullOrWhiteSpace($segment) -or
                $segment -eq "." -or
                $segment -eq ".." -or
                $segment.EndsWith(".") -or
                $segment.EndsWith(" ") -or
                $segment -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$') {
                throw "发行清单包含不安全路径段：$($record.path)"
            }

            if ($segment.IndexOfAny(
                [System.IO.Path]::GetInvalidFileNameChars()
            ) -ge 0) {
                throw "发行清单包含 Windows 不支持的文件名：$($record.path)"
            }
        }

        $filePath = [System.IO.Path]::GetFullPath(
            (Join-Path $root $relativePath)
        )

        if (-not $filePath.StartsWith(
            $prefix,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "发行清单文件路径超出知识库目录：$($record.path)"
        }

        $normalizedRelative = $relativePath.Replace('\', '/')

        if (-not $expectedPaths.Add($normalizedRelative)) {
            throw "发行清单存在重复路径：$normalizedRelative"
        }

        if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
            throw "发行包缺少文件：$normalizedRelative"
        }

        $item = Get-Item -LiteralPath $filePath -Force

        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "发行包文件不能是重解析点：$normalizedRelative"
        }

        if ($item.Length -ne [long]$record.size) {
            throw "文件大小校验失败：$normalizedRelative"
        }

        if ($record.sha256 -notmatch '^[A-Fa-f0-9]{64}$') {
            throw "文件 SHA-256 格式无效：$normalizedRelative"
        }

        $hash = (
            Get-FileHash -LiteralPath $filePath -Algorithm SHA256
        ).Hash

        if ($hash -ine $record.sha256) {
            throw "文件 SHA-256 校验失败：$normalizedRelative"
        }
    }

    $actualFiles = @(
        Get-ChildItem -LiteralPath $root -File -Recurse -Force -ErrorAction Stop
    )

    if ($actualFiles.Count -ne $expectedPaths.Count) {
        throw "知识库文件数量与发行清单不一致。"
    }

    foreach ($item in $actualFiles) {
        $actual = $item.FullName.Substring($prefix.Length).Replace('\', '/')

        if (-not $expectedPaths.Contains($actual)) {
            throw "知识库存在清单之外的文件：$actual"
        }
    }

    $script:MainVersion = $manifest.main_version

    return $manifest
}

function New-SiblingStageDirectory {
    param(
        [string]$ParentDirectory,
        [string]$Prefix
    )

    if (-not (Test-Path -LiteralPath $ParentDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $ParentDirectory -Force |
            Out-Null
    }

    $stagePath = Join-Path $ParentDirectory (
        $Prefix + [Guid]::NewGuid().ToString("N")
    )

    New-Item -ItemType Directory -Path $stagePath -ErrorAction Stop |
        Out-Null

    return $stagePath
}

function Copy-KnowledgeFiles {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
        New-Item -ItemType Directory -Path $Destination -Force |
            Out-Null
    }

    $items = @(Get-ChildItem -LiteralPath $Source -Force -ErrorAction Stop)

    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName `
            -Destination $Destination -Recurse -Force -ErrorAction Stop
    }
}

function Write-InstallMarker {
    param([string]$InstallDirectory)

    $marker = [ordered]@{
        product = $script:ProductId
        marker_version = $script:MarkerVersion
        main_version = $script:MainVersion
        install_dir = ConvertTo-NormalizedPath -Path $InstallDirectory
    }

    $markerFile = Join-Path $InstallDirectory ".lcmd-install.json"

    if (Test-Path -LiteralPath $markerFile) {
        throw "正式安装标记已经存在，拒绝覆盖。"
    }

    $temporaryFile = $markerFile + "." +
        [Guid]::NewGuid().ToString("N") + ".tmp"

    $json = $marker | ConvertTo-Json -Depth 4
    $encoding = New-Object System.Text.UTF8Encoding($false)

    try {
        [System.IO.File]::WriteAllText(
            $temporaryFile,
            $json + [Environment]::NewLine,
            $encoding
        )

        [System.IO.File]::Move($temporaryFile, $markerFile)
    }
    finally {
        if (Test-Path -LiteralPath $temporaryFile) {
            Remove-Item -LiteralPath $temporaryFile -Force -ErrorAction SilentlyContinue
        }
    }
}



function Add-LcmdToUserPath {
    param([string]$InstallDirectory)

    $registryKey = $null
    $changed = $false

    try {
        $registryKey = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(
            "Environment",
            $true
        )

        if ($null -eq $registryKey) {
            $registryKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey(
                "Environment"
            )
        }

        $valueNames = @($registryKey.GetValueNames())

        if ($valueNames -contains "Path") {
            $valueKind = $registryKey.GetValueKind("Path")

            if ($valueKind -ne [Microsoft.Win32.RegistryValueKind]::String -and
                $valueKind -ne [Microsoft.Win32.RegistryValueKind]::ExpandString) {
                throw "当前用户 PATH 注册表值类型不受支持：$valueKind"
            }

            $existingPath = [string]$registryKey.GetValue(
                "Path",
                "",
                [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
            )
        }
        else {
            $valueKind = [Microsoft.Win32.RegistryValueKind]::String
            $existingPath = ""
        }

        $target = ConvertTo-NormalizedPath -Path $InstallDirectory
        $alreadyExists = $false

        $entries = @($existingPath -split ';')

        foreach ($entry in $entries) {
            if ([string]::IsNullOrWhiteSpace($entry)) {
                continue
            }

            $expanded = [Environment]::ExpandEnvironmentVariables(
                $entry.Trim().Trim('"')
            )

            try {
                $normalized = ConvertTo-NormalizedPath -Path $expanded

                if ($normalized -ieq $target) {
                    $alreadyExists = $true
                    break
                }
            }
            catch {
                # 保留原有 PATH 中无法规范化的条目。
            }
        }

        if (-not $alreadyExists) {
            if ([string]::IsNullOrEmpty($existingPath)) {
                $newPath = $target
            }
            else {
                $newPath = $existingPath.TrimEnd(';') + ';' + $target
            }

            $registryKey.SetValue("Path", $newPath, $valueKind)
            $changed = $true
        }

        $registryKey.Flush()
    }
    finally {
        if ($null -ne $registryKey) {
            $registryKey.Dispose()
        }
    }

    if (-not $changed) {
        Write-Host "当前用户 PATH 已包含 LCMD 安装目录。"
        return
    }

    $nativeSource = @'
using System;
using System.Runtime.InteropServices;

public static class LcmdEnvironmentNotification
{
    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd,
        uint Msg,
        UIntPtr wParam,
        string lParam,
        uint fuFlags,
        uint uTimeout,
        out UIntPtr lpdwResult
    );
}
'@

    if (-not ("LcmdEnvironmentNotification" -as [type])) {
        Add-Type -TypeDefinition $nativeSource -ErrorAction Stop
    }

    $result = [UIntPtr]::Zero

    $sendResult = [LcmdEnvironmentNotification]::SendMessageTimeout(
        [IntPtr](-1),
        0x001A,
        [UIntPtr]::Zero,
        "Environment",
        0x0002,
        5000,
        [ref]$result
    )

    if ($sendResult -eq [IntPtr]::Zero) {
        throw "当前用户 PATH 已写入，但 Windows 环境变量变更通知发送失败。"
    }

    Write-Host "当前用户 PATH 已更新：$target"
}

try {
    Write-Host ""
    Write-Host "LCMD Windows 安装程序" -ForegroundColor Cyan
    Write-Host "首次安装模式"
    Write-Host "主程序安装路径固定，不提供自定义路径。"

    # ------------------------------------------------------------
    # 1. 环境检查
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "1/8 环境检查" -MinimumMilliseconds 800 -Action {
        $script:PackageRoot = ConvertTo-NormalizedPath -Path $PSScriptRoot

        $script:Exe = Join-Path $script:PackageRoot "app\lcmd.exe"
        $packageInternal = Join-Path $script:PackageRoot "app\_internal"
        $script:PackageKnowledge = Join-Path $script:PackageRoot "knowledge"
        $script:PackageIntegrity = Join-Path $script:PackageRoot "knowledge-integrity.json"

        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            throw "无法取得 LOCALAPPDATA 环境变量。"
        }

        foreach ($requiredPath in @(
            $script:Exe,
            $packageInternal,
            $script:PackageKnowledge,
            $script:PackageIntegrity
        )) {
            if (-not (Test-Path -LiteralPath $requiredPath)) {
                throw "发行包缺少必要文件或目录：$requiredPath"
            }
        }

        if (-not (Test-Path -LiteralPath $script:Exe -PathType Leaf)) {
            throw "发行包 lcmd.exe 无效。"
        }

        if (-not (Test-Path -LiteralPath $packageInternal -PathType Container) -or
            (Test-DirectoryEmpty -Path $packageInternal)) {
            throw "发行包 app\_internal 无效或为空。"
        }

        $null = Test-ReleaseIntegrity `
            -KnowledgeDirectory $script:PackageKnowledge `
            -IntegrityFile $script:PackageIntegrity

        $packageVersion = Get-ExecutableVersion -Executable $script:Exe

        if ($packageVersion -cne $script:MainVersion) {
            throw "发行包主程序实际版本与完整性清单不一致。"
        }

        $null = & $script:Exe "--internal-validate-knowledge" $script:PackageKnowledge

        if ($LASTEXITCODE -ne 0) {
            throw "发行包自带知识库结构验证失败。"
        }

        Write-Host "发行包结构：通过"
        Write-Host "发行包文件 SHA-256：通过"
        Write-Host "发行包知识库结构：通过"
        Write-Host "主程序实际版本：$packageVersion"
    } | Out-Null

    # ------------------------------------------------------------
    # 2. 安装准备
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "2/8 安装准备" -MinimumMilliseconds 800 -Action {
        $programsDirectory = Join-Path $env:LOCALAPPDATA "Programs"

        $script:InstallDirectory = ConvertTo-NormalizedPath -Path (
            Join-Path $programsDirectory "LCMD"
        )

        $script:ConfigDirectory = ConvertTo-NormalizedPath -Path (
            Join-Path $env:LOCALAPPDATA "lcmd"
        )

        $script:ConfigFile = Join-Path $script:ConfigDirectory "config.toml"

        $installState = Get-InstallDirectoryState `
            -InstallDirectory $script:InstallDirectory

        Write-Host "固定安装目录：$script:InstallDirectory"
        Write-Host "安装目录状态：$($installState.State)"

        if ($installState.State -eq "VALID_LCMD_INSTALL") {
            throw "检测到已有 LCMD 安装（版本 $($installState.MainVersion)）。当前安装程序只处理首次安装，不执行升级。"
        }

        if ($installState.State -eq "UNKNOWN_INVALID") {
            throw "固定安装目录包含未知内容，停止安装以保护现有文件：$($installState.Reason)"
        }

        # 安装器始终使用标准知识库目录，不恢复用户以前的自定义路径。
        $defaultKnowledgePath = Join-Path $script:ConfigDirectory "knowledge"

        $selection = Select-FirstInstallKnowledgePath `
            -DefaultKnowledgePath $defaultKnowledgePath

        $script:KnowledgePath = $selection.Path
        $script:KnowledgeSource = $selection.Source

        if (Test-Path -LiteralPath $script:ConfigFile) {
            if (-not (Test-Path -LiteralPath $script:ConfigFile -PathType Leaf)) {
                throw "配置文件路径存在，但不是普通文件。"
            }

            $configItem = Get-Item -LiteralPath $script:ConfigFile -Force

            if (($configItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "配置文件不能是重解析点。"
            }

            Write-Host "现有配置文件：存在"
            Write-Host "安装后将更新知识库路径，保留原有 platform 和 language。"

            # 不再读取配置中的旧知识库路径。
            # 配置解析及有效性检查由内部配置初始化命令完成。
            $script:DetectedLanguage = "zh-CN"
        }
        else {
            Write-Host "现有配置文件：不存在"

            $script:DetectedLanguage = Get-WindowsPreferredLanguage
            Write-Host "Windows 首选 UI 语言：$script:DetectedLanguage"
        }


    } | Out-Null

    # ------------------------------------------------------------
    # 3. 主程序部署
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "3/8 主程序部署" -MinimumMilliseconds 1000 -Action {
        $programsDirectory = Split-Path -Parent $script:InstallDirectory

        if (-not (Test-Path -LiteralPath $programsDirectory -PathType Container)) {
            New-Item -ItemType Directory -Path $programsDirectory -Force |
                Out-Null
        }

        $script:AppStageDirectory = New-SiblingStageDirectory `
            -ParentDirectory $programsDirectory `
            -Prefix ".lcmd-app-stage-"

        $appSource = Join-Path $script:PackageRoot "app"
        $sourceItems = @(Get-ChildItem -LiteralPath $appSource -Force)

        foreach ($item in $sourceItems) {
            Copy-Item -LiteralPath $item.FullName `
                -Destination $script:AppStageDirectory `
                -Recurse -Force -ErrorAction Stop
        }

        $stagedExe = Join-Path $script:AppStageDirectory "lcmd.exe"
        $stagedInternal = Join-Path $script:AppStageDirectory "_internal"

        if (-not (Test-Path -LiteralPath $stagedExe -PathType Leaf) -or
            -not (Test-Path -LiteralPath $stagedInternal -PathType Container) -or
            (Test-DirectoryEmpty -Path $stagedInternal)) {
            throw "主程序临时部署后关键文件检查失败。"
        }

        $stagedVersion = Get-ExecutableVersion -Executable $stagedExe

        if ($stagedVersion -cne $script:MainVersion) {
            throw "主程序临时部署版本与发行清单不一致。"
        }

        if (Test-Path -LiteralPath $script:InstallDirectory) {
            if (-not (Test-DirectoryEmpty -Path $script:InstallDirectory)) {
                throw "固定安装目录不为空，拒绝覆盖。"
            }

            Remove-Item -LiteralPath $script:InstallDirectory -Force
        }

        [System.IO.Directory]::Move(
            $script:AppStageDirectory,
            $script:InstallDirectory
        )

        $script:AppStageDirectory = $null

        Write-Host "主程序已部署到固定目录。"
        Write-Host "主程序版本：$stagedVersion"
    } | Out-Null

    # ------------------------------------------------------------
    # 4. 知识库部署
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "4/8 知识库部署" -MinimumMilliseconds 1000 -Action {
        $targetState = Test-KnowledgeDirectory -Path $script:KnowledgePath

        if ($targetState.State -eq "VALID_KNOWLEDGE") {
            Write-Host "目标位置已有有效知识库，不覆盖现有内容。"
        }
        elseif ($targetState.State -eq "NOT_EXISTS" -or
            $targetState.State -eq "EMPTY_DIRECTORY") {

            $knowledgeParent = Split-Path -Parent $script:KnowledgePath

            $script:KnowledgeStageDirectory = New-SiblingStageDirectory `
                -ParentDirectory $knowledgeParent `
                -Prefix ".lcmd-knowledge-stage-"

            Copy-KnowledgeFiles `
                -Source $script:PackageKnowledge `
                -Destination $script:KnowledgeStageDirectory

            # 在临时目录中完成全部文件完整性和结构验证。
            $null = Test-ReleaseIntegrity `
                -KnowledgeDirectory $script:KnowledgeStageDirectory `
                -IntegrityFile $script:PackageIntegrity

            $null = & $script:Exe `
                "--internal-validate-knowledge" `
                $script:KnowledgeStageDirectory

            if ($LASTEXITCODE -ne 0) {
                throw "知识库临时部署后的结构验证失败。"
            }

            # 只有新知识库全部验证通过，才处理正式目标目录。
            if (Test-Path -LiteralPath $script:KnowledgePath) {
                if (-not (Test-DirectoryEmpty -Path $script:KnowledgePath)) {
                    throw "知识库目标目录已不为空，拒绝覆盖。"
                }

                Remove-Item -LiteralPath $script:KnowledgePath -Force
            }

            [System.IO.Directory]::Move(
                $script:KnowledgeStageDirectory,
                $script:KnowledgePath
            )

            $script:KnowledgeStageDirectory = $null

            Write-Host "知识库部署及完整性复核通过。"
        }
        else {
            throw "知识库目标目录状态异常：$($targetState.State)。不会覆盖现有内容。"
        }
    } | Out-Null

    # ------------------------------------------------------------
    # 5. 配置初始化
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "5/8 配置初始化" -MinimumMilliseconds 800 -Action {
        if (-not (Test-Path -LiteralPath $script:ConfigDirectory -PathType Container)) {
            New-Item -ItemType Directory `
                -Path $script:ConfigDirectory -Force |
                Out-Null
        }

        $language = $script:DetectedLanguage

        if ([string]::IsNullOrWhiteSpace($language)) {
            $language = Get-WindowsPreferredLanguage
        }

        $null = & $script:Exe `
            "--internal-initialize-config" `
            $script:KnowledgePath `
            "windows" `
            $language `
            $script:ConfigFile

        if ($LASTEXITCODE -ne 0) {
            throw "LCMD 配置初始化失败。"
        }

        Write-Host "配置初始化成功。"
        Write-Host "配置文件：$script:ConfigFile"
        Write-Host "知识库路径：$script:KnowledgePath"
    } | Out-Null

    # ------------------------------------------------------------
    # 6. 安装验证
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "6/8 安装验证" -MinimumMilliseconds 1000 -Action {
        $installedExe = Join-Path $script:InstallDirectory "lcmd.exe"
        $installedInternal = Join-Path $script:InstallDirectory "_internal"

        if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf) -or
            -not (Test-Path -LiteralPath $installedInternal -PathType Container) -or
            (Test-DirectoryEmpty -Path $installedInternal)) {
            throw "安装后的主程序文件检查失败。"
        }

        $installedVersion = Get-ExecutableVersion -Executable $installedExe

        if ($installedVersion -cne $script:MainVersion) {
            throw "安装后的主程序版本与发行清单不一致。"
        }

        $null = & $installedExe `
            "--internal-validate-knowledge" `
            $script:KnowledgePath

        if ($LASTEXITCODE -ne 0) {
            throw "安装后的知识库验证失败。"
        }

        $null = & $installedExe `
            "--internal-validate-config" `
            $script:ConfigFile

        if ($LASTEXITCODE -ne 0) {
            throw "安装后的配置验证失败。"
        }

        Write-Host "主程序关键文件：通过"
        Write-Host "主程序实际版本：$installedVersion"
        Write-Host "知识库结构：通过"
        Write-Host "配置文件：通过"
    } | Out-Null

    # ------------------------------------------------------------
    # 7. PATH 环境变量配置
    # ------------------------------------------------------------

    Write-Section "7/8 PATH 环境变量配置"

    Add-LcmdToUserPath -InstallDirectory $script:InstallDirectory
    $script:CompletedStages += "PATH 环境变量配置"

    Write-Host "当前用户 PATH 配置成功。" -ForegroundColor Green

    # ------------------------------------------------------------
    # 8. 完成收尾
    # ------------------------------------------------------------

    Invoke-InstallStage -Name "8/8 完成收尾" -MinimumMilliseconds 800 -Action {
        # PATH 成功后才写入正式安装身份标记。
        Write-InstallMarker -InstallDirectory $script:InstallDirectory

        $marker = Test-InstallMarker `
            -InstallDirectory $script:InstallDirectory

        if ($marker.main_version -cne $script:MainVersion) {
            throw "安装身份标记中的主程序版本与发行包不一致。"
        }

        Write-Host "安装目录：$script:InstallDirectory"
        Write-Host "配置文件：$script:ConfigFile"
        Write-Host "知识库目录：$script:KnowledgePath"
        Write-Host "主程序版本：$script:MainVersion"
        Write-Host "安装身份标记：通过"
    } | Out-Null

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "LCMD 首次安装成功！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "请重新打开 PowerShell 或终端，然后运行："
    Write-Host "  lcmd ls"
    Write-Host "  lcmd --help"
    Write-Host "  lcmd --version"
    Write-Host ""
    Write-Host "INSTALL_RESULT=SUCCESS"
}
catch {
    $script:ExitCode = 1

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "LCMD 安装失败" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "停止原因：$($_.Exception.Message)" -ForegroundColor Red

    Write-Host ""
    Write-Host "已完成阶段："

    if ($script:CompletedStages.Count -eq 0) {
        Write-Host "  无"
    }
    else {
        foreach ($stage in $script:CompletedStages) {
            Write-Host "  $stage"
        }
    }

    Write-Host ""
    Write-Host "INSTALL_RESULT=ERROR"
    Write-Host "注意：本版本不提供失败回滚或完整中断恢复。"
    Write-Host "请保留现场，不要手动删除已有知识库或配置文件。"
}
finally {
    # 只清理本次运行创建、尚未提升为正式目录的临时目录。
    foreach ($stageDirectory in @(
        $script:AppStageDirectory,
        $script:KnowledgeStageDirectory
    )) {
        if (-not [string]::IsNullOrWhiteSpace($stageDirectory) -and
            (Test-Path -LiteralPath $stageDirectory)) {
            try {
                Remove-Item -LiteralPath $stageDirectory `
                    -Recurse -Force -ErrorAction Stop
            }
            catch {
                Write-Warning "临时目录清理失败，请保留并检查：$stageDirectory"
            }
        }
    }
}

exit $script:ExitCode
