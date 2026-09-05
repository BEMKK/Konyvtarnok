@echo off
pyinstaller --noconsole --onefile --icon="ikon.ico" --add-data "ikon.ico;." --add-data "Enekeskonyvek_adatai.json;." --name="konyvtarnok" main.py
pause