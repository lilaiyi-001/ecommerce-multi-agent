@echo off
set PYTHONPATH=D:\电商选品2\backend\lib;D:\电商选品2\backend
D:\Anaconda\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8085 --log-level info
