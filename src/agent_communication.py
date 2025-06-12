#!/usr/bin/env python3
"""
Agent2Agent Communication Protocol Implementation
"""

import json
import time
import socket
import threading
import queue
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    """メッセージタイプ"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    COORDINATION = "coordination"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

@dataclass
class AgentMessage:
    """エージェント間メッセージ"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: float
    correlation_id: Optional[str] = None
    
    def to_json(self) -> str:
        data = asdict(self)
        data['message_type'] = self.message_type.value
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentMessage':
        data = json.loads(json_str)
        data['message_type'] = MessageType(data['message_type'])
        return cls(**data)

class UnixSocketChannel:
    """Unix Socket を使った通信チャネル"""
    
    def __init__(self, socket_path: str, is_server: bool = False):
        self.socket_path = socket_path
        self.is_server = is_server
        self.socket = None
        self.receive_queue = queue.Queue()
        self.is_running = False
        self.clients = []  # サーバーモードでのクライアント管理
        
        if is_server:
            self._start_server()
        else:
            self._connect_client()
            
    def _start_server(self):
        """サーバーソケットを開始"""
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
            
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.socket_path)
        self.socket.listen(5)
        self.is_running = True
        
        threading.Thread(target=self._accept_connections, daemon=True).start()
        logger.info(f"Unix socket server started at {self.socket_path}")
        
    def _accept_connections(self):
        """クライアント接続を受け付ける"""
        while self.is_running:
            try:
                client_socket, _ = self.socket.accept()
                self.clients.append(client_socket)
                threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                ).start()
            except Exception as e:
                if self.is_running:
                    logger.error(f"Accept error: {e}")
                    
    def _handle_client(self, client_socket):
        """クライアントからのメッセージを処理"""
        while self.is_running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                message = AgentMessage.from_json(data.decode())
                self.receive_queue.put(message)
                
                # ブロードキャスト処理
                if message.receiver_id == "broadcast":
                    self._broadcast_message(message, exclude_socket=client_socket)
                    
            except Exception as e:
                logger.error(f"Client handling error: {e}")
                break
                
        client_socket.close()
        self.clients.remove(client_socket)
        
    def _broadcast_message(self, message: AgentMessage, exclude_socket=None):
        """全クライアントにメッセージをブロードキャスト"""
        data = message.to_json().encode()
        for client in self.clients:
            if client != exclude_socket:
                try:
                    client.sendall(data)
                except:
                    pass
                    
    def _connect_client(self):
        """クライアントとして接続"""
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(self.socket_path)
        self.is_running = True
        
        threading.Thread(target=self._receive_messages, daemon=True).start()
        logger.info(f"Connected to Unix socket at {self.socket_path}")
        
    def _receive_messages(self):
        """メッセージを受信"""
        while self.is_running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                    
                message = AgentMessage.from_json(data.decode())
                self.receive_queue.put(message)
                
            except Exception as e:
                if self.is_running:
                    logger.error(f"Receive error: {e}")
                    
    def send(self, message: AgentMessage):
        """メッセージを送信"""
        if not self.socket:
            raise Exception("Socket not connected")
            
        data = message.to_json().encode()
        self.socket.sendall(data)
        
    def receive(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """メッセージを受信"""
        try:
            return self.receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None
            
    def close(self):
        """接続を閉じる"""
        self.is_running = False
        if self.socket:
            self.socket.close()
        if self.is_server and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

class Agent2AgentProtocol:
    """Agent2Agentプロトコルの実装"""
    
    def __init__(self, agent_id: str, channel: UnixSocketChannel):
        self.agent_id = agent_id
        self.channel = channel
        self.pending_requests: Dict[str, AgentMessage] = {}
        self.response_handlers: Dict[str, Callable] = {}
        self.message_handlers: Dict[MessageType, Callable] = {}
        
    def register_handler(self, message_type: MessageType, handler: Callable):
        """メッセージハンドラーを登録"""
        self.message_handlers[message_type] = handler
        
    def send_task_request(
        self,
        receiver_id: str,
        task: Dict[str, Any],
        callback: Optional[Callable] = None
    ) -> str:
        """タスクリクエストを送信"""
        message_id = f"{self.agent_id}_{int(time.time()*1000)}"
        
        message = AgentMessage(
            message_id=message_id,
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            message_type=MessageType.TASK_REQUEST,
            payload=task,
            timestamp=time.time()
        )
        
        self.pending_requests[message_id] = message
        if callback:
            self.response_handlers[message_id] = callback
            
        self.channel.send(message)
        return message_id
        
    def send_task_response(
        self,
        request_message: AgentMessage,
        result: Dict[str, Any]
    ):
        """タスクレスポンスを送信"""
        response = AgentMessage(
            message_id=f"{self.agent_id}_{int(time.time()*1000)}",
            sender_id=self.agent_id,
            receiver_id=request_message.sender_id,
            message_type=MessageType.TASK_RESPONSE,
            payload=result,
            timestamp=time.time(),
            correlation_id=request_message.message_id
        )
        
        self.channel.send(response)
        
    def process_messages(self):
        """受信メッセージを処理"""
        message = self.channel.receive(timeout=0.1)
        if not message:
            return
            
        if message.message_type == MessageType.TASK_RESPONSE:
            if message.correlation_id in self.response_handlers:
                handler = self.response_handlers[message.correlation_id]
                handler(message)
                del self.response_handlers[message.correlation_id]
                del self.pending_requests[message.correlation_id]
                
        elif message.message_type in self.message_handlers:
            handler = self.message_handlers[message.message_type]
            handler(message)