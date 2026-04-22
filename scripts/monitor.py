#!/usr/bin/env python3
"""
DeepTutor Monitor Dashboard
==========================
Real-time monitoring of DeepTutor services with diagnostics.
"""

import http.server
import json
import os
import psutil
import socket
import subprocess
import threading
import time
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monitor")

PORT = 3783
PROJECT_DIR = Path("/Volumes/ORICO/DeepTutor")
BACKEND_PORT = 8010
FRONTEND_PORT = 3782

class HealthChecker:
    def __init__(self):
        self.last_check = {}
        self.history = []
    
    def check_port(self, port):
        """Check if a port is listening."""
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True, text=True
            )
            is_listening = "LISTEN" in result.stdout
            # Also check if it's a Python/Node process
            processes = []
            for line in result.stdout.strip().split("\n")[1:]:
                if f":{port}" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        processes.append({"pid": parts[1], "name": parts[0]})
            return {"port": port, "listening": is_listening, "processes": processes}
        except Exception as e:
            return {"port": port, "listening": False, "error": str(e)}
    
    def check_backend_api(self):
        """Test backend API response."""
        try:
            start = time.time()
            result = subprocess.run(
                ["curl", "-s", "--max-time", "3", f"http://localhost:{BACKEND_PORT}/"],
                capture_output=True, text=True
            )
            latency = (time.time() - start) * 1000
            success = "DeepTutor" in result.stdout or result.returncode == 0
            return {
                "success": success,
                "latency_ms": round(latency, 1),
                "response": result.stdout[:100] if result.stdout else ""
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_llm_api(self):
        """Test LLM API with a simple request."""
        try:
            api_key = os.getenv("LLM_API_KEY", "")
            if not api_key:
                api_key = subprocess.run(
                    ["grep", "LLM_API_KEY", f"{PROJECT_DIR}/.env"],
                    capture_output=True, text=True
                ).stdout.split("=")[1].strip() if "=" in subprocess.run(
                    ["grep", "LLM_API_KEY", f"{PROJECT_DIR}/.env"],
                    capture_output=True, text=True
                ).stdout else ""
            
            host = os.getenv("LLM_HOST", "https://api.minimaxi.com/v1")
            
            start = time.time()
            result = subprocess.run([
                "curl", "-s", "--max-time", "10",
                "-X", "POST",
                f"{host}/chat/completions",
                "-H", f"Authorization: Bearer {api_key}",
                "-H", "Content-Type: application/json",
                "-d", '{"model":"MiniMax-M2.7","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
            ], capture_output=True, text=True, timeout=15)
            latency = (time.time() - start) * 1000
            
            if result.stdout:
                data = json.loads(result.stdout)
                if "choices" in data:
                    return {"success": True, "latency_ms": round(latency, 1), "model": data.get("model", "unknown")}
                elif "error" in data:
                    return {"success": False, "error": data["error"].get("message", str(data["error"]))}
            
            return {"success": False, "error": "Unknown response", "raw": result.stdout[:200]}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Request timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_disk_space(self):
        """Check disk space for ORICO volume."""
        try:
            volume = Path("/Volumes/ORICO")
            if volume.exists():
                stat = psutil.disk_usage(str(volume))
                return {
                    "total_gb": round(stat.total / (1024**3), 1),
                    "used_gb": round(stat.used / (1024**3), 1),
                    "free_gb": round(stat.free / (1024**3), 1),
                    "percent": stat.percent
                }
            return {"error": "ORICO volume not found"}
        except Exception as e:
            return {"error": str(e)}
    
    def check_memory(self):
        """Check system memory."""
        try:
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 1),
                "used_gb": round(mem.used / (1024**3), 1),
                "free_gb": round(mem.available / (1024**3), 1),
                "percent": mem.percent
            }
        except Exception as e:
            return {"error": str(e)}
    
    def check_log_errors(self, log_path, lines=50):
        """Check for recent errors in log file."""
        try:
            if Path(log_path).exists():
                with open(log_path) as f:
                    content = f.read()
                log_lines = content.strip().split("\n")[-lines:]
                errors = []
                warnings = []
                for line in log_lines:
                    line_lower = line.lower()
                    if "error" in line_lower or "traceback" in line_lower:
                        errors.append(line.strip())
                    elif "warning" in line_lower:
                        warnings.append(line.strip())
                return {"errors": errors[-5:], "warnings": warnings[-5:]}  # Last 5 each
            return {"error": "Log file not found"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_process_info(self):
        """Get info about DeepTutor processes."""
        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'create_time']):
                try:
                    pinfo = proc.info
                    cmdline = " ".join(proc.cmdline()) if hasattr(proc, 'cmdline') else ""
                    if any(x in cmdline.lower() for x in ["deeptutor", "python3.11", "next"]):
                        if "deeptutor" in cmdline.lower() or "run_server" in cmdline:
                            procs.append({
                                "pid": pinfo['pid'],
                                "name": pinfo['name'],
                                "cpu": round(pinfo['cpu_percent'] or 0, 1),
                                "mem": round(pinfo['memory_percent'] or 0, 1),
                                "uptime_min": round((time.time() - pinfo['create_time']) / 60, 1) if pinfo.get('create_time') else 0
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return procs
        except Exception as e:
            return [{"error": str(e)}]
    
    def diagnose(self, health):
        """Generate diagnostic suggestions based on health data."""
        issues = []
        suggestions = []
        
        # Port checks
        if not health["backend"]["listening"]:
            issues.append("❌ Backend not listening on port 8001")
            suggestions.append("→ Restart backend: cd /Volumes/ORICO/DeepTutor && python3.11 -m deeptutor.api.run_server")
        if not health["frontend"]["listening"]:
            issues.append("❌ Frontend not listening on port 3782")
            suggestions.append("→ Restart frontend: cd /Volumes/ORICO/DeepTutor/web && NEXT_PUBLIC_API_BASE=http://localhost:8001 node .next/standalone/server.js -p 3782")
        
        # API checks
        if not health["backend_api"].get("success"):
            issues.append("⚠️ Backend API not responding")
            suggestions.append("→ Check backend logs: tail -50 /tmp/deeptutor_backend.log")
        
        if not health["llm_api"].get("success"):
            err = health["llm_api"].get("error", "Unknown")
            issues.append(f"⚠️ LLM API failed: {err}")
            if "404" in err:
                suggestions.append("→ LLM URL may be wrong. Check LLM_BINDING and LLM_HOST in .env")
            elif "401" in err or "invalid api key" in err.lower():
                suggestions.append("→ API key invalid. Check LLM_API_KEY in .env")
            elif "timeout" in err.lower():
                suggestions.append("→ LLM API timeout. Check network/proxy settings")
            else:
                suggestions.append(f"→ Investigate LLM error: {err}")
        
        # Memory check
        mem = health.get("memory", {})
        if "error" not in mem:
            if mem.get("percent", 0) > 85:
                issues.append(f"⚠️ High memory usage: {mem['percent']}%")
                suggestions.append("→ System running low on memory. Consider restarting services.")
        
        # Disk check
        disk = health.get("disk", {})
        if "error" not in disk:
            if disk.get("free_gb", 100) < 10:
                issues.append(f"⚠️ Low disk space: {disk['free_gb']}GB free")
                suggestions.append("→ ORICO volume running low on space. Consider cleanup.")
        
        # Log errors
        log = health.get("log_errors", {})
        if "errors" in log and log["errors"]:
            last_error = log["errors"][-1] if log["errors"] else ""
            if "404" in last_error:
                issues.append("⚠️ Recent 404 errors in backend log")
                suggestions.append("→ LLM endpoint URL mismatch. Check LLM_HOST and LLM_BINDING configuration.")
            elif "memory" in last_error.lower() or "killed" in last_error.lower():
                issues.append("⚠️ Process may have been OOM killed")
                suggestions.append("→ System low on memory. Reduce load or restart services.")
            elif "connection" in last_error.lower():
                issues.append("⚠️ Network connection errors in log")
                suggestions.append("→ Check proxy settings and network connectivity.")
        
        if not issues:
            return {"status": "healthy", "issues": [], "suggestions": ["✅ All systems operational"]}
        
        return {"status": "degraded", "issues": issues, "suggestions": suggestions}
    
    def get_full_health(self):
        """Get comprehensive health report."""
        health = {
            "timestamp": datetime.now().isoformat(),
            "backend": self.check_port(BACKEND_PORT),
            "frontend": self.check_port(FRONTEND_PORT),
            "backend_api": self.check_backend_api(),
            "llm_api": self.check_llm_api(),
            "memory": self.check_memory(),
            "disk": self.check_disk_space(),
            "log_errors": self.check_log_errors("/tmp/deeptutor_backend.log"),
            "processes": self.get_process_info(),
        }
        health["diagnosis"] = self.diagnose(health)
        return health


class MonitorDashboard(http.server.BaseHTTPRequestHandler):
    checker = HealthChecker()
    
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            health = self.checker.get_full_health()
            html = self.render_html(health)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path == "/api/health":
            health = self.checker.get_full_health()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def render_html(self, health):
        diag = health["diagnosis"]
        status_color = "#22c55e" if diag["status"] == "healthy" else "#ef4444"
        status_bg = "#dcfce7" if diag["status"] == "healthy" else "#fee2e2"
        
        # Service status cards
        backend_status = "✅ Running" if health["backend"]["listening"] else "❌ Down"
        frontend_status = "✅ Running" if health["frontend"]["listening"] else "❌ Down"
        api_status = "✅ OK" if health["backend_api"].get("success") else f"❌ {health['backend_api'].get('error', 'Failed')[:50]}"
        llm_status = "✅ OK" if health["llm_api"].get("success") else f"❌ {health['llm_api'].get('error', 'Failed')[:50]}"
        
        # Metrics
        mem = health.get("memory", {})
        mem_bar = f"{mem.get('percent', 0)}%"
        mem_color = "#22c55e" if mem.get('percent', 0) < 70 else "#f59e0b" if mem.get('percent', 0) < 85 else "#ef4444"
        
        disk = health.get("disk", {})
        disk_bar = f"{disk.get('percent', 0)}%"
        disk_color = "#22c55e" if disk.get('percent', 0) < 80 else "#ef4444"
        
        issues_html = "".join(f"<li>{i}</li>" for i in diag["issues"]) or "<li>✅ All systems operational</li>"
        suggestions_html = "".join(f"<li>{s}</li>" for s in diag["suggestions"])
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>DeepTutor Monitor</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; min-height: 100vh; }}
        .header {{ background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; padding: 20px 30px; }}
        .header h1 {{ font-size: 24px; font-weight: 600; }}
        .header p {{ opacity: 0.8; font-size: 13px; margin-top: 4px; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .status-banner {{ 
            padding: 16px 24px; 
            border-radius: 12px; 
            margin-bottom: 24px;
            background: {status_bg};
            border-left: 4px solid {status_color};
        }}
        .status-banner h2 {{ color: {status_color}; font-size: 18px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
        .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .card h3 {{ font-size: 14px; color: #64748b; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .metric {{ font-size: 28px; font-weight: 700; color: #1e293b; }}
        .metric-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        .progress-bar {{ height: 8px; background: #e2e8f0; border-radius: 4px; margin-top: 12px; overflow: hidden; }}
        .progress-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
        .service-item {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }}
        .service-item:last-child {{ border-bottom: none; }}
        .service-name {{ font-weight: 500; color: #334155; }}
        .service-status {{ font-weight: 600; }}
        .status-ok {{ color: #22c55e; }}
        .status-error {{ color: #ef4444; }}
        .status-warn {{ color: #f59e0b; }}
        .issues-section {{ background: white; border-radius: 12px; padding: 20px; margin-top: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .issues-section h3 {{ font-size: 16px; margin-bottom: 16px; color: #1e293b; }}
        .issues-list {{ list-style: none; }}
        .issues-list li {{ padding: 10px 14px; margin-bottom: 8px; background: #f8fafc; border-radius: 8px; font-size: 14px; }}
        .suggestions-list {{ list-style: none; }}
        .suggestions-list li {{ padding: 10px 14px; margin-bottom: 8px; background: #eff6ff; border-radius: 8px; font-size: 13px; color: #1e40af; font-family: monospace; }}
        .process-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }}
        .refresh {{ position: fixed; bottom: 20px; right: 20px; background: #1e40af; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; }}
        .refresh:hover {{ background: #1e3a8a; }}
        .log-error {{ font-size: 11px; color: #ef4444; background: #fef2f2; padding: 8px; border-radius: 4px; margin-top: 8px; font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 DeepTutor Monitor</h1>
        <p>{health['timestamp']} · Port 3783</p>
    </div>
    
    <div class="container">
        <div class="status-banner">
            <h2>{diag['status'].upper()}</h2>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>🖥️ System Resources</h3>
                <div style="margin-bottom: 16px;">
                    <div class="metric">{mem.get('percent', 0)}%</div>
                    <div class="metric-label">Memory ({mem.get('used_gb', 0)}GB / {mem.get('total_gb', 0)}GB)</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: {mem.get('percent', 0)}%; background: {mem_color}"></div></div>
                </div>
                <div>
                    <div class="metric">{disk.get('percent', 0)}%</div>
                    <div class="metric-label">ORICO Disk ({disk.get('free_gb', 0)}GB free)</div>
                    <div class="progress-bar"><div class="progress-fill" style="width: {disk.get('percent', 0)}%; background: {disk_color}"></div></div>
                </div>
            </div>
            
            <div class="card">
                <h3>🔌 Services</h3>
                <div class="service-item">
                    <span class="service-name">Backend (8001)</span>
                    <span class="service-status {'status-ok' if health['backend']['listening'] else 'status-error'}">{backend_status}</span>
                </div>
                <div class="service-item">
                    <span class="service-name">Frontend (3782)</span>
                    <span class="service-status {'status-ok' if health['frontend']['listening'] else 'status-error'}">{frontend_status}</span>
                </div>
                <div class="service-item">
                    <span class="service-name">Backend API</span>
                    <span class="service-status {'status-ok' if health['backend_api'].get('success') else 'status-error'}">{api_status}</span>
                </div>
                <div class="service-item">
                    <span class="service-name">LLM API</span>
                    <span class="service-status {'status-ok' if health['llm_api'].get('success') else 'status-error'}">{llm_status}</span>
                </div>
            </div>
            
            <div class="card">
                <h3>⚡ API Latency</h3>
                <div class="metric">{health['backend_api'].get('latency_ms', 'N/A')}ms</div>
                <div class="metric-label">Backend response</div>
                <div style="margin-top: 16px;">
                    <div class="metric">{health['llm_api'].get('latency_ms', 'N/A')}ms</div>
                    <div class="metric-label">LLM API response</div>
                </div>
            </div>
        </div>
        
        <div class="issues-section">
            <h3>🔧 Diagnostics & Suggestions</h3>
            <h4 style="margin: 16px 0 8px; color: #64748b; font-size: 12px;">ISSUES</h4>
            <ul class="issues-list">{issues_html}</ul>
            <h4 style="margin: 16px 0 8px; color: #64748b; font-size: 12px;">SUGGESTIONS</h4>
            <ul class="suggestions-list">{suggestions_html}</ul>
        </div>
        
        <div class="issues-section">
            <h3>📋 Recent Log Errors</h3>
            {''.join(f'<div class="log-error">{e}</div>' for e in health['log_errors'].get('errors', [])[:3]) or '<p style="color: #22c55e;">No recent errors</p>'}
        </div>
    </div>
    
    <button class="refresh" onclick="location.reload()">🔄 Refresh</button>
</body>
</html>"""


def run_server():
    server = http.server.HTTPServer(("", PORT), MonitorDashboard)
    logger.info(f"Monitor dashboard running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
