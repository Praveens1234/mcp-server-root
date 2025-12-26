import asyncio
import os
import shutil
import logging
import subprocess
import platform
import shlex
import uuid
import time
import signal
import collections
import itertools
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Third-party imports
try:
    from mcp.server import Server
    from mcp.server.sse import SseServerTransport
    from mcp.types import Tool, TextContent
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import Response
    import uvicorn
except ImportError as e:
    print(f"Critical Dependency Missing: {e}")
    print("Run: pip install mcp starlette uvicorn")
    exit(1)

# --- Configuration & Logging ---
GLOBAL_LOG_FILE = "server_global_history.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MCP-God-Mode-V7.2")

app_server = Server("Linux-God-Mode-V7.2")

# --- Global State Manager ---
class StateManager:
    def __init__(self):
        # Structure: { "job_id": { "process": Popen, "log_file": path, "cmd": str, "file_handle": file_obj, "start_time": float } }
        self.BACKGROUND_JOBS: Dict[str, Dict[str, Any]] = {}

    def clean_finished_jobs(self):
        """Garbage collection for file handles of finished jobs."""
        to_remove = []
        for job_id, job in self.BACKGROUND_JOBS.items():
            if job["process"].poll() is not None:
                # Process is dead, ensure file is closed
                if not job["file_handle"].closed:
                    try:
                        job["file_handle"].flush()
                        job["file_handle"].close()
                    except Exception:
                        pass
                # We don't remove the job key immediately so users can still check logs,
                # but we mark it as closed internally.

STATE = StateManager()

# --- Helpers ---

def append_to_global_log(text: str):
    """Writes to the permanent full history log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(GLOBAL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {text}\n")
    except Exception as e:
        logger.error(f"Global Log Error: {e}")

def read_log_tail(file_path: str, lines: int = 20) -> str:
    """Reads the last N lines efficiently."""
    if not os.path.exists(file_path): 
        return "Log file empty or not found."
    
    try:
        # Optimized for Linux/Mac
        if platform.system() != "Windows" and shutil.which("tail"):
            try:
                return subprocess.check_output(['tail', '-n', str(lines), file_path], stderr=subprocess.STDOUT).decode(errors='replace')
            except subprocess.CalledProcessError:
                return "Error reading log via tail."
        
        # Cross-platform fallback (Memory safe)
        with open(file_path, 'r', errors='replace') as f:
            # deque with maxlen discards old lines instantly, keeping memory low
            return "".join(collections.deque(f, maxlen=lines))
    except Exception as e:
        return f"Error reading log: {e}"

def safe_path(path_str: str) -> Path:
    """Resolves path allowing full system access (God Mode)."""
    try:
        if not path_str or str(path_str).strip() == "":
            return Path.cwd()
        # Resolve handles ../ and ~ expansion
        return Path(path_str).expanduser().resolve()
    except Exception:
        return Path.cwd()

def detect_package_manager():
    if shutil.which("apt-get"): return "apt-get" # More robust than apt
    if shutil.which("apk"): return "apk"
    if shutil.which("dnf"): return "dnf"
    if shutil.which("yum"): return "yum"
    if shutil.which("pacman"): return "pacman"
    if shutil.which("brew"): return "brew"
    return None

async def run_cmd_async(cmd: str, cwd: str = ".", timeout: int = 120) -> str:
    """Runs a blocking command asynchronously with zombie process protection."""
    try:
        run_dir = str(cwd) if os.path.exists(str(cwd)) else "."
        append_to_global_log(f"EXECUTE: {cmd} @ {run_dir}")
        
        # Select shell based on OS
        shell_exec = "/bin/bash" if shutil.which("bash") else "/bin/sh"
        if platform.system() == "Windows":
            shell_exec = None # Auto-select cmd.exe or powershell

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=run_dir,
            executable=shell_exec
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait() # Critical: Reap the zombie
            except: 
                pass
            append_to_global_log(f"TIMEOUT: {cmd}")
            return f"Error: Command timed out after {timeout}s."
        
        output = stdout.decode(errors='replace') + "\n" + stderr.decode(errors='replace')
        return output.strip() if output.strip() else "Done (No Output)"
    except Exception as e:
        return f"Execution Error: {str(e)}"

# --- Tool Definitions ---

@app_server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="process_manager",
            description="Manage background tasks. Starts jobs detached, streams logs to file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["start", "check_status", "stop", "list_jobs", "read_global_history"]},
                    "command": {"type": "string", "description": "Shell command to run backgrounded"},
                    "job_id": {"type": "string"},
                    "lines": {"type": "integer", "default": 20}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="shell_execute",
            description="Run quick blocking commands (ls, mkdir, git status).",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string", "description": "Optional working directory"}
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="file_system",
            description="High-performance file operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["read", "write", "list", "delete", "search", "mkdir"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["action", "path"]
            }
        ),
        Tool(
            name="tmux_manager",
            description="Persistent terminal sessions via tmux.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "kill", "list", "send", "read"]},
                    "session_name": {"type": "string"},
                    "command": {"type": "string"}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="package_manager",
            description="Install software. Needs sudo/root for most operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["install", "remove", "update"]},
                    "package": {"type": "string"}
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="network_inspector",
            description="Network analysis tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["my_ip", "ping", "curl", "dns"]},
                    "target": {"type": "string"}
                },
                "required": ["action"]
            }
        )
    ]

# --- Tool Logic ---

@app_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Periodic cleanup of file handles
    STATE.clean_finished_jobs()

    try:
        # 1. Process Manager
        if name == "process_manager":
            action = arguments.get("action")
            
            if action == "start":
                cmd = arguments.get("command")
                if not cmd: return [TextContent(type="text", text="Error: No command provided.")]
                
                job_id = str(uuid.uuid4())[:8]
                job_log_file = os.path.abspath(f"job_{job_id}.log")
                
                # File Handle Management
                f_out = open(job_log_file, "w")
                
                # Platform specific detachment
                kwargs = {}
                if platform.system() == "Windows":
                    kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kwargs['preexec_fn'] = os.setsid

                proc = subprocess.Popen(
                    cmd, shell=True, stdout=f_out, stderr=subprocess.STDOUT,
                    **kwargs
                )
                
                STATE.BACKGROUND_JOBS[job_id] = {
                    "process": proc,
                    "log_file": job_log_file,
                    "file_handle": f_out,
                    "command": cmd,
                    "start_time": time.time()
                }
                append_to_global_log(f"START_JOB: {job_id} | {cmd}")
                return [TextContent(type="text", text=f"Job Started.\nID: {job_id}\nLog Path: {job_log_file}")]

            elif action == "check_status":
                job_id = arguments.get("job_id")
                lines_req = arguments.get("lines", 20)
                if job_id not in STATE.BACKGROUND_JOBS: return [TextContent(type="text", text="Error: Job ID not found.")]
                
                job = STATE.BACKGROUND_JOBS[job_id]
                
                # Force flush python buffer to disk so read_tail can see it
                if not job["file_handle"].closed:
                    job["file_handle"].flush()
                    os.fsync(job["file_handle"].fileno())

                is_running = job["process"].poll() is None
                status = "RUNNING" if is_running else f"DONE (Exit: {job['process'].poll()})"
                
                log_content = read_log_tail(job["log_file"], lines=lines_req)
                return [TextContent(type="text", text=f"--- Job {job_id} [{status}] ---\nCMD: {job['command']}\n\n[LATEST LOGS]:\n{log_content}")]

            elif action == "stop":
                job_id = arguments.get("job_id")
                if job_id not in STATE.BACKGROUND_JOBS: return [TextContent(type="text", text="Job not found.")]
                
                job = STATE.BACKGROUND_JOBS[job_id]
                if job["process"].poll() is None:
                    # Logic: Kill process group to get children too
                    if platform.system() != "Windows":
                        try:
                            os.killpg(os.getpgid(job["process"].pid), signal.SIGTERM)
                        except ProcessLookupError:
                            pass # Already dead
                    else:
                        job["process"].terminate()
                    
                    # Wait slightly to ensure handle release
                    await asyncio.sleep(0.5)
                    return [TextContent(type="text", text=f"Job {job_id} stop signal sent.")]
                return [TextContent(type="text", text=f"Job {job_id} is already finished.")]

            elif action == "list_jobs":
                if not STATE.BACKGROUND_JOBS: return [TextContent(type="text", text="No active jobs tracked.")]
                report = []
                for k, v in STATE.BACKGROUND_JOBS.items():
                    status = 'RUNNING' if v['process'].poll() is None else 'DONE'
                    report.append(f"ID: {k} | {status} | {v['command']}")
                return [TextContent(type="text", text="\n".join(report))]

            elif action == "read_global_history":
                return [TextContent(type="text", text=read_log_tail(GLOBAL_LOG_FILE, lines=50))]

        # 2. Shell Execute
        elif name == "shell_execute":
            cmd = arguments.get("command")
            cwd = arguments.get("cwd", ".")
            return [TextContent(type="text", text=await run_cmd_async(cmd, safe_path(cwd)))]

        # 3. File System (Memory Optimized)
        elif name == "file_system":
            action = arguments.get("action")
            path = safe_path(arguments.get("path"))
            content = arguments.get("content")
            
            if action == "read":
                if not path.exists(): return [TextContent(type="text", text="Path does not exist.")]
                if path.stat().st_size > 10 * 1024 * 1024: # 10MB Limit for safety
                     return [TextContent(type="text", text="File too large (>10MB). Use 'tail' via shell_execute.")]
                return [TextContent(type="text", text=path.read_text(errors='replace'))]
            
            elif action == "write":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content or "", encoding="utf-8")
                return [TextContent(type="text", text=f"Successfully wrote to {path}")]
            
            elif action == "list":
                if not path.exists(): return [TextContent(type="text", text="Path not found")]
                # Optimization: Don't load full list into memory, use islice
                try:
                    iterator = path.iterdir()
                    # We take first 100 items efficiently
                    items = list(itertools.islice(iterator, 100))
                    
                    # Simple formatter
                    out_lines = []
                    for x in items:
                        type_tag = "[D]" if x.is_dir() else "[F]"
                        out_lines.append(f"{type_tag} {x.name}")
                    
                    if len(items) == 100:
                        out_lines.append("... (Truncated to first 100)")
                        
                    return [TextContent(type="text", text="\n".join(out_lines))]
                except PermissionError:
                    return [TextContent(type="text", text="Permission Denied.")]

            elif action == "delete":
                if path.exists():
                    if path.is_dir(): shutil.rmtree(path)
                    else: path.unlink()
                    return [TextContent(type="text", text="Deleted")]
                return [TextContent(type="text", text="Not Found")]
            
            elif action == "search":
                # Optimization: Limit recursion depth or count to prevent infinite hangs on /
                matches = []
                count = 0
                try:
                    # glob is safer than rglob for depth, but user asked for search
                    for p in path.rglob(f"*{content}*"):
                        matches.append(str(p))
                        count += 1
                        if count >= 50: break # Hard limit to prevent server freeze
                except Exception as e:
                    return [TextContent(type="text", text=f"Search interrupted: {e}")]
                return [TextContent(type="text", text="\n".join(matches) if matches else "No matches found (checked first 50 hits).")]

            elif action == "mkdir":
                path.mkdir(parents=True, exist_ok=True)
                return [TextContent(type="text", text="Directory Created")]

        # 4. Tmux Manager
        elif name == "tmux_manager":
            if not shutil.which("tmux"): return [TextContent(type="text", text="Error: 'tmux' is not installed.")]
            action = arguments.get("action")
            sess = shlex.quote(arguments.get("session_name", "mcp-session"))
            cmd_payload = arguments.get("command", "")
            
            if action == "create":
                # -d for detached, -s for name
                return [TextContent(type="text", text=await run_cmd_async(f"tmux new-session -d -s {sess}"))]
            elif action == "list":
                return [TextContent(type="text", text=await run_cmd_async("tmux list-sessions"))]
            elif action == "kill":
                return [TextContent(type="text", text=await run_cmd_async(f"tmux kill-session -t {sess}"))]
            elif action == "send":
                safe_payload = shlex.quote(cmd_payload)
                # Send keys and Enter (C-m)
                await run_cmd_async(f"tmux send-keys -t {sess} {safe_payload} C-m")
                return [TextContent(type="text", text=f"Sent command to session '{sess}'")]
            elif action == "read":
                return [TextContent(type="text", text=await run_cmd_async(f"tmux capture-pane -t {sess} -p"))]

        # 5. Package Manager
        elif name == "package_manager":
            pkg_mgr = detect_package_manager()
            if not pkg_mgr: return [TextContent(type="text", text="No supported package manager found (apt, apk, dnf, pacman, brew).")]
            
            action = arguments.get("action")
            pkg = shlex.quote(arguments.get("package", ""))
            
            cmd = ""
            # Auto-add sudo if not root, assumption made for 'God Mode' convenience
            sudo_prefix = "sudo " if os.geteuid() != 0 and shutil.which("sudo") else ""

            if pkg_mgr == "apt-get":
                if action == "install": cmd = f"{sudo_prefix}apt-get install -y {pkg}"
                elif action == "remove": cmd = f"{sudo_prefix}apt-get remove -y {pkg}"
                elif action == "update": cmd = f"{sudo_prefix}apt-get update"
            elif pkg_mgr == "apk":
                prefix = "" if os.geteuid() == 0 else "doas " 
                if action == "install": cmd = f"{prefix}apk add {pkg}"
                elif action == "remove": cmd = f"{prefix}apk del {pkg}"
                elif action == "update": cmd = f"{prefix}apk update"
            # Add other managers as needed...
            
            if not cmd: cmd = f"echo 'Manager {pkg_mgr} not fully configured in script logic yet.'"
            
            return [TextContent(type="text", text=await run_cmd_async(cmd))]

        # 6. Network Inspector
        elif name == "network_inspector":
            action = arguments.get("action")
            target = shlex.quote(arguments.get("target", "8.8.8.8"))
            
            if action == "my_ip": 
                return [TextContent(type="text", text=await run_cmd_async("ip addr show" if shutil.which("ip") else "ifconfig"))]
            elif action == "ping": 
                # -c 3 for linux, -n 3 for windows
                flag = "-n" if platform.system() == "Windows" else "-c"
                return [TextContent(type="text", text=await run_cmd_async(f"ping {flag} 3 {target}"))]
            elif action == "curl": 
                return [TextContent(type="text", text=await run_cmd_async(f"curl -I {target}"))]
            elif action == "dns": 
                return [TextContent(type="text", text=await run_cmd_async(f"nslookup {target}"))]

        else:
            return [TextContent(type="text", text=f"Unknown Tool: {name}")]

    except Exception as e:
        logger.error(f"Tool Execution Error: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Critical Server Error: {str(e)}")]

# --- Server Start ---
sse = SseServerTransport("/messages")

async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app_server.run(streams[0], streams[1], app_server.create_initialization_options())

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)
    return Response(status_code=202)

starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"])
    ]
)

if __name__ == "__main__":
    print("\n🚀 MCP God Mode V7.2 (Optimized & Debugged) Running")
    print(f"📍 Log File: {os.path.abspath(GLOBAL_LOG_FILE)}")
    uvicorn.run(starlette_app, host="0.0.0.0", port=8000)