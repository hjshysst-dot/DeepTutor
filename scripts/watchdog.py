#!/usr/bin/env python3
"""
DeepTutor Watchdog - Keeps backend and frontend running
Auto-restarts if services crash
"""

import os
import sys
import time
import signal
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/tmp/deeptutor_watchdog.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("watchdog")

PROJECT_DIR = "/Volumes/ORICO/DeepTutor"
BACKEND_PORT = 8001
FRONTEND_PORT = 3782
CHECK_INTERVAL = 30  # seconds


def is_port_open(port):
    """Check if a port is listening."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}"],
            capture_output=True,
            text=True,
        )
        return "LISTEN" in result.stdout
    except Exception:
        return False


def start_backend():
    """Start the DeepTutor backend."""
    logger.info("Starting backend...")
    os.chdir(PROJECT_DIR)
    env = os.environ.copy()
    # Clear any conflicting proxy settings
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    
    with open("/tmp/deeptutor_backend.log", "w") as f:
        subprocess.Popen(
            ["/opt/homebrew/bin/python3.11", "-m", "deeptutor.api.run_server"],
            cwd=PROJECT_DIR,
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    time.sleep(3)


def start_frontend():
    """Start the Next.js frontend."""
    logger.info("Starting frontend...")
    os.chdir(f"{PROJECT_DIR}/web")
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_BASE"] = "http://localhost:8001"
    env["PORT"] = str(FRONTEND_PORT)
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    
    with open("/tmp/deeptutor_frontend.log", "w") as f:
        subprocess.Popen(
            ["node", ".next/standalone/server.js", "-p", str(FRONTEND_PORT)],
            cwd=f"{PROJECT_DIR}/web",
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
        )
    time.sleep(3)


def stop_process_on_port(port):
    """Kill process using a specific port."""
    try:
        result = subprocess.run(
            ["lsof", "-t", "-i", f":{port}"],
            capture_output=True,
            text=True,
        )
        for pid in result.stdout.strip().split("\n"):
            if pid:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    logger.info(f"Killed process {pid} on port {port}")
                except ProcessLookupError:
                    pass
    except Exception as e:
        logger.warning(f"Error stopping port {port}: {e}")


def check_and_restart():
    """Check services and restart if needed."""
    backend_ok = is_port_open(BACKEND_PORT)
    frontend_ok = is_port_open(FRONTEND_PORT)

    if not backend_ok:
        logger.warning(f"Backend port {BACKEND_PORT} not listening!")
        stop_process_on_port(BACKEND_PORT)
        start_backend()
    else:
        logger.info(f"Backend OK (port {BACKEND_PORT})")

    if not frontend_ok:
        logger.warning(f"Frontend port {FRONTEND_PORT} not listening!")
        stop_process_on_port(FRONTEND_PORT)
        start_frontend()
    else:
        logger.info(f"Frontend OK (port {FRONTEND_PORT})")


def main():
    logger.info("DeepTutor Watchdog started")
    logger.info(f"Checking every {CHECK_INTERVAL} seconds...")

    # Start services on launch
    check_and_restart()

    while True:
        try:
            check_and_restart()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Watchdog stopped by user")
            break
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
