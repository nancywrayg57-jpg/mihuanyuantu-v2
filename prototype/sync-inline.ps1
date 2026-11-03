$ErrorActionPreference = 'Stop'
$jsPath = Join-Path $PSScriptRoot 'prototype.js'
$htmlPath = Join-Path $PSScriptRoot 'index.html'
$js = Get-Content -Raw -Path $jsPath
$html = Get-Content -Raw -Path $htmlPath
$pattern = '(?s)(<script>\r?\n)(.*?)(\r?\n\s*</script>\s*</body>)'
if ($html -notmatch $pattern) {
  Write-Error 'inline script block not found in index.html'
  exit 1
}
$newHtml = [regex]::Replace($html, $pattern, { param($m) $m.Groups[1].Value + $js.TrimEnd() + $m.Groups[3].Value }, 1)
[System.IO.File]::WriteAllText($htmlPath, $newHtml)
Write-Output 'synced'
Write-Output ("prototype.js bytes=" + (Get-Item $jsPath).Length)
Write-Output ("index.html bytes=" + (Get-Item $htmlPath).Length)
