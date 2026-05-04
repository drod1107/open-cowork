"""Server harness for backend tests - starts/stops the real server."""
import subprocess
import time
import socket
from pathlib import Path

SERVER_PROCESS = None
SERVER_READY = False
SERVER_URL = "http://localhost:7337"
MAX_WAIT = 10  # seconds


def _is_port_open(host: str, port: int) -> bool:
    """Check if port is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout):
            return False


def start_server():
    """Start the backend server in a subprocess."""
    global SERVER_PROCESS, SERVER_READY
    
    if SERVER_PROCESS:
        return
    
    # Start server using the venv python from repo root
    repo_root = Path(__file__).parent.parent  # backend/.. = repo root
    
    # Try multiple python paths
    python_paths = [
        repo_root / ".venv" / "bin" / "python3",
        Path("/usr/bin/python3.12"),
        Path("/usr/bin/python3"),
    ]
    
    venv_python = None
    for p in python_paths:
        if p.exists():
            venv_python = p
            break
    
    if not venv_python:
        raise FileNotFoundError(f"Python not found in: {[str(p) for p in python_paths]}")
    
    SERVER_PROCESS = subprocess.Popen(
        [str(venv_python), "-m", "backend.main"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to be ready
    for _ in range(MAX_WAIT * 2):  # Check every 0.5s
        if _is_port_open("localhost", 7337):
            SERVER_READY = True
            return
        time.sleep(0.5)
    
    raise TimeoutError(f"Server failed to start within {MAX_WAIT}s")


def stop_server():
    """Stop the backend server."""
    global SERVER_PROCESS, SERVER_READY
    
    if not SERVER_PROCESS:
        return
    
    SERVER_PROCESS.terminate()
    try:
        SERVER_PROCESS.wait(timeout=5)
    except subprocess.TimeoutExpired:
        SERVER_PROCESS.kill()
    
    SERVER_PROCESS = None
    SERVER_READY = False


def is_server_ready() -> bool:
    """Check if server is ready."""
    return SERVER_READY


def get_server_url() -> str:
    """Get the server URL."""
    return SERVER_URL
