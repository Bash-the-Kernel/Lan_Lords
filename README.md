# LAN Lords - 2D Multiplayer Fighting Game

A 2D multiplayer fighting game for 2-4 players running on a Local Area Network (LAN).

## Features

- **Multiplayer Combat**: Support for 2-4 players in real-time
- **Server-Client Architecture**: Central server manages game state
- **Real-time Synchronization**: Player positions, attacks, and health tracked in real-time
- **In-Game Chat**: Communicate with other players during gameplay
- **Cross-Platform**: Works on Windows and Linux

## Technical Stack

- **Language**: Python 3.7+
- **Libraries**:
  - `pygame` - Rendering and input handling
  - `socket` - Network communication
  - `threading` - Concurrent client handling
  - `json` - Message serialization
  - `asyncio` - Event loop management

## Project Structure

```
.
├── server.py           # Main server that handles clients and game logic
├── client.py           # Client application with GUI
├── protocol.py         # Message protocol definitions
├── config.py           # Configuration settings
└── README.md          # This file
```

## Requirements

Install the required dependencies:

```bash
pip install pygame
```

## How to Run

### 1. Start the Server

On the machine that will host the game:

```bash
python server.py
```

The server will listen on port 5555 by default. You'll see a message indicating the server is running and waiting for connections.

### 2. Start Clients

On each player's machine, run:

```bash
python client.py
```

Enter your player name and the server IP address when prompted.

### Connecting on the Same Machine

For testing on a single machine, use `localhost` or `127.0.0.1` as the server address.

For LAN connections, use the host machine's local IP address (e.g., `192.168.1.100`).

## Controls

- **Arrow Keys / WASD**: Move your character
- **Space**: Attack in the direction you're facing
- **Enter**: Open chat (type message and press Enter again)
- **Esc**: Exit game

## Game Mechanics

- **Health**: Each player starts with 100 HP
- **Movement**: Use arrow keys or WASD to move around the arena
- **Attacks**: Press space to attack. You damage players within your attack range
- **Attack Range**: Visual attack indicator shows damage range
- **Cooldown**: Attacks have a 1-second cooldown
- **Winning**: Last player standing wins

## Architecture

### Server (`server.py`)

- Manages up to 4 concurrent client connections
- Maintains game state (player positions, health, etc.)
- Broadcasts game updates to all clients
- Handles player disconnections gracefully

### Client (`client.py`)

- Connects to server via TCP socket
- Sends player input (movement, attacks)
- Receives and renders game state
- Renders game arena using pygame
- Handles chat messages

### Protocol (`protocol.py`)

- Defines message types and serialization
- JSON-based communication protocol
- Message types: CONNECT, DISCONNECT, PLAYER_INPUT, GAME_STATE, CHAT_MESSAGE, ATTACK

## Network Protocol

### Message Format

All messages are JSON objects with this structure:

```json
{
    "type": "message_type",
    "data": {
        ...
    }
}
```

### Message Types

- `connect`: Player joins the game
- `disconnect`: Player leaves the game
- `player_input`: Player movement/input
- `attack`: Player performs an attack
- `game_state`: Server broadcasts current game state
- `chat_message`: Chat message from a player

## Development

### Adding Features

The code is organized into modules:

- `server.py`: Server logic and game state management
- `client.py`: Client GUI and rendering
- `protocol.py`: Network protocol definitions
- `config.py`: Game configuration

To modify game mechanics, edit the relevant sections in `server.py`. To change the UI, modify rendering code in `client.py`.

## Troubleshooting

### Connection Issues

- Ensure firewall allows port 5555
- Check that server and clients are on the same network
- Verify IP address is correct

### Game Lag

- Ensure stable network connection
- Reduce number of players if experiencing issues
- Check server machine performance

### Client Crashes

- Make sure pygame is installed: `pip install pygame`
- Check Python version (3.7+ required)
- Verify server is running before starting clients

## License

This project is created for educational purposes to demonstrate networking and game development concepts.

## Credits

Built as a demonstration of:
- Socket programming
- Network synchronization
- Concurrent client handling
- Game development with pygame

