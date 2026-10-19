# Run from repository root. Captures exit codes and full output without suppressing failures.
$ErrorActionPreference = 'Continue'
$checks = @(
  @{ Name = 'ts18_specific'; Args = @('-m','pytest','-ra','tests/test_ts_18_6_football_regression_stress.py','tests/test_ts_18_6_spatial_seeded_regression.py') },
  @{ Name = 'complete_regression'; Args = @('-m','pytest','-ra') },
  @{ Name = 'seasons_and_persistence'; Args = @('-m','pytest','-ra','tests/test_phase6_7_full_season_integration.py','tests/test_ts_17_1_multiseason_scheduling.py','tests/test_ts_17_4_long_career_persistence.py') }
)
foreach ($check in $checks) {
  Write-Host "Running $($check.Name)"
  & python @($check.Args) 2>&1 | Tee-Object -FilePath "TS_18_6_$($check.Name).log"
  $code = $LASTEXITCODE
  Write-Host "$($check.Name) exit code: $code"
  if ($code -ne 0) { Write-Warning "$($check.Name) did not pass. Check log." }
}
