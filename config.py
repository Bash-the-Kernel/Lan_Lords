"""
Configuration settings for LAN Lords
"""

# Server Configuration
# Use localhost and a high port to avoid Windows permission issues (WinError 10013)
SERVER_HOST = "127.0.0.1"  # For LAN later, switch to "0.0.0.0" or your LAN IP
SERVER_PORT = 60000
MAX_PLAYERS = 4
BUFFER_SIZE = 4096

# Game Configuration
ARENA_WIDTH = 800
ARENA_HEIGHT = 600
GAME_TICK_RATE = 60  # Updates per second

# Player Configuration
PLAYER_SIZE = 40
PLAYER_SPEED = 5
PLAYER_MAX_HEALTH = 100
PLAYER_ATTACK_DAMAGE = 10
PLAYER_ATTACK_RANGE = 60
PLAYER_ATTACK_COOLDOWN = 1.0  # seconds
PLAYER_COLORS = [
    (255, 0, 0),    # Red
    (0, 0, 255),    # Blue
    (0, 255, 0),    # Green
    (255, 255, 0)   # Yellow
]

# Chat Configuration
MAX_CHAT_HISTORY = 50
CHAT_FONT_SIZE = 16

# Network Configuration
MESSAGE_DELIMITER = "\n"

