
param(
    [Parameter(Mandatory = $true)]
    [string]$MainVersion,

    [Parameter(Mandatory = $false)]
    [string]$Prerelease = "",

    [Parameter(Mandatory = $true)]
    [string]$KnowledgeArchive,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedKnowledgeSha256,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$specFile = Join-Path $repoRoot "lcmd.spec"
$installScript = Join-Path $PSScriptRoot "install.ps1"

$outputCreated = $false
$buildSucceeded = $false
$failureMessage = $null

function Get-RelativeFilePath {
    param(
        [string]$Root,
        [string]$File
    )

    $prefix = $Root.TrimEnd('\') + '\'
    return $File.Substring($prefix.Length).Replace('\', '/')
}

try {
    Write-Host "`n========== 输入参数检查 ==========" -ForegroundColor Cyan

    if (-not (Test-Path $python -PathType Leaf)) {
        throw "未找到项目虚拟环境 Python：$python"
    }

    if (-not (Test-Path $specFile -PathType Leaf)) {
        throw "未找到 PyInstaller 配置：$specFile"
    }

    if (-not (Test-Path $installScript -PathType Leaf)) {
        throw "未找到安装脚本：$installScript"
    }

    if (-not (Test-Path $KnowledgeArchive -PathType Leaf)) {
        throw "知识库 ZIP 不存在：$KnowledgeArchive"
    }

    if ($MainVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw "主程序版本格式无效：$MainVersion"
    }

    if (-not [string]::IsNullOrEmpty($Prerelease) -and $Prerelease -notmatch '^[a-zA-Z0-9.-]+$') {
        throw "Pre-release 标识格式无效：$Prerelease"
    }

    if ($ExpectedKnowledgeSha256 -notmatch '^[A-Fa-f0-9]{64}$') {
        throw "预期 SHA-256 格式无效。"
    }

    $outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
    $archivePath = (Resolve-Path $KnowledgeArchive).Path

    if (Test-Path $outputPath) {
        throw "发行输出目录已经存在，为避免覆盖，停止构建：$outputPath"
    }

    $currentVersion = & $python -c "import sys; sys.path.insert(0, r'$repoRoot\src'); import lcmd; print(lcmd.__version__)"

    if ($LASTEXITCODE -ne 0) {
        throw "读取主程序版本失败。"
    }

    $currentVersion = ($currentVersion | Out-String).Trim()

    if ($currentVersion -ne $MainVersion) {
        throw "参数主程序版本 $MainVersion 与源码版本 $currentVersion 不一致。"
    }

    Write-Host "主程序版本：$MainVersion"

    if ([string]::IsNullOrEmpty($Prerelease)) {
        Write-Host "发行类型：稳定版"
    }
    else {
        Write-Host "Pre-release：$Prerelease"
    }

    Write-Host "安装脚本：$installScript"

    Write-Host "`n========== 知识库 ZIP 校验 ==========" -ForegroundColor Cyan

    $actualArchiveHash = (Get-FileHash $archivePath -Algorithm SHA256).Hash

    if ($actualArchiveHash -ne $ExpectedKnowledgeSha256.ToUpperInvariant()) {
        throw "知识库 ZIP SHA-256 校验失败。"
    }

    Write-Host "知识库 ZIP SHA-256 校验通过。" -ForegroundColor Green

    $tempDir = Join-Path $env:TEMP ("lcmd-release-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempDir | Out-Null

    try {
        Write-Host "`n========== 解压并检查知识库 ==========" -ForegroundColor Cyan

        $knowledgeSource = Join-Path $tempDir "knowledge"

        Expand-Archive -LiteralPath $archivePath -DestinationPath $knowledgeSource

        $kbManifestPath = Join-Path $knowledgeSource "manifest.json"

        if (-not (Test-Path $kbManifestPath -PathType Leaf)) {
            throw "知识库根目录缺少 manifest.json。"
        }

        $kbManifest = Get-Content $kbManifestPath -Raw | ConvertFrom-Json

        $manifestProperties = @($kbManifest.PSObject.Properties.Name)

        if (
            $manifestProperties.Count -ne 1 -or
            $manifestProperties[0] -ne "version"
        ) {
            throw "知识库 manifest.json 必须且只能包含 version 字段。"
        }

        $knowledgeVersion = [string]$kbManifest.version

        if ($knowledgeVersion -notmatch '^\d+\.\d+\.\d+$') {
            throw "知识库版本格式无效：$knowledgeVersion"
        }

        $knowledgeMajor = [int]($knowledgeVersion.Split('.')[0])

        if ($knowledgeMajor -ne 0) {
            throw "当前主程序不支持知识库主版本：$knowledgeMajor"
        }

        $platformsDir = Join-Path $knowledgeSource "commands\platforms"

        if (-not (Test-Path $platformsDir -PathType Container)) {
            throw "知识库缺少 commands/platforms 目录。"
        }

        $toolsDir = Join-Path $knowledgeSource "commands\tools"

        if (
            (Test-Path $toolsDir) -and
            -not (Test-Path $toolsDir -PathType Container)
        ) {
            throw "知识库 commands/tools 存在，但不是目录。"
        }

        $sourceFiles = @(
            Get-ChildItem $knowledgeSource -File -Recurse -Force
        )

        if ($sourceFiles.Count -eq 0) {
            throw "知识库没有任何文件。"
        }

        Write-Host "知识库版本：$knowledgeVersion"
        Write-Host "知识库文件数量：$($sourceFiles.Count)"

        Write-Host "`n========== 构建主程序 ==========" -ForegroundColor Cyan

        Push-Location $repoRoot

        try {
            & $python -m PyInstaller --clean --noconfirm $specFile

            if ($LASTEXITCODE -ne 0) {
                throw "PyInstaller 构建失败，退出代码：$LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }

        $distDir = Join-Path $repoRoot "dist\lcmd"

        if (-not (Test-Path (Join-Path $distDir "lcmd.exe") -PathType Leaf)) {
            throw "构建产物缺少 lcmd.exe。"
        }

        if (-not (Test-Path (Join-Path $distDir "_internal") -PathType Container)) {
            throw "构建产物缺少 _internal 目录。"
        }

        Write-Host "`n========== 生成发行目录 ==========" -ForegroundColor Cyan

        New-Item -ItemType Directory -Path $outputPath | Out-Null
        $outputCreated = $true

        $appDir = Join-Path $outputPath "app"
        $knowledgeDir = Join-Path $outputPath "knowledge"
        $installScriptTarget = Join-Path $outputPath "install.ps1"

        Copy-Item -Path $distDir -Destination $appDir -Recurse
        Copy-Item -Path $knowledgeSource -Destination $knowledgeDir -Recurse

        Write-Host "`n========== 复制并验证安装脚本 ==========" -ForegroundColor Cyan

        Copy-Item -LiteralPath $installScript -Destination $installScriptTarget

        if (-not (Test-Path $installScriptTarget -PathType Leaf)) {
            throw "发行包缺少 install.ps1。"
        }

        $sourceInstallHash = (Get-FileHash $installScript -Algorithm SHA256).Hash
        $targetInstallHash = (Get-FileHash $installScriptTarget -Algorithm SHA256).Hash

        if ($sourceInstallHash -ne $targetInstallHash) {
            throw "发行包 install.ps1 与源安装脚本 SHA-256 不一致。"
        }

        Write-Host "安装脚本复制及 SHA-256 校验通过。" -ForegroundColor Green
        Write-Host "安装脚本 SHA-256：$targetInstallHash"

        $copiedFiles = @(
            Get-ChildItem $knowledgeDir -File -Recurse -Force
        )

        if ($copiedFiles.Count -ne $sourceFiles.Count) {
            throw "知识库复制后文件数量不一致。"
        }

        Write-Host "`n========== 生成知识库完整性清单 ==========" -ForegroundColor Cyan

        $fileEntries = @(
            foreach ($file in ($copiedFiles | Sort-Object FullName)) {
                $relativePath = Get-RelativeFilePath -Root $knowledgeDir -File $file.FullName
                $hash = (Get-FileHash $file.FullName -Algorithm SHA256).Hash

                [PSCustomObject]@{
                    path   = $relativePath
                    size   = $file.Length
                    sha256 = $hash.ToLowerInvariant()
                }
            }
        )

        $integrity = [PSCustomObject]@{
            schema_version           = 1
            main_version             = $MainVersion
            main_prerelease          = $Prerelease
            knowledge_version        = $knowledgeVersion
            knowledge_archive_sha256 = $actualArchiveHash.ToLowerInvariant()
            file_count               = $fileEntries.Count
            files                    = $fileEntries
        }

        $integrityPath = Join-Path $outputPath "knowledge-integrity.json"

        $integrityJson = $integrity | ConvertTo-Json -Depth 8

        [System.IO.File]::WriteAllText(
            $integrityPath,
            $integrityJson,
            [System.Text.UTF8Encoding]::new($false)
        )

        Write-Host "`n========== 最终完整性复核 ==========" -ForegroundColor Cyan

        $savedIntegrity = Get-Content $integrityPath -Raw | ConvertFrom-Json

        foreach ($entry in $savedIntegrity.files) {
            $filePath = Join-Path $knowledgeDir ($entry.path.Replace('/', '\'))

            if (-not (Test-Path $filePath -PathType Leaf)) {
                throw "完整性复核失败，文件缺失：$($entry.path)"
            }

            $fileInfo = Get-Item $filePath
            $fileHash = (Get-FileHash $filePath -Algorithm SHA256).Hash

            if ($fileInfo.Length -ne $entry.size) {
                throw "文件大小校验失败：$($entry.path)"
            }

            if ($fileHash.ToLowerInvariant() -ne $entry.sha256) {
                throw "文件 SHA-256 校验失败：$($entry.path)"
            }
        }

        if ($savedIntegrity.file_count -ne $copiedFiles.Count) {
            throw "完整性清单文件数量不一致。"
        }

        $actualPaths = @(
            Get-ChildItem $knowledgeDir -File -Recurse -Force |
            ForEach-Object {
                Get-RelativeFilePath -Root $knowledgeDir -File $_.FullName
            } |
            Sort-Object
        )

        $manifestPaths = @(
            $savedIntegrity.files |
            ForEach-Object { $_.path } |
            Sort-Object
        )

        if (Compare-Object $actualPaths $manifestPaths) {
            throw "知识库实际文件集合与完整性清单不一致。"
        }

        Write-Host "知识库文件数量：$($savedIntegrity.file_count)"
        Write-Host "逐文件 SHA-256：全部通过" -ForegroundColor Green

        $buildSucceeded = $true

        Write-Host "`n发行暂存构建成功。" -ForegroundColor Green
        Write-Host "发行目录：$outputPath"
    }
    finally {
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force
        }
    }
}
catch {
    $failureMessage = $_.Exception.Message
}
finally {
    if ($outputCreated -and -not $buildSucceeded) {
        if (Test-Path $outputPath) {
            Remove-Item $outputPath -Recurse -Force
            Write-Host "已清理本次失败生成的发行目录。" -ForegroundColor Yellow
        }
    }
}

if ($failureMessage) {
    Write-Host "`n发行构建失败：$failureMessage" -ForegroundColor Red
    exit 1
}
