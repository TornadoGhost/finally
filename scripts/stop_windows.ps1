$ErrorActionPreference = 'Stop'

docker stop finally 2>$null | Out-Null
docker rm finally 2>$null | Out-Null

Write-Host "FinAlly stopped (data persists in 'finally-data' volume)"
