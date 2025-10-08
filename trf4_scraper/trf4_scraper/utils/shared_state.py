import os
import sys
import json
import time
from pathlib import Path

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

class FileLock:
    def __init__(self, lock_file):
        self.lock_file = lock_file
        self.fh = None

    def __enter__(self):
        self.fh = open(self.lock_file, 'a+')
        if os.name == 'nt':
            while True:
                try:
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            while True:
                try:
                    fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(0.05)
        return self.fh

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fh:
            if os.name == 'nt':
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.fh, fcntl.LOCK_UN)
            self.fh.close()


def read_state(state_path):
    state_path = Path(state_path)
    if not state_path.exists():
        return {"current_page_number": 1, "done": False}
    with open(state_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_state(state_path, data):
    state_path = Path(state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

def get_and_increment_page(state_path, lock_path):
    state_path = Path(state_path)
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path):
        state = read_state(state_path)
        if state.get('done'):
            return None
        page = state.get('current_page_number', 1)
        state['current_page_number'] = page + 1
        write_state(state_path, state)
        return page

def mark_done(state_path, lock_path):
    state_path = Path(state_path)
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path):
        state = read_state(state_path)
        state['done'] = True
        write_state(state_path, state)
