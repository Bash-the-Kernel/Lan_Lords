"""
Protocol Definitions for LAN Lords
Defines message structure and serialization for client-server communication
"""

import json
from enum import Enum
from typing import Dict, List, Any, Optional

class MessageType(Enum):
    """Message types for client-server communication"""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PLAYER_INPUT = "player_input"
    GAME_STATE = "game_state"
    CHAT_MESSAGE = "chat_message"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    ATTACK = "attack"
    ATTACK_RESULT = "attack_result"
    DAMAGE = "damage"
    REQUEST_STATE = "request_state"

class ActionType(Enum):
    """Player action types"""
    MOVE = "move"
    STOP = "stop"
    ATTACK = "attack"
    NONE = "none"

class Direction(Enum):
    """Movement directions"""
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    NONE = "none"

class Message:
    """Message wrapper for network communication"""
    
    def __init__(self, msg_type: MessageType, data: Dict[str, Any]):
        self.type = msg_type
        self.data = data
    
    def to_json(self) -> str:
        """Serialize message to JSON"""
        return json.dumps({
            "type": self.type.value,
            "data": self.data
        })
    
    @staticmethod
    def from_json(json_str: str) -> 'Message':
        """Deserialize message from JSON"""
        try:
            obj = json.loads(json_str)
            msg_type = MessageType(obj["type"])
            return Message(msg_type, obj["data"])
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid message format: {e}")
    
    def __str__(self):
        return f"Message(type={self.type.value}, data={self.data})"

def create_connect_message(name: str) -> Message:
    """Create a player connect message"""
    return Message(MessageType.CONNECT, {"name": name})

def create_player_input(player_id: int, action: ActionType, direction: Direction) -> Message:
    """Create a player input message"""
    return Message(MessageType.PLAYER_INPUT, {
        "player_id": player_id,
        "action": action.value,
        "direction": direction.value
    })

def create_attack_message(player_id: int, direction: Direction) -> Message:
    """Create an attack message"""
    return Message(MessageType.ATTACK, {
        "player_id": player_id,
        "direction": direction.value
    })

def create_chat_message(player_id: int, text: str) -> Message:
    """Create a chat message"""
    return Message(MessageType.CHAT_MESSAGE, {
        "player_id": player_id,
        "text": text
    })

def create_game_state_message(game_state: Dict[str, Any]) -> Message:
    """Create a game state broadcast message"""
    return Message(MessageType.GAME_STATE, game_state)

def create_request_state_message(player_id: int) -> Message:
    """Create a request for current game state"""
    return Message(MessageType.REQUEST_STATE, {"player_id": player_id})

def create_disconnect_message(player_id: int) -> Message:
    """Create a disconnect message"""
    return Message(MessageType.DISCONNECT, {"player_id": player_id})

