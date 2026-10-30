<#
.SYNOPSIS
  Deploy do PetGo na AWS com um unico comando (CloudFormation).

.DESCRIPTION
  Cria/atualiza o stack CloudFormation que provisiona a EC2 Windows, instala
  tudo e sobe a aplicacao. Ao final imprime a URL de acesso.

.EXAMPLE
  .\deploy.ps1
  .\deploy.ps1 -StackName petgo -Region us-east-1 -AllowedCidr 0.0.0.0/0
#>
param(
  [string]$StackName  = "petgo",
  [string]$Region     = "us-east-1",
  [string]$RepoUrl    = "https://github.com/willian-J-A/petgo.git",
  [string]$RepoBranch = "main",
  [string]$AppSubdir  = "petgo",
  [int]   $AppPort    = 8080,
  [string]$InstanceType = "t3.small",
  [string]$AllowedCidr  = "0.0.0.0/0",
  [string]$EnableRdp    = "false",
  [string]$KeyName      = ""
)

$ErrorActionPreference = "Stop"
$template = Join-Path $PSScriptRoot "petgo-cfn.yaml"

Write-Host "==> Validando template" -ForegroundColor Cyan
aws cloudformation validate-template --template-body "file://$template" --region $Region | Out-Null

Write-Host "==> Fazendo deploy do stack '$StackName' em $Region (pode levar ~10-15 min)" -ForegroundColor Cyan
aws cloudformation deploy `
  --stack-name $StackName `
  --template-file $template `
  --region $Region `
  --no-fail-on-empty-changeset `
  --parameter-overrides `
    RepoUrl=$RepoUrl `
    RepoBranch=$RepoBranch `
    AppSubdir=$AppSubdir `
    AppPort=$AppPort `
    InstanceType=$InstanceType `
    AllowedCidr=$AllowedCidr `
    EnableRdp=$EnableRdp `
    KeyName=$KeyName

if ($LASTEXITCODE -ne 0) { throw "Falha no deploy do CloudFormation." }

Write-Host "`n==> Deploy concluido. Links:" -ForegroundColor Green
$outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region `
  --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
foreach ($o in $outputs) {
  Write-Host ("  {0,-12} {1}" -f $o.OutputKey, $o.OutputValue)
}
$url = ($outputs | Where-Object { $_.OutputKey -eq "AccessUrl" }).OutputValue
Write-Host "`nAcesse: $url" -ForegroundColor Yellow
