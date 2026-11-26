# Build and run the host-side test for UNO_Node v1.2.
# Sources are copied to an ASCII temp directory first, because g++ cannot
# resolve #include paths that contain non-ASCII characters.

$ErrorActionPreference = 'Stop'

$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$inoDir = Join-Path (Split-Path -Parent $here) 'UNO_Node'
$ino    = Join-Path $inoDir 'UNO_Node.ino'

if (-not (Test-Path $ino)) { throw "UNO_Node.ino not found: $ino" }

$stage = Join-Path $env:TEMP 'uno_node_v12_test'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

Copy-Item (Join-Path $here 'stubs') $stage -Recurse
Copy-Item (Join-Path $here 'parse_test.cpp') (Join-Path $stage 'test.cpp')
Copy-Item $ino $stage

$gpp = (Get-Command g++ -ErrorAction SilentlyContinue).Source
if (-not $gpp) {
  foreach ($c in @('C:\opt\w64devkit\bin\g++.exe')) {
    if (Test-Path $c) { $gpp = $c; break }
  }
}
if (-not $gpp) { throw 'g++ not found. Install w64devkit / MinGW and add it to PATH.' }

& $gpp -std=gnu++11 -Wall -Wextra -Wno-unused-parameter -I (Join-Path $stage 'stubs') (Join-Path $stage 'test.cpp') -o (Join-Path $stage 'test.exe')
if ($LASTEXITCODE -ne 0) { throw "compile failed (exit $LASTEXITCODE)" }

& (Join-Path $stage 'test.exe')
exit $LASTEXITCODE
