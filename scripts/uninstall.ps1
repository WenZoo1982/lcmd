#requires -Version 5.1

[CmdletBinding(SupportsShouldProcess = $true)]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:ProductId = "WenZoo.LCMD"
$script:MarkerVersion = 1
$script:ExitCode = 0
$script:InstallDirectory = $null
$script:DataDirectory = $null
$script:KnowledgeDirectory = $null
$script:ConfigFile = $null
$script:PathEntryRemoved = $false

function ConvertTo-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not [System.IO.Path]::IsPathRooted($Path)) {
        throw "路径无效或不是绝对路径：$Path"
    }

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($fullPath)

    if ($fullPath.Length -gt $root.Length) {
        $fullPath = $fullPath.TrimEnd([char[]]@(92, 47))
    }

    return $fullPath
}

function Test-PathReparsePoints {
    param([Parameter(Mandatory = $true)][string]$Path)

    $rootItem = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        return $true
    }

    if ($rootItem.PSIsContainer) {
        foreach ($item in Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction Stop) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                return $true
            }
        }
    }

    return $false
}

function Test-InstallMarker {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $markerFile = Join-Path $Directory ".lcmd-install.json"
    if (-not (Test-Path -LiteralPath $markerFile -PathType Leaf)) {
        throw "安装身份标记不存在，无法确认这是 LCMD 安装目录。"
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

    $requiredFields = @("product", "marker_version", "main_version", "install_dir")
    $actualFields = @($marker.PSObject.Properties | ForEach-Object { $_.Name })

    if ($actualFields.Count -ne 4) {
        throw "安装身份标记字段数量不正确。"
    }

    foreach ($field in $requiredFields) {
        if ($actualFields -cnotcontains $field) {
            throw "安装身份标记缺少字段：$field"
        }
    }

    if ($marker.product -isnot [string] -or $marker.product -cne $script:ProductId) {
        throw "安装身份标记产品标识不匹配。"
    }

    if ($marker.marker_version -isnot [int] -or
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
    $expected = ConvertTo-NormalizedPath -Path $Directory
    if ($recorded -ine $expected) {
        throw "安装身份标记记录的路径与固定安装目录不一致。"
    }

    return $marker
}

function Write-UninstallCenteredText {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text,
        [ConsoleColor]$ForegroundColor = [ConsoleColor]::Gray
    )

    try {
        $width = [Console]::BufferWidth
    }
    catch {
        Write-Host $Text -ForegroundColor $ForegroundColor
        return
    }

    if ($width -le 1) {
        Write-Host $Text -ForegroundColor $ForegroundColor
        return
    }

    $displayWidth = 0
    foreach ($character in $Text.ToCharArray()) {
        if ([int]$character -gt 255) { $displayWidth += 2 }
        else { $displayWidth++ }
    }

    $left = [Math]::Max(0, [int][Math]::Floor(($width - $displayWidth) / 2))
    Write-Host ((" " * $left) + $Text) -ForegroundColor $ForegroundColor
}

function Write-UninstallProgress {
    param(
        [Parameter(Mandatory = $true)][string]$Stage,
        [Parameter(Mandatory = $true)][int]$Percent,
        [switch]$Initialize
    )

    try {
        if ($Initialize) {
            $script:ProgressTop = [Console]::CursorTop
        }

        $width = [Console]::BufferWidth
        if ($width -le 1 -or [Console]::BufferHeight -lt ($script:ProgressTop + 3)) {
            throw "控制台空间不足。"
        }

        $stageLine = "正在执行：$Stage"
        $progressLine = "已完成：$Percent%"
        $stageLeft = [Math]::Max(0, [int][Math]::Floor(($width - $stageLine.Length) / 2))
        $progressLeft = [Math]::Max(0, [int][Math]::Floor(($width - $progressLine.Length) / 2))
        $oldColor = [Console]::ForegroundColor

        [Console]::SetCursorPosition(0, $script:ProgressTop)
        [Console]::Write(" " * ($width - 1))
        [Console]::SetCursorPosition($stageLeft, $script:ProgressTop)
        [Console]::ForegroundColor = [ConsoleColor]::Cyan
        [Console]::Write($stageLine)

        [Console]::SetCursorPosition(0, $script:ProgressTop + 1)
        [Console]::Write(" " * ($width - 1))
        [Console]::SetCursorPosition($progressLeft, $script:ProgressTop + 1)
        [Console]::ForegroundColor = [ConsoleColor]::Green
        [Console]::Write($progressLine)
        [Console]::ForegroundColor = $oldColor
        [Console]::SetCursorPosition(0, $script:ProgressTop + 2)
    }
    catch {
        Write-Host "$Stage（$Percent%）"
    }
}

function Remove-LcmdFromUserPath {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
    if ($null -eq $key) {
        Write-Host "当前用户 PATH 注册表项不存在，无需清理。"
        return
    }

    try {
        if (@($key.GetValueNames()) -notcontains "Path") {
            Write-Host "当前用户 PATH 未设置，无需清理。"
            return
        }

        $kind = $key.GetValueKind("Path")
        if ($kind -ne [Microsoft.Win32.RegistryValueKind]::String -and
            $kind -ne [Microsoft.Win32.RegistryValueKind]::ExpandString) {
            throw "当前用户 PATH 注册表值类型不受支持：$kind"
        }

        $rawPath = [string]$key.GetValue(
            "Path",
            "",
            [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
        )

        $target = ConvertTo-NormalizedPath -Path $script:InstallDirectory
        $keptEntries = New-Object System.Collections.Generic.List[string]

        foreach ($entry in $rawPath.Split([char]';')) {
            if ([string]::IsNullOrWhiteSpace($entry)) {
                $keptEntries.Add($entry)
                continue
            }

            $candidate = [Environment]::ExpandEnvironmentVariables($entry.Trim().Trim('"'))
            $matchesTarget = $false
            try {
                $matchesTarget = (ConvertTo-NormalizedPath -Path $candidate) -ieq $target
            }
            catch {
                # 无法识别的原有 PATH 条目必须原样保留。
            }

            if ($matchesTarget) {
                $script:PathEntryRemoved = $true
            }
            else {
                $keptEntries.Add($entry)
            }
        }

        if (-not $script:PathEntryRemoved) {
            Write-Host "当前用户 PATH 不包含 LCMD 安装目录，无需清理。"
            return
        }

        $newPath = $keptEntries -join ';'
        if (-not $WhatIfPreference) {
            if ([string]::IsNullOrEmpty($newPath)) {
                $key.DeleteValue("Path", $false)
            }
            else {
                $key.SetValue("Path", $newPath, $kind)
            }
            $key.Flush()
        }
    }
    finally {
        $key.Dispose()
    }

    if ($script:PathEntryRemoved) {
        if ($WhatIfPreference) {
            Write-Host "模拟：将从当前用户 PATH 中移除 LCMD 安装目录。"
        }
        else {
            Write-Host "已从当前用户 PATH 中移除 LCMD 安装目录。"

            $nativeSource = @'
using System;
using System.Runtime.InteropServices;

public static class LcmdUninstallEnvironmentNotification
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

            try {
                if (-not ("LcmdUninstallEnvironmentNotification" -as [type])) {
                    Add-Type -TypeDefinition $nativeSource -ErrorAction Stop
                }

                $result = [UIntPtr]::Zero
                $sendResult = [LcmdUninstallEnvironmentNotification]::SendMessageTimeout(
                    [IntPtr](-1),
                    0x001A,
                    [UIntPtr]::Zero,
                    "Environment",
                    0x0002,
                    5000,
                    [ref]$result
                )

                if ($sendResult -eq [IntPtr]::Zero) {
                    Write-Warning "PATH 已更新，但 Windows 环境变量变更通知发送失败。"
                }
            }
            catch {
                Write-Warning "PATH 已更新，但环境变量变更通知失败：$($_.Exception.Message)"
            }
        }
    }
}

try {
    Clear-Host
    Write-Host ""
    Write-UninstallCenteredText "LCMD Windows 卸载程序" -ForegroundColor Cyan
    Write-UninstallCenteredText "移除 LCMD 主程序与官方知识库" -ForegroundColor DarkCyan
    Write-Host ""

    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "无法取得 LOCALAPPDATA 环境变量。"
    }

    $localAppData = ConvertTo-NormalizedPath -Path $env:LOCALAPPDATA
    $programsDirectory = Join-Path $localAppData "Programs"
    if (Test-Path -LiteralPath $programsDirectory) {
        $programsItem = Get-Item -LiteralPath $programsDirectory -Force
        if (-not $programsItem.PSIsContainer -or
            ($programsItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Programs 父目录不是普通目录，或包含重解析点。"
        }
    }

    $script:InstallDirectory = ConvertTo-NormalizedPath -Path (
        Join-Path $programsDirectory "LCMD"
    )
    $script:DataDirectory = ConvertTo-NormalizedPath -Path (
        Join-Path $localAppData "lcmd"
    )
    $script:KnowledgeDirectory = Join-Path $script:DataDirectory "knowledge"
    $script:ConfigFile = Join-Path $script:DataDirectory "config.toml"

    Write-Host "固定安装目录：$script:InstallDirectory"
    Write-Host "官方知识库：$script:KnowledgeDirectory"
    Write-Host "配置文件：$script:ConfigFile"
    Write-Host ""

    if (-not (Test-Path -LiteralPath $script:InstallDirectory -PathType Container)) {
        throw "固定安装目录不存在，或不是目录。为避免误删，已停止卸载。"
    }

    if (Test-PathReparsePoints -Path $script:InstallDirectory) {
        throw "主程序安装目录包含重解析点，已停止卸载。"
    }

    $marker = Test-InstallMarker -Directory $script:InstallDirectory

    $exe = Join-Path $script:InstallDirectory "lcmd.exe"
    $internalDirectory = Join-Path $script:InstallDirectory "_internal"
    $uninstaller = Join-Path $script:InstallDirectory "uninstall.ps1"

    if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $internalDirectory -PathType Container)) {
        throw "主程序安装目录缺少 onedir 关键文件，无法确认安装完整性。"
    }

    $internalFirstItem = Get-ChildItem -LiteralPath $internalDirectory -Force |
        Select-Object -First 1
    if ($null -eq $internalFirstItem) {
        throw "主程序 _internal 目录为空，无法确认安装完整性。"
    }

    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw "安装目录缺少 uninstall.ps1，请从发行包中的 app 目录运行卸载脚本。"
    }

    if (Test-Path -LiteralPath $script:DataDirectory) {
        if (-not (Test-Path -LiteralPath $script:DataDirectory -PathType Container)) {
            throw "LCMD 数据路径存在，但不是目录。"
        }
        $dataDirectoryItem = Get-Item -LiteralPath $script:DataDirectory -Force
        if (($dataDirectoryItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "LCMD 数据目录本身是重解析点，已停止卸载。"
        }
    }

    if (Test-Path -LiteralPath $script:KnowledgeDirectory) {
        if (-not (Test-Path -LiteralPath $script:KnowledgeDirectory -PathType Container)) {
            throw "官方知识库路径存在，但不是目录。"
        }
        if (Test-PathReparsePoints -Path $script:KnowledgeDirectory) {
            throw "官方知识库目录包含重解析点，已停止卸载。"
        }
    }

    if (Test-Path -LiteralPath $script:ConfigFile) {
        if (-not (Test-Path -LiteralPath $script:ConfigFile -PathType Leaf)) {
            throw "配置文件路径存在，但不是普通文件。"
        }
        $configItem = Get-Item -LiteralPath $script:ConfigFile -Force
        if (($configItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "配置文件不能是重解析点。"
        }
    }

    Write-Host "检测到 LCMD 主程序版本：$($marker.main_version)"
    Write-Host ""
    Write-Host "卸载将删除以上 LCMD 主程序、官方知识库和配置文件。"
    Write-Host "同时只移除当前用户 PATH 中与 LCMD 安装目录完全匹配的条目。"
    Write-Host "其他文件、其他 PATH 条目及用户自定义知识库目录均会保留。"
    Write-Host ""

    $answer = Read-Host "确认卸载 LCMD？请输入 Y 继续，其他输入取消"
    if ($answer -notmatch '^(?i)y$') {
        Write-Host ""
        Write-UninstallCenteredText "已取消卸载，未更改任何内容。" -ForegroundColor Yellow
        exit 0
    }

    Write-Host ""
    Write-UninstallProgress -Stage "1/4 卸载准备" -Percent 0 -Initialize

    # 切换工作目录，避免当前目录占用待删除的安装目录。
    Set-Location -LiteralPath $env:TEMP

    Write-UninstallProgress -Stage "2/4 删除主程序" -Percent 25
    if ($PSCmdlet.ShouldProcess($script:InstallDirectory, "删除 LCMD 主程序目录")) {
        Remove-Item -LiteralPath $script:InstallDirectory -Recurse -Force -ErrorAction Stop
    }

    Write-UninstallProgress -Stage "3/4 删除知识库与配置" -Percent 60
    if (Test-Path -LiteralPath $script:KnowledgeDirectory -PathType Container) {
        if ($PSCmdlet.ShouldProcess($script:KnowledgeDirectory, "删除 LCMD 官方知识库")) {
            Remove-Item -LiteralPath $script:KnowledgeDirectory -Recurse -Force -ErrorAction Stop
        }
    }

    if (Test-Path -LiteralPath $script:ConfigFile -PathType Leaf) {
        if ($PSCmdlet.ShouldProcess($script:ConfigFile, "删除 LCMD 配置文件")) {
            Remove-Item -LiteralPath $script:ConfigFile -Force -ErrorAction Stop
        }
    }

    if (Test-Path -LiteralPath $script:DataDirectory -PathType Container) {
        $remainingItems = @(Get-ChildItem -LiteralPath $script:DataDirectory -Force)
        if ($remainingItems.Count -eq 0 -and
            $PSCmdlet.ShouldProcess($script:DataDirectory, "删除空的 LCMD 数据目录")) {
            Remove-Item -LiteralPath $script:DataDirectory -Force -ErrorAction Stop
        }
        elseif ($remainingItems.Count -gt 0) {
            Write-Host "数据目录中仍有非 LCMD 内容，已保留：$script:DataDirectory" -ForegroundColor Yellow
        }
    }

    Write-UninstallProgress -Stage "4/4 清理 PATH 并完成" -Percent 85
    Remove-LcmdFromUserPath

    Write-UninstallProgress -Stage "4/4 清理 PATH 并完成" -Percent 100

    Write-Host ""
    if ($WhatIfPreference) {
        Write-UninstallCenteredText "卸载模拟完成（未更改任何文件或 PATH）。" -ForegroundColor Yellow
    }
    else {
        Write-UninstallCenteredText "========================================" -ForegroundColor Green
        Write-UninstallCenteredText "LCMD 卸载成功！" -ForegroundColor Green
        Write-UninstallCenteredText "========================================" -ForegroundColor Green
        Write-Host ""
        Write-UninstallCenteredText "LCMD 主程序、官方知识库及配置已按卸载范围处理。" -ForegroundColor Cyan
        Write-UninstallCenteredText "请重新打开 PowerShell 或终端。" -ForegroundColor Cyan
    }
}
catch {
    $script:ExitCode = 1
    Write-Host ""
    Write-UninstallCenteredText "========================================" -ForegroundColor Red
    Write-UninstallCenteredText "LCMD 卸载失败" -ForegroundColor Red
    Write-UninstallCenteredText "========================================" -ForegroundColor Red
    Write-UninstallCenteredText "停止原因：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-UninstallCenteredText "UNINSTALL_RESULT=ERROR" -ForegroundColor Red
}
exit $script:ExitCode
