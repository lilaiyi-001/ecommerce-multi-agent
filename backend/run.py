"""启动脚本 - 确保 lib 目录在 sys.path 中"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8085,
        reload=False,
        log_level="info",
    )
