@echo off
set PYTHONPATH=D:\电商选品2\backend\lib;D:\电商选品2\backend
start /B /MIN D:\Anaconda\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8085 --log-level info > D:\电商选品2\backend\server_out.log 2>&1
echo Server started on port 8085
echo PID: %ERRORLEVEL%

