"""
Start ReliefRank: press Ctrl+F5 on this file.
Creates the database, starts the web server and opens the browser.
"""
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from reliefrank import store


def main():
    store.init_db()
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed. Run: pip install -r requirements.txt")
        return
    try:
        from server.api import app
    except Exception as e:
        print(f"Could not load server/api.py: {e}")
        return

    url = f"http://{config.HOST}:{config.PORT}"
    print(f"ReliefRank running at {url}  (backend: {config.BACKEND}, pack: {config.ACTIVE_PACK})")
    if config.OPEN_BROWSER:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
