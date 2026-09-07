param(
    [string]$ResourceGroup = "opamp-regression-rg",
    [switch]$Wait
)

$ErrorActionPreference = "Stop"

if ($Wait) {
    az group delete --name $ResourceGroup --yes | Out-Host
} else {
    az group delete --name $ResourceGroup --yes --no-wait | Out-Host
}
