$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Build if needed or if -Build flag passed
$shouldBuild = $args -contains "-Build" -or -not (docker image inspect finally -q 2>$null)
if ($shouldBuild) {
    Write-Host "Building Docker image..."
    docker build -t finally $projectRoot
}

# Stop existing container if running
docker stop finally 2>$null | Out-Null
docker rm finally 2>$null | Out-Null

# Start container
docker run -d `
  --name finally `
  -v finally-data:/app/db `
  -p 8000:8000 `
  --env-file "$projectRoot\.env" `
  finally

Write-Host "FinAlly is running at http://localhost:8000"
