import os
import sys
import time
import gc
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess

# Memory management for Railway
def log_memory_usage(context=""):
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"[MEMORY] {context}: {memory_mb:.1f}MB")
        return memory_mb
    except:
        return 0

class RestartHandler(FileSystemEventHandler):
    def __init__(self, script):
        self.script = script
        self.process = None
        self.start_bot()

    def start_bot(self):
        # Cleanup before starting
        gc.collect()
        log_memory_usage("Before bot start")
        
        if self.process is not None:
            self.process.terminate()
            self.process.wait()
            gc.collect()
            log_memory_usage("After terminating previous process")
        
        # Set memory-related environment variables
        env = os.environ.copy()
        env['PYTHONOPTIMIZE'] = '1'  # Optimize Python
        env['MALLOC_TRIM_THRESHOLD_'] = '65536'  # More aggressive memory release
        
        self.process = subprocess.Popen([sys.executable, self.script], env=env)
        log_memory_usage("After starting bot process")

    def on_modified(self, event):
        if event.src_path.endswith("bot.py"):
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
