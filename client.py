"""
LAN Lords Client
Handles player input, rendering, and network communication with server
"""

import pygame
import socket
import threading
import time
from typing import Dict, List, Optional

from protocol import Message, MessageType, ActionType, Direction
from config import (
    ARENA_WIDTH, ARENA_HEIGHT, SERVER_PORT,
    PLAYER_COLORS, PLAYER_SIZE, PLAYER_MAX_HEALTH
)

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
FPS = 60

class GameClient:
    """Main client class that handles connection and rendering"""
    
    def __init__(self):
        self.socket = None
        self.server_address = None
        self.player_id = None
        self.players: Dict[int, Dict] = {}
        self.running = False
        self.lock = threading.Lock()
        self.screen = None
        self.clock = None
        self.connected = False
        
        # Input state
        self.keys_pressed = set()
        self.chat_active = False
        self.chat_input = ""
        self.chat_messages: List[Dict] = []
        
        # Attack state
        self.last_attack_time = 0
        self.attack_cooldown = 1.0
        self.showing_attack = False
        self.attack_start_time = 0
        
        # Scene state
        self.scene = "menu"  # "menu" or "game"
        
        # Menu inputs
        self.menu_name = "Player"
        self.menu_ip = "127.0.0.1"
        self.menu_focus = "name"  # "name" or "ip" or "button"

        # Sync state
        self.received_first_state = False
        self.last_state_request_time = 0.0
    
    def connect(self, server_ip: str, player_name: str) -> bool:
        """Connect to the game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, SERVER_PORT))
            
            # Send connection message
            connect_msg = Message(MessageType.CONNECT, {"name": player_name})
            self.socket.sendall(connect_msg.to_json().encode('utf-8') + b'\n')
            print("➡️  Sent CONNECT message")
            
            self.server_address = server_ip
            self.player_name = player_name
            
            # Start receiver thread
            self.connected = True
            receiver_thread = threading.Thread(target=self.receive_loop)
            receiver_thread.daemon = True
            receiver_thread.start()
            
            print(f"✅ Connected to server at {server_ip}:{SERVER_PORT}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def receive_loop(self):
        """Receive messages from server"""
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        # Debug: print first 60 chars of message
                        self.handle_message(line)
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
        
        self.connected = False
        self.running = False
    
    def handle_message(self, json_str: str):
        """Handle incoming message from server"""
        try:
            message = Message.from_json(json_str)
            
            if message.type == MessageType.GAME_STATE:
                with self.lock:
                    # Update player data
                    for player_data in message.data.get("players", []):
                        self.players[player_data["id"]] = player_data
                    
                    # Update chat
                    self.chat_messages = message.data.get("chat", [])
                    self.received_first_state = True
            
            elif message.type == MessageType.PLAYER_JOINED:
                # Check if this is our own join message with ID assignment
                if "player_id" in message.data:
                    with self.lock:
                        self.player_id = message.data.get("player_id")
                        print(f"✅ Your ID is {self.player_id}")
                else:
                    print(f"✅ Player joined: {message.data.get('name')}")
            
            if message.type == MessageType.GAME_STATE:
                with self.lock:
                    # Update player data
                    for player_data in message.data.get("players", []):
                        self.players[player_data["id"]] = player_data
                    
                    # Update chat
                    self.chat_messages = message.data.get("chat", [])
                    self.received_first_state = True
            
            elif message.type == MessageType.PLAYER_LEFT:
                player_id = message.data.get("player_id")
                with self.lock:
                    self.players.pop(player_id, None)
        
        except Exception as e:
            print(f"Error handling message: {e}")
    
    def send_input(self, action: ActionType, direction: Direction):
        """Send player input to server"""
        if not self.socket or self.player_id is None:
            return
        
        message = Message(MessageType.PLAYER_INPUT, {
            "player_id": self.player_id,
            "action": action.value,
            "direction": direction.value
        })
        
        try:
            self.socket.sendall(message.to_json().encode('utf-8') + b'\n')
        except:
            pass
    
    def send_attack(self, direction: Direction):
        """Send attack to server"""
        if not self.socket or self.player_id is None:
            return
        
        current_time = time.time()
        if current_time - self.last_attack_time < self.attack_cooldown:
            return
        
        self.last_attack_time = current_time
        self.showing_attack = True
        self.attack_start_time = current_time
        
        message = Message(MessageType.ATTACK, {
            "player_id": self.player_id,
            "direction": direction.value
        })
        
        try:
            self.socket.sendall(message.to_json().encode('utf-8') + b'\n')
        except:
            pass
    
    def send_chat_message(self, text: str):
        """Send chat message to server"""
        if not self.socket or self.player_id is None:
            return
        
        message = Message(MessageType.CHAT_MESSAGE, {
            "player_id": self.player_id,
            "text": text
        })
        
        try:
            self.socket.sendall(message.to_json().encode('utf-8') + b'\n')
        except:
            pass
    
    def run(self):
        """Main game loop"""
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("LAN Lords")
        self.clock = pygame.time.Clock()
        
        self.running = True
        
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        
        pygame.quit()
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Menu scene event handling
            if self.scene == "menu":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_TAB:
                        # Cycle focus
                        if self.menu_focus == "name":
                            self.menu_focus = "ip"
                        elif self.menu_focus == "ip":
                            self.menu_focus = "button"
                        else:
                            self.menu_focus = "name"
                    elif event.key == pygame.K_RETURN:
                        if self.menu_focus in ("name", "ip"):
                            # Pressing enter from fields triggers connect
                            self.try_connect_from_menu()
                        else:
                            self.try_connect_from_menu()
                    elif event.key == pygame.K_BACKSPACE:
                        if self.menu_focus == "name" and len(self.menu_name) > 0:
                            self.menu_name = self.menu_name[:-1]
                        elif self.menu_focus == "ip" and len(self.menu_ip) > 0:
                            self.menu_ip = self.menu_ip[:-1]
                    else:
                        if self.menu_focus == "name":
                            if event.unicode and event.unicode.isprintable():
                                self.menu_name += event.unicode
                        elif self.menu_focus == "ip":
                            if event.unicode and event.unicode.isprintable():
                                self.menu_ip += event.unicode
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = pygame.mouse.get_pos()
                    # Determine UI element bounds
                    name_rect = pygame.Rect(WINDOW_WIDTH//2 - 150, 260, 300, 36)
                    ip_rect = pygame.Rect(WINDOW_WIDTH//2 - 150, 320, 300, 36)
                    btn_rect = pygame.Rect(WINDOW_WIDTH//2 - 80, 380, 160, 44)
                    if name_rect.collidepoint(mx, my):
                        self.menu_focus = "name"
                    elif ip_rect.collidepoint(mx, my):
                        self.menu_focus = "ip"
                    elif btn_rect.collidepoint(mx, my):
                        self.menu_focus = "button"
                        self.try_connect_from_menu()
                return
            
            elif event.type == pygame.KEYDOWN and self.scene == "game":
                if self.chat_active:
                    if event.key == pygame.K_RETURN:
                        if self.chat_input:
                            self.send_chat_message(self.chat_input)
                            self.chat_input = ""
                        self.chat_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.chat_input = self.chat_input[:-1]
                    else:
                        self.chat_input += event.unicode
                else:
                    if event.key == pygame.K_RETURN:
                        self.chat_active = True
                    elif event.key == pygame.K_SPACE:
                        self.handle_attack()
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
            elif event.type == pygame.KEYUP and self.scene == "game":
                if event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    # Reset crouching when down key released
                    with self.lock:
                        for player_data in self.players.values():
                            if player_data.get("id") == self.player_id:
                                player_data["is_crouching"] = False
                                break
    
    def handle_attack(self):
        """Handle attack input"""
        if self.player_id is None or self.player_id not in self.players:
            return
        
        # Get current velocity-based direction
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            direction = Direction.LEFT
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            direction = Direction.RIGHT
        elif keys[pygame.K_UP] or keys[pygame.K_w]:
            direction = Direction.UP
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            direction = Direction.DOWN
        else:
            # Use last facing direction
            player = self.players[self.player_id]
            direction = Direction(player.get("direction", "right"))
        
        self.send_attack(direction)
    
    def update(self):
        """Update game state"""
        if self.scene == "menu":
            return
        
        # If connected but haven't received state, request it periodically
        if self.connected and not self.received_first_state:
            now = time.time()
            if now - self.last_state_request_time > 0.5 and self.player_id is not None:
                try:
                    msg = Message(MessageType.REQUEST_STATE, {"player_id": self.player_id})
                    self.socket.sendall(msg.to_json().encode('utf-8') + b'\n')
                    self.last_state_request_time = now
                    print("➡️  Requested GAME_STATE")
                except Exception as e:
                    print(f"Failed to request state: {e}")
        
        # Handle keyboard input (only skip if chat is active)
        if not self.chat_active:
            keys = pygame.key.get_pressed()
            
            # Movement
            direction = Direction.NONE
            action = ActionType.NONE
            
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                direction = Direction.UP
                action = ActionType.MOVE
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                direction = Direction.DOWN
                action = ActionType.MOVE
            elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
                direction = Direction.LEFT
                action = ActionType.MOVE
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                direction = Direction.RIGHT
                action = ActionType.MOVE
            
            if action != ActionType.NONE:
                self.send_input(action, direction)
        
        # Update attack animation
        if self.showing_attack:
            if time.time() - self.attack_start_time > 0.2:
                self.showing_attack = False
    
    def render(self):
        """Render game screen"""
        self.screen.fill((20, 20, 30))
        
        if self.scene == "menu":
            self.render_menu()
            pygame.display.flip()
            return
        
        # Draw arena background with simple platforms
        arena_rect = pygame.Rect(50, 50, ARENA_WIDTH, ARENA_HEIGHT)
        pygame.draw.rect(self.screen, (40, 40, 50), arena_rect)
        pygame.draw.rect(self.screen, (60, 60, 80), arena_rect, 3)
        
        # Platforms (basic smash-like layout)
        platform_color = (80, 90, 120)
        base_platform = pygame.Rect(50 + 80, 50 + ARENA_HEIGHT - 80, ARENA_WIDTH - 160, 20)
        left_platform = pygame.Rect(50 + 120, 50 + ARENA_HEIGHT - 220, 180, 18)
        right_platform = pygame.Rect(50 + ARENA_WIDTH - 300, 50 + ARENA_HEIGHT - 220, 180, 18)
        top_platform = pygame.Rect(50 + ARENA_WIDTH//2 - 120, 50 + 120, 240, 16)
        for rect in (base_platform, left_platform, right_platform, top_platform):
            pygame.draw.rect(self.screen, platform_color, rect, border_radius=4)
        
        # Draw players
        with self.lock:
            for player_id, player_data in self.players.items():
                x = int(player_data.get("x", 0))
                y = int(player_data.get("y", 0))
                health = player_data.get("health", 0)
                max_health = player_data.get("max_health", PLAYER_MAX_HEALTH)
                direction = player_data.get("direction", "none")
                
                # Offset to arena position
                screen_x = 50 + x
                screen_y = 50 + y
                
                # Draw player
                player_color = PLAYER_COLORS[(player_id - 1) % len(PLAYER_COLORS)]
                
                # Check if crouching
                is_crouching = player_data.get("is_crouching", False)
                
                if player_id == self.player_id:
                    # Highlight own player
                    pygame.draw.circle(self.screen, player_color, 
                                     (screen_x + 20, screen_y + 20), 
                                     PLAYER_SIZE // 2 + 2)
                
                # Draw player (squished if crouching)
                player_height = PLAYER_SIZE if not is_crouching else PLAYER_SIZE // 2
                player_y = screen_y + 20 if not is_crouching else screen_y + 40
                pygame.draw.circle(self.screen, player_color, 
                                 (screen_x + 20, player_y), 
                                 player_height // 2)
                
                # Draw health bar
                bar_width = PLAYER_SIZE
                bar_height = 5
                bar_x = screen_x
                bar_y = screen_y - 10
                
                # Background
                pygame.draw.rect(self.screen, (100, 0, 0), 
                               (bar_x, bar_y, bar_width, bar_height))
                
                # Health
                health_ratio = health / max_health
                health_width = int(bar_width * health_ratio)
                health_color = (int(255 * (1 - health_ratio)), int(255 * health_ratio), 0)
                pygame.draw.rect(self.screen, health_color, 
                               (bar_x, bar_y, health_width, bar_height))
                
                # Draw direction indicator
                self.draw_direction_indicator(screen_x + 20, screen_y + 20, direction)
                
                # Draw player name
                font = pygame.font.Font(None, 20)
                name_text = font.render(player_data.get("name", "Player"), True, player_color)
                name_rect = name_text.get_rect(center=(screen_x + 20, screen_y - 25))
                self.screen.blit(name_text, name_rect)
        
        # Draw chat
        self.draw_chat()
        
        # Draw control instructions
        self.draw_instructions()
        
        # Draw chat input
        if self.chat_active:
            self.draw_chat_input()
        
        # Draw attack animation
        if self.showing_attack:
            self.draw_attack_animation()
        
        pygame.display.flip()
    
    def draw_direction_indicator(self, x: int, y: int, direction: str):
        """Draw a small indicator showing player direction"""
        if direction == "none":
            return
        
        arrow_size = 8
        if direction == "up":
            pygame.draw.polygon(self.screen, (255, 255, 255), 
                             [(x, y - arrow_size - 15), 
                              (x - arrow_size // 2, y - arrow_size // 2 - 15),
                              (x + arrow_size // 2, y - arrow_size // 2 - 15)])
        elif direction == "down":
            pygame.draw.polygon(self.screen, (255, 255, 255), 
                             [(x, y + arrow_size + 15), 
                              (x - arrow_size // 2, y + arrow_size // 2 + 15),
                              (x + arrow_size // 2, y + arrow_size // 2 + 15)])
        elif direction == "left":
            pygame.draw.polygon(self.screen, (255, 255, 255), 
                             [(x - arrow_size - 15, y), 
                              (x - arrow_size // 2 - 15, y - arrow_size // 2),
                              (x - arrow_size // 2 - 15, y + arrow_size // 2)])
        elif direction == "right":
            pygame.draw.polygon(self.screen, (255, 255, 255), 
                             [(x + arrow_size + 15, y), 
                              (x + arrow_size // 2 + 15, y - arrow_size // 2),
                              (x + arrow_size // 2 + 15, y + arrow_size // 2)])
    
    def draw_chat(self):
        """Draw chat messages"""
        font = pygame.font.Font(None, 20)
        y_offset = WINDOW_HEIGHT - 150
        
        # Draw chat background
        chat_bg = pygame.Rect(50, y_offset - 10, 400, 120)
        pygame.draw.rect(self.screen, (0, 0, 0, 128), chat_bg)
        pygame.draw.rect(self.screen, (100, 100, 100), chat_bg, 1)
        
        # Draw chat messages
        with self.lock:
            messages_to_show = self.chat_messages[-5:] if self.chat_messages else []
        
        for i, msg_data in enumerate(messages_to_show):
            text = msg_data.get("text", "")
            is_system = msg_data.get("is_system", False)
            
            color = (150, 150, 200) if is_system else (220, 220, 220)
            try:
                if text:  # Only render non-empty text
                    text_surface = font.render(str(text), True, color)
                    self.screen.blit(text_surface, (60, y_offset + i * 22))
            except Exception as e:
                print(f"Chat render error: {e}")
    
    def draw_instructions(self):
        """Draw control instructions"""
        font = pygame.font.Font(None, 20)
        instructions = [
            "Controls:",
            "Arrow Keys / WASD: Move",
            "Space: Attack",
            "Enter: Chat",
            "Esc: Exit"
        ]
        
        for i, text in enumerate(instructions):
            text_surface = font.render(text, True, (150, 150, 150))
            self.screen.blit(text_surface, (900, 60 + i * 25))
    
    def draw_chat_input(self):
        """Draw chat input box"""
        font = pygame.font.Font(None, 24)
        input_text = f"> {self.chat_input}_"
        text_surface = font.render(input_text, True, (255, 255, 255))
        
        # Draw background
        pygame.draw.rect(self.screen, (50, 50, 50), 
                        (50, WINDOW_HEIGHT - 100, WINDOW_WIDTH - 100, 30))
        
        self.screen.blit(text_surface, (60, WINDOW_HEIGHT - 95))
    
    def draw_attack_animation(self):
        """Draw attack animation"""
        # This will be shown as a visual effect on the attacking player
        if self.player_id and self.player_id in self.players:
            player = self.players[self.player_id]
            x = int(50 + player.get("x", 0) + 20)
            y = int(50 + player.get("y", 0) + 20)
            direction = Direction(player.get("direction", "none"))
            
            # Draw attack range indicator
            attack_range = 60
            attack_color = (255, 200, 0)
            
            elapsed = time.time() - self.attack_start_time
            alpha = int(255 * (1 - elapsed / 0.2))
            
            attack_color = (min(255, attack_color[0]), 
                          min(255, attack_color[1]), 
                          min(255, attack_color[2]))
            
            if elapsed < 0.2:
                if direction == Direction.UP:
                    pygame.draw.line(self.screen, attack_color, (x, y - 20), (x, y - 50), 5)
                elif direction == Direction.DOWN:
                    pygame.draw.line(self.screen, attack_color, (x, y + 20), (x, y + 70), 5)
                elif direction == Direction.LEFT:
                    pygame.draw.line(self.screen, attack_color, (x - 20, y), (x - 50, y), 5)
                elif direction == Direction.RIGHT:
                    pygame.draw.line(self.screen, attack_color, (x + 20, y), (x + 70, y), 5)

    def render_menu(self):
        """Render the start menu with name/IP input and Connect button"""
        title_font = pygame.font.Font(None, 64)
        label_font = pygame.font.Font(None, 28)
        input_font = pygame.font.Font(None, 32)
        btn_font = pygame.font.Font(None, 32)
        
        # Title
        title = title_font.render("LAN Lords", True, (230, 230, 255))
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH//2, 160)))
        
        # Labels
        name_label = label_font.render("Name", True, (180, 180, 200))
        ip_label = label_font.render("Server IP", True, (180, 180, 200))
        self.screen.blit(name_label, (WINDOW_WIDTH//2 - 150, 235))
        self.screen.blit(ip_label, (WINDOW_WIDTH//2 - 150, 295))
        
        # Inputs
        name_rect = pygame.Rect(WINDOW_WIDTH//2 - 150, 260, 300, 36)
        ip_rect = pygame.Rect(WINDOW_WIDTH//2 - 150, 320, 300, 36)
        btn_rect = pygame.Rect(WINDOW_WIDTH//2 - 80, 380, 160, 44)
        
        pygame.draw.rect(self.screen, (50, 50, 70), name_rect, border_radius=6)
        pygame.draw.rect(self.screen, (50, 50, 70), ip_rect, border_radius=6)
        
        # Focus outlines
        if self.menu_focus == "name":
            pygame.draw.rect(self.screen, (120, 160, 255), name_rect, 2, border_radius=6)
        else:
            pygame.draw.rect(self.screen, (90, 90, 110), name_rect, 2, border_radius=6)
        if self.menu_focus == "ip":
            pygame.draw.rect(self.screen, (120, 160, 255), ip_rect, 2, border_radius=6)
        else:
            pygame.draw.rect(self.screen, (90, 90, 110), ip_rect, 2, border_radius=6)
        
        # Text in inputs
        name_text = input_font.render(self.menu_name, True, (230, 230, 240))
        ip_text = input_font.render(self.menu_ip, True, (230, 230, 240))
        self.screen.blit(name_text, (name_rect.x + 8, name_rect.y + 6))
        self.screen.blit(ip_text, (ip_rect.x + 8, ip_rect.y + 6))
        
        # Connect button
        btn_color = (80, 120, 255) if self.menu_focus == "button" else (70, 90, 130)
        pygame.draw.rect(self.screen, btn_color, btn_rect, border_radius=8)
        btn_label = btn_font.render("Connect", True, (255, 255, 255))
        self.screen.blit(btn_label, btn_label.get_rect(center=btn_rect.center))
        
        # Footer
        footer = label_font.render("Tab to switch fields • Enter to connect", True, (140, 140, 160))
        self.screen.blit(footer, footer.get_rect(center=(WINDOW_WIDTH//2, 450)))

    def try_connect_from_menu(self):
        """Attempt to connect using menu inputs and switch to game scene on success"""
        name = self.menu_name.strip() or "Player"
        ip = self.menu_ip.strip() or "127.0.0.1"
        ok = self.connect(ip, name)
        if ok:
            self.scene = "game"

def main():
    """Main entry point"""
    client = GameClient()
    client.run()

if __name__ == "__main__":
    main()

