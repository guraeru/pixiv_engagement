@echo off

:: conda環境をアクティブにする
call "%USERPROFILE%\anaconda3\condabin\conda.bat" activate Test001

:: スクリプトを実行
python pixiv_gui_app.py

pause