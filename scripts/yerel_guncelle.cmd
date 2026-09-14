@echo off
REM TBF verisini bu bilgisayardan ceker ve repoya gonderir (Windows).
cd /d "%~dp0.."
echo TBF verisi cekiliyor...
python scripts\tbf_sync.py %*
if errorlevel 1 goto :son

git diff --quiet -- data/league.json
if %errorlevel%==0 (
  echo Degisiklik yok.
  goto :son
)

git add data/league.json
git commit -m "TBF verisi guncellendi"
git push
echo Gonderildi.

:son
pause
