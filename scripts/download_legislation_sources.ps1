param(
    [string]$ManifestPath = "data/legislation/sources.json",
    [string]$OutputDir = "data/legislation"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$defaultHeaders = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
    "Accept-Language" = "pt-BR,pt;q=0.9,en;q=0.8"
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifesto não encontrado: $ManifestPath"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$results = @()

foreach ($entry in $manifest) {
    $targetPath = Join-Path $OutputDir $entry.filename
    Write-Host "Baixando $($entry.title) -> $targetPath"

    try {
        if ($entry.download_mode -eq "binary") {
            Invoke-WebRequest -Uri $entry.source_url -Headers $defaultHeaders -OutFile $targetPath
        }
        else {
            $response = Invoke-WebRequest -Uri $entry.source_url -Headers $defaultHeaders
            $content = @(
                "# $($entry.title)"
                ""
                "- Fonte: $($entry.source_url)"
                "- Capturado em: $(Get-Date -Format o)"
                "- Modo: $($entry.download_mode)"
                ""
                $response.Content
            )
            Set-Content -LiteralPath $targetPath -Value $content -Encoding UTF8
        }

        $item = Get-Item -LiteralPath $targetPath
        $results += [pscustomobject]@{
            filename = $entry.filename
            bytes = $item.Length
            source_url = $entry.source_url
            status = "ok"
        }
    }
    catch {
        $results += [pscustomobject]@{
            filename = $entry.filename
            bytes = 0
            source_url = $entry.source_url
            status = $_.Exception.Message
        }
    }
}

$results | Format-Table -AutoSize
