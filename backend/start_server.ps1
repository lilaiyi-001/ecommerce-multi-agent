# 在沙箱外启动 Uvicorn 服务器
$env:PYTHONPATH = "D:\电商选品2\backend\lib;D:\电商选品2\backend"
Start-Process -WindowStyle Hidden -FilePath "D:\Anaconda\python.exe" 
    -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8085 --log-level info" 
    -WorkingDirectory "D:\电商选品2\backend" 
    -RedirectStandardOutput "D:\电商选品2\backend\server_stdout.log" 
    -RedirectStandardError "D:\电商选品2\backend\server_stderr.log"
Write-Output "Server starting on port 8085 (PID unknown - started as background process)"
