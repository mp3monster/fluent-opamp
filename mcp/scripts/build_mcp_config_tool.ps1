param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $BuildArgs
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$McpDir = Split-Path -Parent $ScriptDir
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$env:PYTHONPATH = if ($env:PYTHONPATH) {
    (Join-Path $McpDir "src") + [IO.Path]::PathSeparator + $env:PYTHONPATH
} else {
    (Join-Path $McpDir "src")
}

& $PythonBin -m opamp_mcp_config.build_tool @BuildArgs
exit $LASTEXITCODE
