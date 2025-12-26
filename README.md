# Root MCP Server

A powerful Model Context Protocol (MCP) server that provides comprehensive system-level access and control. This server acts as a "God Mode" interface for Linux systems, offering tools for process management, file system operations, package management, and network inspection.

## Features

- **Process Management**: Start, stop, and monitor background tasks
- **Shell Execution**: Run blocking commands with full system access
- **File System Operations**: Read, write, search, and manage files and directories
- **Terminal Session Management**: Create and control tmux sessions
- **Package Management**: Install, remove, and update system packages
- **Network Inspection**: Analyze network connectivity and DNS resolution

## Prerequisites

- Python 3.8 or higher
- Linux-based operating system (tested on Ubuntu, Debian, Alpine, Fedora, Arch Linux)
- Appropriate system permissions (some tools require sudo/root access)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Praveens1234/mcp-server-root.git
cd mcp-server-root
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The server runs on port 8000 by default. To change this, modify the port number in the `server.py` file.

## Usage

1. Start the server:
```bash
python server.py
```

2. Connect your MCP client to:
```
http://localhost:8000/sse
```

## Available Tools

### Process Manager
- `start`: Start a background job
- `check_status`: Check the status of a running job
- `stop`: Stop a running job
- `list_jobs`: List all tracked jobs
- `read_global_history`: Read the global execution history

### Shell Executor
- `shell_execute`: Run quick blocking commands

### File System
- `read`: Read file contents
- `write`: Write content to a file
- `list`: List directory contents
- `delete`: Delete files or directories
- `search`: Search for files
- `mkdir`: Create directories

### Tmux Manager
- `create`: Create a new tmux session
- `kill`: Kill a tmux session
- `list`: List all tmux sessions
- `send`: Send commands to a tmux session
- `read`: Read the contents of a tmux session

### Package Manager
- `install`: Install system packages
- `remove`: Remove system packages
- `update`: Update package lists

### Network Inspector
- `my_ip`: Show network interface information
- `ping`: Ping a target host
- `curl`: Perform HTTP requests
- `dns`: Perform DNS lookups

## Security Considerations

⚠️ **WARNING**: This server provides unrestricted access to the underlying system. Only run this in trusted environments and ensure proper access controls are in place.

- Never expose this server to public networks without authentication
- Use appropriate firewall rules to restrict access
- Run with minimal privileges when possible
- Regularly audit logs for suspicious activity

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.