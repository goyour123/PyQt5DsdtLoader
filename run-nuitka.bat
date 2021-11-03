@set SCRIPT_NAME=PyQt5DsdtLoader
@set CFG_NAME=wal

python -m nuitka --mingw64 --standalone --plugin-enable=qt-plugins %SCRIPT_NAME%.py

@REM Copy configuration file to executable distribution
@if exist %CFG_NAME%.json (
  @if exist %SCRIPT_NAME%.dist (
    copy %CFG_NAME%.json %SCRIPT_NAME%.dist
  )
)

@REM Copy debug file to dist
@set DEBUG_SCRIPT=*.asi
@if exist %SCRIPT_NAME%.dist (
  copy %DEBUG_SCRIPT% %SCRIPT_NAME%.dist
)


@REM Copy third party tool to dist
@set ASL_EXE=asl.exe
@set IASL_EXE=iasl.exe
@if exist %SCRIPT_NAME%.dist (
  @if exist %ASL_EXE% (
    copy %ASL_EXE% %SCRIPT_NAME%.dist
  )
  @if exist %IASL_EXE% (
    copy %IASL_EXE% %SCRIPT_NAME%.dist
  )
)
