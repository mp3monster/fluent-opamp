$ErrorActionPreference = "Stop"

$CliRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CliEntry = (Resolve-Path (Join-Path $CliRoot "main.py")).Path

if (-not (Test-Path $CliEntry)) {
    throw "Could not find CLI entrypoint: $CliEntry"
}

$BlockStart = "# >>> opamp-cli aliases >>>"
$BlockEnd = "# <<< opamp-cli aliases <<<"
$AliasBlock = @(
    $BlockStart
    '$script:OpampCliEntry = ''' + $CliEntry.Replace("'", "''") + ''''
    'function opamp-cli {'
    '  & python $script:OpampCliEntry @args'
    '}'
    'function opamp {'
    '  & python $script:OpampCliEntry @args'
    '}'
    $BlockEnd
    ''
) -join "`r`n"

$ProfilePaths = @()
$ProfilePaths += $PROFILE
if ($PROFILE -notlike "*WindowsPowerShell*") {
    $Legacy = Join-Path $HOME "Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"
    $ProfilePaths += $Legacy
}

foreach ($ProfilePath in ($ProfilePaths | Select-Object -Unique)) {
    $ProfileDir = Split-Path -Parent $ProfilePath
    if (-not (Test-Path $ProfileDir)) {
        New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
    }
    if (-not (Test-Path $ProfilePath)) {
        Set-Content -Path $ProfilePath -Value $AliasBlock -Encoding UTF8
        Write-Host "Created profile aliases in: $ProfilePath"
        continue
    }

    $Existing = Get-Content -Path $ProfilePath -Raw -Encoding UTF8
    $StartIndex = $Existing.IndexOf($BlockStart)
    $EndIndex = $Existing.IndexOf($BlockEnd)
    if ($StartIndex -ge 0 -and $EndIndex -gt $StartIndex) {
        $EndIndex += $BlockEnd.Length
        $Updated = $Existing.Substring(0, $StartIndex) + $AliasBlock + $Existing.Substring($EndIndex)
    } else {
        if ($Existing.Length -gt 0 -and -not $Existing.EndsWith("`n")) {
            $Existing += "`r`n"
        }
        $Updated = $Existing + $AliasBlock
    }
    Set-Content -Path $ProfilePath -Value $Updated -Encoding UTF8
    Write-Host "Updated profile aliases in: $ProfilePath"
}

Write-Host "Done. Open a new PowerShell session, or run: . `$PROFILE"
