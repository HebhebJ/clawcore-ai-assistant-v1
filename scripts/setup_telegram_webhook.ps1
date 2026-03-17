param(
    [Parameter(Mandatory = $true)]
    [string]$PublicBaseUrl
)

$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envPath)) {
    throw ".env not found at $envPath"
}

$vars = @{}
Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
        return
    }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim()
    $vars[$key] = $value
}

$token = "$($vars["TELEGRAM_BOT_TOKEN"])".Trim()
$secret = "$($vars["TELEGRAM_WEBHOOK_SECRET"])".Trim()
if (-not $token) {
    throw "TELEGRAM_BOT_TOKEN is missing in .env"
}
if (-not $secret) {
    throw "TELEGRAM_WEBHOOK_SECRET is missing in .env"
}

$base = $PublicBaseUrl.Trim().TrimEnd("/")
$webhookUrl = "$base/webhook/telegram"
$apiUrl = "https://api.telegram.org/bot$token/setWebhook"

$body = @{
    url = $webhookUrl
    secret_token = $secret
}

$response = Invoke-RestMethod -Uri $apiUrl -Method Post -Body $body -ContentType "application/x-www-form-urlencoded"
$response | ConvertTo-Json -Depth 8
