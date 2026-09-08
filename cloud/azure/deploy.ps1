param(
    [string]$ResourceGroup = "opamp-regression-rg",
    [string]$Location = "uksouth",
    [string]$ParametersFile = "cloud/azure/parameters.example.json",
    [string]$TemplateFile = "cloud/azure/mainTemplate.json"
)

$ErrorActionPreference = "Stop"

az group create --name $ResourceGroup --location $Location | Out-Host
az deployment group create `
    --resource-group $ResourceGroup `
    --template-file $TemplateFile `
    --parameters "@$ParametersFile" | Out-Host
