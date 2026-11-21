@echo off
pyinstaller --noconsole --onefile --icon="ikon.ico" --add-data "ikon.ico;." --add-data "license.txt;." --name="konyvtarnok" main.py
pause