param(
  [string]$Destination = "$PSScriptRoot\..\dictionary-data"
)

$ErrorActionPreference = 'Stop'
$ecdictCommit = 'bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b'
$directory = New-Item -ItemType Directory -Force -Path $Destination
$ecdict = Join-Path $directory.FullName 'ecdict.csv'
$cedict = Join-Path $directory.FullName 'cedict_1_0_ts_utf-8_mdbg.txt.gz'
$output = Join-Path $directory.FullName 'local-dictionary.sqlite3'

Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/skywind3000/ECDICT/$ecdictCommit/ecdict.csv" -OutFile $ecdict
Invoke-WebRequest -UseBasicParsing -Uri 'https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz' -OutFile $cedict

$ecdictHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ecdict).Hash.ToLowerInvariant()
$cedictHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cedict).Hash.ToLowerInvariant()
$version = "ecdict-$($ecdictCommit.Substring(0,12))_cedict-$($cedictHash.Substring(0,12))"

python "$PSScriptRoot\build_local_dictionary.py" --ecdict $ecdict --cedict $cedict --output $output --version $version
Set-Content -Encoding ascii -LiteralPath (Join-Path $directory.FullName 'SHA256SUMS') -Value @(
  "$ecdictHash  ecdict.csv"
  "$cedictHash  cedict_1_0_ts_utf-8_mdbg.txt.gz"
  "$((Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash.ToLowerInvariant())  local-dictionary.sqlite3"
)
