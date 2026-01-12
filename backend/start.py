#!/usr/bin/env python3
"""
Startup script for the AI Smart Receptionist backend.
This script ensures the application runs correctly in all environments.
"""
import os
import uvicorn
from main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
