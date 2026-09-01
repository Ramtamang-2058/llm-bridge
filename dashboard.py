"""
Minimal web dashboard for the task queue — stdlib only, so it works
anywhere with no extra installs.

Usage:
    python dashboard.py [--port 8000] [--host 127.0.0.1]
Then open http://127.0.0.1:8000 in your browser.
"""
import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import settings
import tasks

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>llm-bridge dashboard</title>
<style>
  body{font-family:system-ui,sans-serif;margin:2rem auto;max-width:900px;color:#222}
  h1{font-size:1.4rem}
  .card{background:#f6f6f6;border:1px solid #ddd;border-radius:8px;padding:1rem;margin-bottom:1rem}
  form{display:flex;gap:.5rem;margin-bottom:1.5rem}
  select,input[type=text]{padding:.5rem;font-size:1rem;flex:1;min-width:0}
  button{padding:.5rem 1rem;font-size:1rem;cursor:pointer}
  table{width:100%;border-collapse:collapse;font-size:.9rem}
  th,td{text-align:left;padding:.5rem;border-bottom:1px solid #eee;vertical-align:top}
  .s-pending{color:#b06a00}.s-in_progress{color:#1a6db0}.s-done{color:#1a8a3c}.s-error{color:#c02b2b}
  pre{white-space:pre-wrap;max-width:340px;max-height:120px;overflow:auto;font-size:.8rem}
</style>
</head>
<body>
<h1>llm-bridge dashboard</h1>
<div class="card">
  <form id="addForm">
    <select id="service"></select>
    <input type="text" id="prompt" placeholder="Prompt to send to this service..." required>
    <button type="submit">Add task</button>
  </form>
</div>
<div class="card">
  <table>
    <thead><tr><th>ID</th><th>Status</th><th>Service</th><th>Prompt</th><th>Result</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</div>
<script>
const svcSel = document.getElementById('service');
const rows = document.getElementById('rows');
function refresh(){
  fetch('/api/tasks').then(r=>r.json()).then(data=>{
    svcSel.innerHTML = data.services.map(s=>`<option value="${s}">${s}</option>`).join('');
    rows.innerHTML = data.tasks.map(t=>`
      <tr>
        <td>${t.id}</td>
        <td class="s-${t.status}">${t.status}</td>
        <td>${t.assigned_to}</td>
        <td>${escapeHtml(t.prompt)}</td>
        <td>${t.result ? `<pre>${escapeHtml(t.result)}</pre>` : ''}</td>
      </tr>`).join('');
  });
}
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
document.getElementById('addForm').addEventListener('submit', e=>{
  e.preventDefault();
  fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({service:svcSel.value,prompt:document.getElementById('prompt').value})})
  .then(()=>{document.getElementById('prompt').value='';refresh();});
});
refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        if path == "/api/tasks":
            tasks.init_db()
            try:
                rows = [dict(r) for r in tasks.get_conn().execute(
                    "SELECT * FROM tasks ORDER BY id DESC LIMIT 100").fetchall()]
            except sqlite3.Error:
                rows = []
            self._send(200, {"tasks": rows, "services": list(settings.services().keys())})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/add":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            service = data.get("service")
            prompt = data.get("prompt", "")
            if service not in settings.services() or not prompt:
                self._send(400, {"error": "service or prompt missing/invalid"})
                return
            tasks.init_db()
            task_id = tasks.add_task(service, prompt)
            self._send(200, {"added": task_id})
            return
        self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="llm-bridge dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    tasks.init_db()
    print(f"Dashboard: http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
