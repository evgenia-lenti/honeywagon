@echo off
rem Runs the Honeywagon core with the arguments it is given, on Windows
rem without a Unix shell. It does the same as the script next to it: it finds
rem the core, first as the honeywagon command and then as a module of a Python
rem on this computer. It installs nothing and it changes nothing.

where honeywagon >nul 2>nul
if not errorlevel 1 (
  honeywagon %*
  exit /b
)

py -3 -c "import honeywagon" >nul 2>nul
if not errorlevel 1 (
  py -3 -m honeywagon %*
  exit /b
)

python -c "import honeywagon" >nul 2>nul
if not errorlevel 1 (
  python -m honeywagon %*
  exit /b
)

echo The Honeywagon core is not installed on this computer. 1>&2
echo Install it once and run the audit again. The steps are at 1>&2
echo https://github.com/evgenia-lenti/honeywagon/tree/main/runners/claude_code 1>&2
exit /b 3
