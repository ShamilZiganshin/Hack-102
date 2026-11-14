param([string]$RtxIP,[string]$WifiIP)
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if(!$RtxIP){$RtxIP=Read-Host 'Radmin IPv4 of RTX computer'}
if(!$WifiIP){
 Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.AddressState -eq 'Preferred'} | Format-Table InterfaceAlias,IPAddress
 $WifiIP=Read-Host 'IPv4 of THIS computer on the Wi-Fi used by the phone'
}
$nic=Get-NetIPAddress -AddressFamily IPv4 -IPAddress $WifiIP -ErrorAction Stop
$route=Find-NetRoute -RemoteIPAddress $RtxIP | Select-Object -First 1
if($route.InterfaceAlias -notmatch 'Radmin'){throw "Route to RTX uses $($route.InterfaceAlias). Check the RTX Radmin IP and VPN connection."}
Write-Host "Phone -> $WifiIP ($($nic.InterfaceAlias)) -> RTX $RtxIP ($($route.InterfaceAlias))"
$venv=Join-Path $PSScriptRoot 'radmin/.venv'
$python=Join-Path $venv 'Scripts/python.exe'
if(!(Test-Path $python)){py -3.11 -m venv $venv;if($LASTEXITCODE){throw 'Install Python 3.11 x64 with the py launcher'}}
& $python -c "import importlib.util as u,sys;sys.exit(not all(u.find_spec(k) for k in ('qrcode','PIL','cryptography')))"
if($LASTEXITCODE){& $python -m pip install qrcode pillow cryptography;if($LASTEXITCODE){throw 'Dependency installation failed'}}
& $python -u radmin_gateway.py $RtxIP $WifiIP
exit $LASTEXITCODE
