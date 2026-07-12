# AgentCron verification
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python -m unittest discover -s tests -v
python -m agentcron --version
python -m agentcron --config examples\agentcron.json status
python -m agentcron --config examples\agentcron.json install --all --dry-run
Write-Host "AgentCron verification passed." -ForegroundColor Green
