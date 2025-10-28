# Quick Start Guide

## Installation

### 1. Install Python Dependencies

Make sure you have Python 3.7+ installed, then:

```bash
pip install -r requirements.txt
```

### 2. Run the Server

**On Windows:**
```bash
start_server.bat
# Or directly:
python server.py
```

**On Linux/Mac:**
```bash
./start_server.sh
# Or directly:
python3 server.py
```

The server will start and listen on port 5555.

### 3. Run the Clients

Open a terminal/command prompt for each player (you can run multiple clients on the same machine).

**On Windows:**
```bash
start_client.bat
# Or directly:
python client.py
```

**On Linux/Mac:**
```bash
./start_client.sh
# Or directly:
python3 client.py
```

When prompted:
- Enter your player name
- Enter the server IP address
  - Use `localhost` if the server is on the same machine
  - Use the server's local IP (e.g., `192.168.1.100`) for LAN connections

## Finding Your Server IP

### Windows:
```bash
ipconfig
# Look for "IPv4 Address" under your network adapter
```

### Linux/Mac:
```bash
ifconfig
# Or:
ip addr show
# Look for "inet" address of your network interface
```

## Game Controls

- **Arrow Keys** or **WASD**: Move your character
- **Space**: Attack in the direction you're facing
- **Enter**: Open chat (type message, press Enter to send)
- **Esc**: Exit game

## Testing Locally

To test on the same machine:

1. Start the server (terminal 1)
2. Start client 1 (terminal 2) - use `localhost` as server IP
3. Start client 2 (terminal 3) - use `localhost` as server IP
4. Repeat for more players up to 4 total

## Troubleshooting

### Connection Refused
- Make sure the server is running first
- Check that firewall allows port 5555
- Verify the server IP is correct

### Module Not Found
```bash
pip install pygame
```

### Port Already in Use
- Another instance of the server may be running
- Close it or change the port in `config.py`

## LAN Play

For multiple machines on the same network:

1. Start server on one machine
2. Note the server's IP address
3. Each client connects to that IP
4. Ensure all machines are on the same network (WiFi or LAN)
5. Firewall may need to allow Python through

