"""Entry point to launch the JobFlow-AI Career CRM Dashboard.

Run:
    python run_dashboard.py

Then open your browser at:
    http://localhost:8000
"""

import uvicorn


def main():
    print("=" * 70)
    print("🚀 Launching JobFlow-AI Career CRM Dashboard...")
    print("👉 Open your browser at: http://localhost:8000")
    print("=" * 70)
    uvicorn.run("src.server.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
