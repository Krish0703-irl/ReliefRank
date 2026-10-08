# run.py  (repo root) - open this file in VS Code and press Ctrl+F5.
# Starts the ReliefRank server and opens the page in your browser.

# ---- Settings (change these, no command-line arguments needed) ----
HOST = "127.0.0.1"
PORT = 8000
OPEN_BROWSER = True
# -------------------------------------------------------------------

import threading
import webbrowser

import uvicorn

from server.api import app

if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"ReliefRank running at {url}  (stop it with Shift+F5 in VS Code)")
    if OPEN_BROWSER:
        threading.Timer(1.5, webbrowser.open, args=[url]).start()
    uvicorn.run(app, host=HOST, port=PORT)