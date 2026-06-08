#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           ⚗️ DENIA PHARMACIST ⚗️                              ║
║     Advanced Medicinal Chemistry Research Bot                 ║
║     Model: mistral-medium-3.5-128b                            ║
║     Architecture: Async | Long-running | No Timeout             ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python run.py
"""

import sys
import os

# Ensure bot package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.main import main

if __name__ == "__main__":
    print("🔬 Initializing Denia Pharmacist...")
    print("⚗️ Loading pharmaceutical chemistry knowledge base...")
    print("🧪 Calibrating AI client (mistral-medium-3.5-128b)...")
    print("📡 Connecting to Telegram API...")
    print("✅ All systems nominal. Starting bot.\n")
    
    main()
