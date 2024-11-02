import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

class RestartHandler(FileSystemEventHandler):
    def __init__(self, script):
        self.script = script
        self.process = None
        self.start_bot()

    def start_bot(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait()
        self.process = subprocess.Popen([sys.executable, self.script])

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print(f"Detected change in {event.src_path}, restarting...")
            self.start_bot()

if __name__ == "__main__":
    script = "bot.py"  # Replace with your main bot script name
    event_handler = RestartHandler(script)
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=False)

    try:
        observer.start()
        print("Watching for changes... Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
