"""
LAN Lords Server
Handles client connections, game state management, and broadcasting updates
"""

import socket
import threading
import json
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from protocol import Message, MessageType, ActionType, Direction
from config import (
    SERVER_HOST, SERVER_PORT, MAX_PLAYERS, BUFFER_SIZE,
    ARENA_WIDTH, ARENA_HEIGHT, GAME_TICK_RATE,
    PLAYER_SPEED, PLAYER_MAX_HEALTH, PLAYER_ATTACK_DAMAGE,
    PLAYER_ATTACK_RANGE, PLAYER_ATTACK_COOLDOWN
)

@dataclass
class Player:
    """Represents a player in the game"""
    id: int
    name: str
    x: float
    y: float
    vx: float = 0.0  # Velocity X
    vy: float = 0.0  # Velocity Y
    health: int = PLAYER_MAX_HEALTH
    direction: Direction = Direction.NONE
    is_jumping: bool = False
    can_double_jump: bool = False
    is_crouching: bool = False
    is_grounded: bool = False
    last_attack_time: float = 0.0
    conn: Optional[socket.socket] = None
    address: Optional[Tuple[str, int]] = None
    
    def is_alive(self) -> bool:
        return self.health > 0
    
    def can_attack(self, current_time: float) -> bool:
        return current_time - self.last_attack_time >= PLAYER_ATTACK_COOLDOWN
    
    def attack(self, current_time: float):
        self.last_attack_time = current_time
    
    def update_physics(self, platforms):
        """Update player physics (gravity, collisions)"""
        GRAVITY = 0.5
        MAX_FALL_SPEED = 12
        
        # Apply gravity
        if not self.is_grounded:
            self.vy += GRAVITY
            if self.vy > MAX_FALL_SPEED:
                self.vy = MAX_FALL_SPEED
        
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Horizontal friction
        self.vx *= 0.85
        if abs(self.vx) < 0.1:
            self.vx = 0
        
        # Check platform collisions
        self.is_grounded = False
        player_bottom = self.y + 40
        player_top = self.y
        player_left = self.x
        player_right = self.x + 40
        
        for platform in platforms:
            # Check if player is above platform
            if player_bottom >= platform[1] and self.vy > 0:
                # Check X overlap
                if player_left < platform[0] + platform[2] and player_right > platform[0]:
                    # Landing on top
                    if player_top < platform[1]:
                        self.y = platform[1] - 40
                        self.vy = 0
                        self.is_grounded = True
                        self.is_jumping = False
                        self.can_double_jump = True
            
            # Side collisions
            if player_bottom > platform[1] and player_top < platform[1] + platform[3]:
                # Hit from left
                if player_right > platform[0] and self.vx > 0 and player_left < platform[0]:
                    self.x = platform[0] - 40
                    self.vx = 0
                # Hit from right
                if player_left < platform[0] + platform[2] and self.vx < 0 and player_right > platform[0] + platform[2]:
                    self.x = platform[0] + platform[2]
                    self.vx = 0
        
        # Arena bounds
        self.x = max(0, min(ARENA_WIDTH - 40, self.x))
        self.y = max(0, min(ARENA_HEIGHT - 40, self.y))
        
        if self.y >= ARENA_HEIGHT - 40:
            self.y = ARENA_HEIGHT - 40
            self.vy = 0
            self.is_grounded = True
            self.is_jumping = False
            self.can_double_jump = True
    
    def move(self, action: ActionType, direction: Direction):
        """Update player movement state"""
        self.direction = direction
        
        if action == ActionType.MOVE:
            if direction == Direction.LEFT:
                self.vx = -PLAYER_SPEED * 0.8
            elif direction == Direction.RIGHT:
                self.vx = PLAYER_SPEED * 0.8
            elif direction == Direction.UP:
                # Jump
                if self.is_grounded:
                    self.vy = -13
                    self.is_jumping = True
                    self.can_double_jump = True
                elif not self.is_jumping and self.can_double_jump:
                    self.vy = -13
                    self.is_jumping = True
                    self.can_double_jump = False
            elif direction == Direction.DOWN:
                # Crouch
                self.is_crouching = True

class GameServer:
    """Main game server that manages players and game state"""
    
    def __init__(self):
        self.players: Dict[int, Player] = {}
        self.next_player_id = 1
        self.running = True
        self.lock = threading.Lock()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.chat_history: List[Dict[str, any]] = []
        # Define platforms (x, y, width, height)
        self.platforms = [
            (80, ARENA_HEIGHT - 80, ARENA_WIDTH - 160, 20),  # Ground
            (120, ARENA_HEIGHT - 220, 180, 18),  # Left platform
            (ARENA_WIDTH - 300, ARENA_HEIGHT - 220, 180, 18),  # Right platform
            (ARENA_WIDTH//2 - 120, 120, 240, 16),  # Top platform
        ]
    
    def start(self):
        """Start the game server"""
        self.socket.bind((SERVER_HOST, SERVER_PORT))
        self.socket.listen(MAX_PLAYERS)
        print(f"🎮 LAN Lords Server started on {SERVER_HOST}:{SERVER_PORT}")
        print(f"Waiting for players to connect...")
        
        # Start periodic broadcast loop for game state
        broadcaster = threading.Thread(target=self.broadcast_loop)
        broadcaster.daemon = True
        broadcaster.start()

        try:
            while self.running:
                client_socket, address = self.socket.accept()
                print(f"📥 Connection from {address}")
                
                # Check if we have room for more players
                with self.lock:
                    if len(self.players) >= MAX_PLAYERS:
                        print("❌ Server is full!")
                        client_socket.close()
                        continue
                
                # Handle new client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
        except Exception as e:
            print(f"Error in server loop: {e}")
        finally:
            self.stop()

    def broadcast_loop(self):
        """Periodically update physics and broadcast game state to all clients"""
        interval = 1.0 / max(1, GAME_TICK_RATE)
        while self.running:
            try:
                time.sleep(interval)
                # Update physics even when no input
                with self.lock:
                    for p in self.players.values():
                        p.update_physics(self.platforms)
                
                # Broadcast game state
                if self.players:
                    game_state = self.get_game_state()
                    message = Message(MessageType.GAME_STATE, game_state)
                    payload = message.to_json().encode('utf-8') + b'\n'
                    for pid, p in self.players.items():
                        try:
                            p.conn.sendall(payload)
                        except:
                            pass
            except Exception as e:
                time.sleep(interval)
    
    def handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle communication with a single client using newline-delimited JSON messages"""
        player_id = None
        buffer = ""
        try:
            # Read until we get a CONNECT message
            while self.running and player_id is None:
                chunk = client_socket.recv(BUFFER_SIZE).decode('utf-8')
                if not chunk:
                    return
                buffer += chunk
                # Debug: show received chunk size
                try:
                    print(f"   Rx {len(chunk)} bytes from {address}")
                    print(f"   Buffer now has {len(buffer)} chars: {buffer[:100]}")
                except:
                    pass
                # Try to parse as-is if it looks complete
                trimmed = buffer.strip()
                if player_id is None and trimmed.startswith('{') and trimmed.endswith('}'):
                    print(f"   Trying to parse CONNECT message...")
                    try:
                        message = Message.from_json(trimmed)
                        print(f"   Parsed message type: {message.type}, name: {message.data.get('name')}")
                        buffer = ""  # consumed
                        if message.type == MessageType.CONNECT:
                            print("   Message type is CONNECT, calling add_player...")
                            player_name = message.data.get("name", f"Player")
                            player_id = self.add_player(client_socket, address, player_name)
                            print(f"   add_player returned: {player_id}")
                            if player_id is None:
                                print("   add_player returned None, returning")
                                return
                            print(f"✅ Player {player_id} ({player_name}) joined!")
                            print(f"   Total players now: {len(self.players)}")
                            print("   Done with join process")
                    except Exception as e:
                        print(f"Parse error (no newline): {e}")
                        import traceback
                        traceback.print_exc()
                
                # Also try newline-delimited
                while '\n' in buffer and player_id is None:
                    line, buffer = buffer.split('\n', 1)
                    if not line:
                        continue
                    try:
                        message = Message.from_json(line)
                    except Exception as e:
                        print(f"Invalid message during connect from {address}: {e}")
                        continue
                    if message.type == MessageType.CONNECT:
                        player_name = message.data.get("name", f"Player")
                        player_id = self.add_player(client_socket, address, player_name)
                        if player_id is None:
                            return
                        print(f"✅ Player {player_id} ({player_name}) joined!")
                        print(f"   Total players now: {len(self.players)}")
                        self.send_game_state(player_id)
                        self.broadcast_player_joined(player_id)


            # Main message loop
            while self.running and player_id in self.players:
                chunk = client_socket.recv(BUFFER_SIZE).decode('utf-8')
                if not chunk:
                    break
                buffer += chunk
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line:
                        continue
                    try:
                        message = Message.from_json(line)
                        self.handle_message(player_id, message)
                    except Exception as e:
                        print(f"Error handling message from player {player_id}: {e}")
                        # continue processing remaining buffered messages
                        continue
        except Exception as e:
            print(f"Error in client handler: {e}")
        finally:
            if player_id:
                self.remove_player(player_id)
                try:
                    client_socket.close()
                except:
                    pass
                print(f"👋 Player {player_id} disconnected")
    
    def add_player(self, client_socket: socket.socket, address: Tuple[str, int], name: str) -> Optional[int]:
        """Add a new player to the game"""
        print(f"   add_player called for {name}")
        with self.lock:
            print(f"   Lock acquired, checking max players...")
            if len(self.players) >= MAX_PLAYERS:
                print(f"   Max players reached ({len(self.players)} >= {MAX_PLAYERS})")
                return None
            
            player_id = self.next_player_id
            self.next_player_id += 1
            print(f"   Assigned player ID: {player_id}")
            
            # Spawn player at different positions based on ID
            spawn_positions = [
                (100, 100),
                (700, 100),
                (100, 500),
                (700, 500)
            ]
            spawn_idx = (player_id - 1) % len(spawn_positions)
            x, y = spawn_positions[spawn_idx]
            print(f"   Spawning at ({x}, {y})")
            
            player = Player(
                id=player_id,
                name=name,
                x=x,
                y=y,
                health=PLAYER_MAX_HEALTH,
                direction=Direction.NONE,
                conn=client_socket,
                address=address
            )
            print(f"   Created Player object")
            
            self.players[player_id] = player
            print(f"   Added to players dict (total: {len(self.players)})")
            
            # Send player their own ID
            player_config = {
                "player_id": player_id,
                "name": name
            }
            config_msg = Message(MessageType.PLAYER_JOINED, player_config)
            try:
                payload = config_msg.to_json().encode('utf-8') + b'\n'
                print(f"   Sending PLAYER_JOINED message ({len(payload)} bytes)")
                client_socket.sendall(payload)
                print(f"   Sent PLAYER_JOINED successfully")
            except Exception as e:
                print(f"   Error sending PLAYER_JOINED: {e}")
            
            # Send initial game state
            players_data = []
            for pid, p in self.players.items():
                players_data.append({
                    "id": p.id,
                    "name": p.name,
                    "x": p.x,
                    "y": p.y,
                    "health": p.health,
                    "direction": p.direction.value,
                    "max_health": PLAYER_MAX_HEALTH
                })
            game_state = {
                "players": players_data,
                "chat": self.chat_history[-10:],
                "timestamp": time.time()
            }
            message = Message(MessageType.GAME_STATE, game_state)
            to_remove = []
            for pid, p in self.players.items():
                try:
                    payload = message.to_json().encode('utf-8') + b'\n'
                    p.conn.sendall(payload)
                except:
                    to_remove.append(pid)
            for pid in to_remove:
                self.players.pop(pid, None)
            print(f"   Broadcasted game state in add_player")

            print(f"   Returning player_id: {player_id}")
            return player_id
    
    def remove_player(self, player_id: int):
        """Remove a player from the game"""
        with self.lock:
            if player_id in self.players:
                self.players.pop(player_id)
                self.broadcast_player_left(player_id)
    
    def handle_message(self, player_id: int, message: Message):
        """Process incoming message from a player"""
        if message.type == MessageType.PLAYER_INPUT:
            self.handle_player_input(player_id, message.data)
        elif message.type == MessageType.ATTACK:
            self.handle_attack(player_id, message.data)
        elif message.type == MessageType.CHAT_MESSAGE:
            self.handle_chat_message(player_id, message.data)
        elif message.type == MessageType.REQUEST_STATE:
            # Send full game state back to requester
            self.send_game_state(player_id)
    
    def handle_player_input(self, player_id: int, data: Dict):
        """Handle player movement input"""
        with self.lock:
            if player_id not in self.players:
                return
            
            player = self.players[player_id]
            action = ActionType(data.get("action", "none"))
            direction = Direction(data.get("direction", "none"))
            
            # Handle input
            if action == ActionType.MOVE:
                player.move(action, direction)
            
            # Reset crouching for this player if not crouching
            if direction != Direction.DOWN:
                player.is_crouching = False
    
    def handle_attack(self, player_id: int, data: Dict):
        """Handle player attack"""
        with self.lock:
            if player_id not in self.players:
                return
            
            player = self.players[player_id]
            current_time = time.time()
            
            if not player.can_attack(current_time):
                return
            
            player.attack(current_time)
            direction = Direction(data.get("direction", "none"))
            
            # Calculate attack position
            attack_x, attack_y = self.get_attack_position(player, direction)
            
            # Check for hits on other players
            for other_id, other_player in self.players.items():
                if other_id == player_id or not other_player.is_alive():
                    continue
                
                # Check distance
                dx = other_player.x - attack_x
                dy = other_player.y - attack_y
                distance = (dx * dx + dy * dy) ** 0.5
                
                if distance <= PLAYER_ATTACK_RANGE:
                    other_player.health -= PLAYER_ATTACK_DAMAGE
                    other_player.health = max(0, other_player.health)
                    
                    print(f"💥 Player {player_id} hit Player {other_id}! Health: {other_player.health}")
                    
                    # Add chat message
                    self.add_chat_message(
                        f"{player.name} hit {other_player.name}!",
                        is_system=True
                    )
            
            # Broadcast updated game state
            self.broadcast_game_state()
    
    def get_attack_position(self, player: Player, direction: Direction) -> Tuple[float, float]:
        """Get the position where the attack occurs"""
        if direction == Direction.UP:
            return (player.x + 20, player.y - 30)
        elif direction == Direction.DOWN:
            return (player.x + 20, player.y + 70)
        elif direction == Direction.LEFT:
            return (player.x - 30, player.y + 20)
        elif direction == Direction.RIGHT:
            return (player.x + 70, player.y + 20)
        else:
            return (player.x + 20, player.y + 20)
    
    def handle_chat_message(self, player_id: int, data: Dict):
        """Handle chat message from player"""
        with self.lock:
            if player_id not in self.players:
                return
            
            player = self.players[player_id]
            text = data.get("text", "")
            
            if text:
                self.add_chat_message(f"{player.name}: {text}", is_system=False)
                self.broadcast_game_state()
    
    def add_chat_message(self, text: str, is_system: bool = False):
        """Add a message to chat history"""
        self.chat_history.append({
            "text": text,
            "is_system": is_system,
            "timestamp": time.time()
        })
        
        # Keep only recent messages
        if len(self.chat_history) > 100:
            self.chat_history = self.chat_history[-100:]
    
    def send_game_state(self, player_id: int):
        """Send game state to a specific player"""
        if player_id not in self.players:
            return
        
        game_state = self.get_game_state()
        message = Message(MessageType.GAME_STATE, game_state)
        
        try:
            payload = message.to_json().encode('utf-8') + b'\n'
            self.players[player_id].conn.sendall(payload)
            try:
                print(f"   → Sent initial GAME_STATE to {player_id} with {len(game_state.get('players', []))} players")
            except:
                pass
        except Exception as e:
            print(f"Error sending game state to player {player_id}: {e}")
    
    def broadcast_game_state(self):
        """Send game state to all connected players"""
        print(f"   broadcast_game_state called")
        if not self.players:
            print(f"   No players, returning")
            return
        print(f"   Calling get_game_state...")
        game_state = self.get_game_state()
        print(f"   Got game_state with {len(game_state.get('players', []))} players")
        message = Message(MessageType.GAME_STATE, game_state)
        print(f"   Created message")
        
        to_remove = []
        for player_id, player in self.players.items():
            try:
                payload = message.to_json().encode('utf-8') + b'\n'
                player.conn.sendall(payload)
            except Exception as e:
                print(f"Error broadcasting to player {player_id}: {e}")
                to_remove.append(player_id)
        
        # Remove disconnected players
        for player_id in to_remove:
            self.remove_player(player_id)
        try:
            print(f"   → Broadcast GAME_STATE to {len(self.players)} players (entities={len(game_state.get('players', []))})")
        except:
            pass
    
    def broadcast_player_joined(self, player_id: int):
        """Notify all players that a new player joined"""
        if player_id not in self.players:
            return
        
        player = self.players[player_id]
        message_data = {
            "player_id": player_id,
            "name": player.name
        }
        message = Message(MessageType.PLAYER_JOINED, message_data)
        
        for p_id, p in self.players.items():
            if p_id != player_id:
                try:
                    p.conn.sendall(message.to_json().encode('utf-8') + b'\n')
                except:
                    pass
    
    def broadcast_player_left(self, player_id: int):
        """Notify all players that a player left"""
        message_data = {"player_id": player_id}
        message = Message(MessageType.PLAYER_LEFT, message_data)
        
        for p_id, p in self.players.items():
            try:
                p.conn.sendall(message.to_json().encode('utf-8') + b'\n')
            except:
                pass
    
    def get_game_state(self) -> Dict:
        """Get current game state"""
        print(f"   get_game_state: acquiring lock...")
        with self.lock:
            print(f"   get_game_state: lock acquired")
            players_data = []
            for player_id, player in self.players.items():
                players_data.append({
                    "id": player.id,
                    "name": player.name,
                    "x": player.x,
                    "y": player.y,
                    "health": player.health,
                    "direction": player.direction.value,
                    "max_health": PLAYER_MAX_HEALTH,
                    "is_crouching": player.is_crouching
                })
            
            return {
                "players": players_data,
                "chat": self.chat_history[-10:],  # Last 10 messages
                "timestamp": time.time()
            }
    
    def stop(self):
        """Stop the server"""
        self.running = False
        self.socket.close()
        print("🛑 Server stopped")

if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        server.stop()

