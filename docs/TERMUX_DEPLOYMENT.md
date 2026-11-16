# Aegis Intelligence — Termux Deployment & Production Guide

This guide details the deployment, process management, networking, and maintenance of Aegis Intelligence in a native Termux Android environment (arm64 / aarch64, tested on OnePlus 9R).

---

## 1. Environment & Architecture Overview

Aegis Intelligence is designed to run locally on Android without requiring root privileges, proot containers, or Docker. It leverages standard POSIX utilities, Python 3.14+, SQLite with WAL journaling, and native loopback networking.

### Hardware & Software Profile
- **Device**: OnePlus 9R (Qualcomm Snapdragon 870, 8GB/12GB RAM)
- **OS**: Android (OxygenOS / Custom AOSP)
- **Runtime Environment**: Termux (`/data/data/com.termux/files/usr/`)
- **Architecture**: `aarch64` (`arm64-v8a`)
- **Python**: 3.14.x (Termux native package)
- **Primary Daemon**: `server.py` binding strictly to `127.0.0.1:8765`
- **Orchestration / Workflow**: n8n 2.47.4 (Node.js runtime on Termux or external server)

---

## 2. Termux Battery Optimization & Wake-Lock

Android aggressively suspends background processes when the screen turns off or when battery optimization is active. To prevent the Aegis server and Antigravity execution tasks from sleeping:

### 2.1 Termux Wake-Lock
Always acquire an Android wake-lock before running persistent daemons:
```bash
termux-wake-lock
```
*(To release the wake-lock later, run `termux-wake-unlock`).*

### 2.2 System Battery Optimization Settings
1. Go to Android **Settings** → **Battery** → **Battery Optimization / Background usage limits**.
2. Find **Termux** and set it to **Don't optimize** / **Unrestricted**.
3. (Optional on OnePlus/OxygenOS): In Recent Apps, lock Termux to prevent task clearing.

---

## 3. Process Management (Without Systemd)

Because Android lacks `systemd` / `init.d`, choose one of the following methods for daemon management:

### Option A: Persistent `tmux` Session (Recommended for Interactive Development)
`tmux` preserves terminal state and keeps the daemon active even if the SSH/terminal session disconnects.

```bash
# 1. Start a named tmux session
tmux new -s aegis

# 2. Start the daemon with bytecode suppression
cd ~/aegis-intelligence
python3 -B server.py

# 3. Detach from session: Press Ctrl+b, then d
# 4. Re-attach whenever needed:
tmux attach -t aegis
```

### Option B: Background Service with `nohup`
For headless background execution:

```bash
cd ~/aegis-intelligence
nohup python3 -B server.py > data/logs/server.log 2>&1 &
echo $! > data/server.pid
```

To stop the background server:
```bash
if [ -f data/server.pid ]; then
  kill $(cat data/server.pid) && rm data/server.pid
else
  pkill -f "python3.*server.py"
fi
```

### Option C: Automatic Startup on Device Boot (`Termux:Boot`)
Install the **Termux:Boot** companion app from F-Droid to automatically launch Aegis on device restart.

1. Ensure the boot directory exists:
   ```bash
   mkdir -p ~/.termux/boot
   ```
2. Create the boot script `~/.termux/boot/start-aegis.sh`:
   ```bash
   #!/data/data/com.termux/files/usr/bin/sh
   termux-wake-lock
   cd /data/data/com.termux/files/home/aegis-intelligence
   
   # Rotate old server log if > 10MB
   if [ -f data/logs/server.log ] && [ $(wc -c < data/logs/server.log) -gt 10485760 ]; then
     mv data/logs/server.log data/logs/server.log.old
   fi
   
   nohup python3 -B server.py > data/logs/server.log 2>&1 &
   echo $! > data/server.pid
   ```
3. Make the script executable:
   ```bash
   chmod +x ~/.termux/boot/start-aegis.sh
   ```

---

## 4. Networking & Secure Exposure

### 4.1 Strict Loopback Boundary
By default, Aegis Intelligence binds **only** to `127.0.0.1:8765`. It must **never** be bound directly to `0.0.0.0` or exposed unencrypted over local Wi-Fi.

### 4.2 Local n8n Architecture
If n8n is running locally within Termux:
- n8n URL: `http://127.0.0.1:5678`
- Aegis Base URL in HTTP Request nodes: `http://127.0.0.1:8765`
- Network traffic never leaves the Linux kernel network namespace.

### 4.3 Cloudflare Tunnel (Remote Access to n8n Webhook / Dashboard)
If you access n8n or trigger Telegram webhooks from outside the local network:
1. **Never tunnel Aegis API port 8765 directly.** Aegis is a privileged local operational engine.
2. Only tunnel the **n8n webhook endpoint** or UI (`5678`), protected by Cloudflare Access or strong authentication:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:5678
   ```
3. The n8n agent communicates securely over loopback to Aegis (`http://127.0.0.1:8765`) on the same device.

---

## 5. Health Checks & Log Monitoring

### Health Endpoint
Verify server availability, uptime, and database connection:
```bash
curl -s http://127.0.0.1:8765/health | jq
```

Expected output:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "database": "connected",
  "registered_projects": 1,
  "antigravity_cli": "available"
}
```

### Live Log Streams
Monitor operational and security logs:
```bash
# Server application logs
tail -f ~/aegis-intelligence/data/logs/server.log

# Security and permission audit log
tail -f ~/aegis-intelligence/data/logs/audit.log
```

---

## 6. Maintenance, Backups & Disaster Recovery

### 6.1 Database Backups
Aegis uses SQLite in Write-Ahead Logging (WAL) mode. To create a consistent, live-safe snapshot without interrupting operations, use the SQLite backup API or CLI `.backup` command:

```bash
mkdir -p data/backups
python3 -B -c "
import sqlite3
src = sqlite3.connect('data/aegis.db')
dst = sqlite3.connect('data/backups/aegis_manual_backup.db')
src.backup(dst)
dst.close()
src.close()
print('Consistent backup created successfully.')
"
```

### 6.2 Low Memory Killer (OOM) Protection
Termux processes can occasionally be targeted by Android's `lmkd` (Low Memory Killer Daemon) during heavy compilation or large Antigravity runs:
- Ensure heavy compilations (e.g. native C-extensions) use single-threaded jobs: `MAKEFLAGS="-j2"`.
- Run Python with bytecode caching disabled (`-B`) to reduce filesystem write pressure on flash storage.
- Regularly inspect `data/logs/` to prevent disk saturation.
