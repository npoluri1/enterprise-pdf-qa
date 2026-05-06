# Keep llama3.2:3b loaded in memory permanently
# This pings Ollama every 3 minutes so it never unloads the model
while ($true) {
    $body = '{"model":"llama3.2:3b","prompt":"hi","stream":false,"keep_alive":"10m"}'
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" `
            -Method Post `
            -Body $body `
            -ContentType "application/json" | Out-Null
        Write-Host "$(Get-Date -Format 'HH:mm:ss') model kept warm"
    } catch {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') warmup failed - is Ollama running?"
    }
    Start-Sleep -Seconds 180
}