#!/usr/bin/env python3
"""
AI Chat Launcher
Chạy cả backend API và phục vụ frontend static
"""
import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

def main():
    print("🚀 AI Chat Backend starting...")
    print(f"   URL: http://{HOST}:{PORT}")
    print(f"   API: http://{HOST}:{PORT}/api/chat")
    print(f"   Models: http://{HOST}:{PORT}/api/models")
    print("   Press Ctrl+C to stop\n")

    uvicorn.run(
        "backend:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Shutdown complete")
        sys.exit(0)
