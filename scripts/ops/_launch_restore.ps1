$ErrorActionPreference = "Stop"
Set-Location "d:\muhimu\muhimu ERP"

$utf8 = New-Object System.Text.UTF8Encoding $false
foreach ($f in @(
  "scripts\ops\restore_drill.sh",
  "scripts\ops\lib_common.sh",
  "scripts\ops\validate_restored.sql",
  "scripts\ops\set_restore_role_passwords.py"
)) {
  if (Test-Path $f) {
    $t = [IO.File]::ReadAllText((Resolve-Path $f)) -replace "`r`n", "`n" -replace "`r", "`n"
    [IO.File]::WriteAllText((Resolve-Path $f), $t, $utf8)
  }
}

$env:OPS_RESTORE_PG_PASSWORD = "ops_restore_temp_lab_only"
$env:OPS_RESTORE_APP_PASSWORD = "OpsRestoreApp_" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$env:OPS_RESTORE_PLATFORM_PASSWORD = "OpsRestorePlat_" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$env:OPS_RESTORE_PG_PORT = "5439"
$env:DUMP = "backups/postgres/muhimu_dev_20261010_044901.dump"
$env:ROLES = "backups/postgres/muhimu_dev_20261010_044901_roles.sql"
$env:MSYS_NO_PATHCONV = "1"

$sw = [Diagnostics.Stopwatch]::StartNew()
& "C:\Program Files\Git\bin\bash.exe" "scripts/ops/restore_drill.sh"
$code = $LASTEXITCODE
Write-Host "RESTORE_EXIT=$code elapsed_s=$([int]$sw.Elapsed.TotalSeconds)"

Remove-Item Env:OPS_RESTORE_PG_PASSWORD, Env:OPS_RESTORE_APP_PASSWORD, Env:OPS_RESTORE_PLATFORM_PASSWORD -ErrorAction SilentlyContinue
exit $code
