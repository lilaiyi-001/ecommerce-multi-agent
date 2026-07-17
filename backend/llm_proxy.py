"""LLM API 代理脚本 - 在沙箱外运行以绕过网络限制

用法：D:\Anaconda\python.exe llm_proxy.py <api_key> <base_url> <model> <system_prompt> <user_message>
输出：JSON 格式 { "success": true, "content": "..." } 或 { "success": false, "error": "..." }
"""
import sys
import json
import os

# 添加 lib 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

try:
    from openai import OpenAI

    api_key = sys.argv[1]
    base_url = sys.argv[2]
    model = sys.argv[3]
    system_prompt = sys.argv[4]
    user_message = sys.argv[5]

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    content = resp.choices[0].message.content or ""
    print(json.dumps({"success": True, "content": content}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
