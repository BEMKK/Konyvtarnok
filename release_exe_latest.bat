@echo off
for /f "tokens=*" %%i in ('gh release view --repo bemkk/konyvtarnok --json tagName -q .tagName') do set LATEST_TAG=%%i

if defined LATEST_TAG (
    echo Legfrissebb release: %LATEST_TAG%
    gh release upload %LATEST_TAG% "konyvtarnok.exe" --repo bemkk/konyvtarnok --clobber
) else (
    echo Nem sikerült lekérni a legfrissebb release tag-jét.
)

pause