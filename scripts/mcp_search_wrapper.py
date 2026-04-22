#!/usr/bin/env python3
"""MiniMax MCP Search HTTP Wrapper"""
import json
import subprocess
import threading
import time
import sys
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 3785


class MiniMaxMCPSearch:
    def __init__(self):
        self.p = None
        self.rid = 0
        self.resp = {}
        self.lock = threading.Lock()
        self._start()

    def _start(self):
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = "sk-cp-8-i3tOaOXQubQe6_OiGFYikOKhe423atiFgiIeP7YprWPrATadzcHKjl2uGQ3KUh9r_OG-BTOITJ-u7S-4C_r_oCbiwc2Zlh1Ou1vLUiScjbdRYH5AdkMtI"
        env["MINIMAX_API_HOST"] = "https://api.minimaxi.com"
        env["MINIMAX_API_RESOURCE_MODE"] = "url"
        env["MINIMAX_MCP_BASE_PATH"] = "/tmp/mcp_resources"

        self.p = subprocess.Popen(
            ["uvx", "minimax-coding-plan-mcp", "-y"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=env
        )

        threading.Thread(target=self._read, daemon=True).start()
        time.sleep(2)

        # Initialize
        self._send("initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "search-wrapper", "version": "1.0"}
        })
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.p.stdin.flush()
        time.sleep(0.5)
        print("MiniMax MCP Search initialized", file=sys.stderr)

    def _read(self):
        while self.p:
            try:
                line = self.p.stdout.readline()
                if not line:
                    break
                d = json.loads(line)
                rid = d.get("id")
                if rid is not None:
                    with self.lock:
                        self.resp[rid] = d
            except:
                break

    def _send(self, method, params=None):
        with self.lock:
            self.rid += 1
            rid = self.rid
            self.resp[rid] = None
            req = {"jsonrpc": "2.0", "id": rid, "method": method}
            if params:
                req["params"] = params
            self.p.stdin.write(json.dumps(req) + "\n")
            self.p.stdin.flush()
            return rid

    def _wait(self, rid, timeout=15):
        for _ in range(int(timeout * 10)):
            time.sleep(0.1)
            with self.lock:
                if self.resp.get(rid) is not None:
                    return self.resp.pop(rid)
        return {"error": "timeout"}

    def search(self, query, count=5):
        rid = self._send("tools/call", {
            "name": "web_search",
            "arguments": {"query": query, "count": count}
        })
        result = self._wait(rid)
        if "error" in result:
            return result
        content = result.get("result", {}).get("content", [])
        if content:
            try:
                text = content[0].get("text", "{}")
                return json.loads(text)
            except:
                return {"raw": content}
        return result

    def close(self):
        if self.p:
            self.p.terminate()


_client = None


def get_client():
    global _client
    if _client is None:
        _client = MiniMaxMCPSearch()
    return _client


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/search"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            count = int(params.get("count", ["5"])[0])

            if not query:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing q parameter"}).encode())
                return

            try:
                result = get_client().search(query, count)
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>MiniMax Search</h1><p>GET /search?q=query</p></body></html>")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    client = get_client()
    server = HTTPServer(("", PORT), Handler)
    print(f"MiniMax Search: http://localhost:{PORT}/search?q=query", file=sys.stderr)
    server.serve_forever()
