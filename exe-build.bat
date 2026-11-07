@echo off
pyinstaller --noconsole --onefile --icon="ikon.ico" --add-data "ikon.ico;." --name="konyvtarnok" main.py
pause