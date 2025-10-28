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
    health: int
    direction: Direction
    last_attack_time: float = 0.0
    conn: Optional[socket.socket] = None
    address: Optional[Tuple[str, int]] = None
    
    def is_alive(self) -> bool:
        return self.health > 0
    
    def can_attack(self, current_time: float) -> bool:
        return current_time - self.last_attack_time >= PLAYER_ATTACK_COOLDOWN
    
    def attack(self, current_time: float):
        self.last_attack_time = current_time
    
    def move(self, action: ActionType, direction: Direction):
        """Update player movement state"""
        self.direction = direction
        
        if action == ActionType.MOVE and direction != Direction.NONE:
            speed = PLAYER_SPEED
            if direction == Direction.UP:
                self.y -= speed
            elif direction == Direction.DOWN:
                self.y += speed
            elif direction == Direction.LEFT:
                self.x -= speed
            elif direction == Direction.RIGHT:
                self.x += speed
            
            # Keep player within arena bounds
            self.x = max(0, min(ARENA_WIDTH - 40, self.x))
            self.y = max(0, min(ARENA_HEIGHT - 40, self.y))

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
    
    def start(self):
        """Start the game server"""
        self.socket.bind((SERVER_HOST, SERVER_PORT))
        self.socket.listen(MAX_PLAYERS)
        print(f"🎮 LAN Lords Server started on {SERVER_HOST}:{SERVER_PORT}")
        print(f"Waiting for players to connect...")
        
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
    
    def handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle communication with a single client"""
        player_id = None
        try:
            # Wait for connection message
            data = client_socket.recv(BUFFER_SIZE).decode('utf-8')
            if not data:
                return
            
            message = Message.from_json(data)
            
            if message.type == MessageType.CONNECT:
                player_name = message.data.get("name", f"Player")
                player_id = self.add_player(client_socket, address, player_name)
                
                if player_id is None:
                    return
                
                print(f"✅ Player {player_id} ({player_name}) joined!")
                
                # Send initial game state
                self.send_game_state(player_id)
                
                # Notify other players
                self.broadcast_player_joined(player_id)
                
                # Main message loop
                while self.running and player_id in self.players:
                    try:
                        data = client_socket.recv(BUFFER_SIZE).decode('utf-8')
                        if not data:
                            break
                        
                        message = Message.from_json(data)
                        self.handle_message(player_id, message)
                    except Exception as e:
                        print(f"Error handling message from player {player_id}: {e}")
                        break
        except Exception as e:
            print(f"Error in client handler: {e}")
        finally:
            if player_id:
                self.remove_player(player_id)
                client_socket.close()
                print(f"👋 Player {player_id} disconnected")
    
    def add_player(self, client_socket: socket.socket, address: Tuple[str, int], name: str) -> Optional[int]:
        """Add a new player to the game"""
        with self.lock:
            if len(self.players) >= MAX_PLAYERS:
                return None
            
            player_id = self.next_player_id
            self.next_player_id += 1
            
            # Spawn player at different positions based on ID
            spawn_positions = [
                (100, 100),
                (700, 100),
                (100, 500),
                (700, 500)
            ]
            spawn_idx = (player_id - 1) % len(spawn_positions)
            x, y = spawn_positions[spawn_idx]
            
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
            
            self.players[player_id] = player
            
            # Send player their own ID
            player_config = {
                "player_id": player_id,
                "name": name
            }
            config_msg = Message(MessageType.PLAYER_JOINED, player_config)
            try:
                client_socket.sendall(config_msg.to_json().encode('utf-8') + b'\n')
            except:
                pass
            
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
    
    def handle_player_input(self, player_id: int, data: Dict):
        """Handle player movement input"""
        with self.lock:
            if player_id not in self.players:
                return
            
            player = self.players[player_id]
            action = ActionType(data.get("action", "none"))
            direction = Direction(data.get("direction", "none"))
            
            player.move(action, direction)
            
            # Broadcast updated game state
            self.broadcast_game_state()
    
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
            self.players[player_id].conn.sendall(message.to_json().encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error sending game state to player {player_id}: {e}")
    
    def broadcast_game_state(self):
        """Send game state to all connected players"""
        game_state = self.get_game_state()
        message = Message(MessageType.GAME_STATE, game_state)
        
        to_remove = []
        for player_id, player in self.players.items():
            try:
                player.conn.sendall(message.to_json().encode('utf-8') + b'\n')
            except Exception as e:
                print(f"Error broadcasting to player {player_id}: {e}")
                to_remove.append(player_id)
        
        # Remove disconnected players
        for player_id in to_remove:
            self.remove_player(player_id)
    
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
        with self.lock:
            players_data = []
            for player_id, player in self.players.items():
                players_data.append({
                    "id": player.id,
                    "name": player.name,
                    "x": player.x,
                    "y": player.y,
                    "health": player.health,
                    "direction": player.direction.value,
                    "max_health": PLAYER_MAX_HEALTH
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

