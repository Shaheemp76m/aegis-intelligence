# Aegis Intelligence - Termux Startup & Process Management

Aegis Intelligence runs entirely in Termux without requiring Docker or root privileges.

---

## 1. Quick Start (Foreground)

To start the backend in the foreground for debugging:

```bash
cd ~/aegis-intelligence
python3 server.py
```

The server binds strictly to `http://127.0.0.1:8765`.

---

## 2. Background Execution Options in Termux

Because Linux `systemd` is not present in Android/Termux, use one of the following methods to keep the server running reliably:

### Option A: Running with `nohup` (Simplest)

```bash
cd ~/aegis-intelligence
nohup python3 server.py > data/logs/server.log 2>&1 &
```

To verify it is running:
```bash
curl -s http://127.0.0.1:8765/health | jq
```

To stop the process:
```bash
pkill -f "python3 server.py"
```

---

### Option B: Running inside `tmux` (Recommended for Persistent Sessions)

1. Start a tmux session:
   ```bash
   tmux new -s aegis
   ```
2. Launch the backend:
   ```bash
   cd ~/aegis-intelligence
   python3 server.py
   ```
3. Detach from tmux by pressing `Ctrl + b` then `d`.
4. To re-attach later:
   ```bash
   tmux attach -t aegis
   ```

---

### Option C: Startup on Termux Boot (Termux:Boot)

If you have the Termux:Boot app installed:
1. Create boot script:
   ```bash
   mkdir -p ~/.termux/boot
   cat << 'EOF' > ~/.termux/boot/start-aegis.sh
   #!/data/data/com.termux/files/usr/bin/sh
   termux-wake-lock
   cd /data/data/com.termux/files/home/aegis-intelligence
   nohup python3 server.py > data/logs/server.log 2>&1 &
   EOF
   chmod +x ~/.termux/boot/start-aegis.sh
   ```

---

## 3. Checking Health & Viewing Logs

Check server health:
```bash
curl -i http://127.0.0.1:8765/health
```

View live server logs:
```bash
tail -f ~/aegis-intelligence/data/logs/server.log
```

View live security audit logs:
```bash
tail -f ~/aegis-intelligence/data/logs/audit.log
```
