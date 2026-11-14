$ErrorActionPreference='Stop'
# Only this local demonstration, only local-subnet clients, no database access.
foreach ($port in @(8769,8443)) {
    $name="Kiber102-Mobile-$port"
    if (-not (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name $name -DisplayName "Kiber102 mobile inspection TCP $port (LAN only)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -RemoteAddress LocalSubnet -Profile Any -ErrorAction Stop | Out-Null
    }
}
$rules=Get-NetFirewallRule -Name 'Kiber102-Mobile-8769','Kiber102-Mobile-8443' -ErrorAction Stop
if (@($rules).Count -ne 2) { throw 'Both firewall rules were not verified.' }
$rules | Select-Object Name,Enabled,Direction,Action | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'outputs\firewall_verified.json') -Encoding UTF8
Write-Host 'LAN HTTP/HTTPS allowed. PostgreSQL remains loopback-only.'
