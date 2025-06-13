"""
Unit tests for the protocol module
"""

import pytest
import json
import time
import socket
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

from conductor.protocol import (
    AgentMessage, MessageType, UnixSocketChannel, AgentProtocol,
    ProtocolError
)


class TestMessageType:
    """Test cases for MessageType enum"""
    
    def test_message_types_exist(self):
        """Test that all required message types exist"""
        assert hasattr(MessageType, 'TASK_REQUEST')
        assert hasattr(MessageType, 'TASK_RESPONSE')
        assert hasattr(MessageType, 'HEALTH_CHECK')
        assert hasattr(MessageType, 'AGENT_STATUS')
        assert hasattr(MessageType, 'SHUTDOWN')


class TestAgentMessage:
    """Test cases for AgentMessage class"""
    
    def test_message_creation(self):
        """Test basic message creation"""
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
            timestamp=1234567890.0
        )
        
        assert message.message_id == "msg_001"
        assert message.sender_id == "agent_001"
        assert message.receiver_id == "agent_002"
        assert message.message_type == MessageType.TASK_REQUEST
        assert message.payload == {"task": "test"}
        assert message.timestamp == 1234567890.0
        assert message.correlation_id is None
    
    def test_message_with_correlation_id(self):
        """Test message creation with correlation ID"""
        message = AgentMessage(
            message_id="msg_002",
            sender_id="agent_002",
            receiver_id="agent_001",
            message_type=MessageType.TASK_RESPONSE,
            payload={"result": "success"},
            timestamp=1234567891.0,
            correlation_id="msg_001"
        )
        
        assert message.correlation_id == "msg_001"
    
    def test_message_to_dict(self):
        """Test message serialization to dict"""
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
            timestamp=1234567890.0
        )
        
        data = message.to_dict()
        
        assert data["message_id"] == "msg_001"
        assert data["sender_id"] == "agent_001"
        assert data["receiver_id"] == "agent_002"
        assert data["message_type"] == MessageType.TASK_REQUEST.value
        assert data["payload"] == {"task": "test"}
        assert data["timestamp"] == 1234567890.0
    
    def test_message_from_dict(self):
        """Test message deserialization from dict"""
        data = {
            "message_id": "msg_001",
            "sender_id": "agent_001",
            "receiver_id": "agent_002",
            "message_type": "task_request",
            "payload": {"task": "test"},
            "timestamp": 1234567890.0,
            "correlation_id": "msg_000"
        }
        
        message = AgentMessage.from_dict(data)
        
        assert message.message_id == "msg_001"
        assert message.sender_id == "agent_001"
        assert message.receiver_id == "agent_002"
        assert message.message_type == MessageType.TASK_REQUEST
        assert message.payload == {"task": "test"}
        assert message.timestamp == 1234567890.0
        assert message.correlation_id == "msg_000"
    
    def test_message_to_json(self):
        """Test message JSON serialization"""
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
            timestamp=1234567890.0
        )
        
        json_str = message.to_json()
        data = json.loads(json_str)
        
        assert data["message_id"] == "msg_001"
        assert data["message_type"] == "task_request"
    
    def test_message_from_json(self):
        """Test message JSON deserialization"""
        json_str = '''
        {
            "message_id": "msg_001",
            "sender_id": "agent_001",
            "receiver_id": "agent_002",
            "message_type": "task_request",
            "payload": {"task": "test"},
            "timestamp": 1234567890.0
        }
        '''
        
        message = AgentMessage.from_json(json_str)
        
        assert message.message_id == "msg_001"
        assert message.message_type == MessageType.TASK_REQUEST
        assert message.payload == {"task": "test"}


class TestUnixSocketChannel:
    """Test cases for UnixSocketChannel class"""
    
    def test_channel_initialization(self, temp_dir):
        """Test channel initialization"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        assert channel.socket_path == socket_path
        assert channel.socket is None
        assert channel.is_server is False
        assert channel.connections == []
    
    @patch('socket.socket')
    def test_start_server(self, mock_socket_class, temp_dir):
        """Test starting server"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        
        channel.start_server()
        
        assert channel.is_server is True
        assert channel.socket == mock_socket
        mock_socket.bind.assert_called_with(socket_path)
        mock_socket.listen.assert_called_once()
    
    @patch('socket.socket')
    def test_connect_client(self, mock_socket_class, temp_dir):
        """Test client connection"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket
        
        channel.connect()
        
        assert channel.is_server is False
        assert channel.socket == mock_socket
        mock_socket.connect.assert_called_with(socket_path)
    
    def test_send_message(self, temp_dir):
        """Test sending message"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        mock_socket = MagicMock()
        channel.socket = mock_socket
        
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
            timestamp=time.time()
        )
        
        channel.send_message(message)
        
        mock_socket.sendall.assert_called_once()
        sent_data = mock_socket.sendall.call_args[0][0]
        assert b'\n' in sent_data  # Should end with newline
    
    def test_receive_message(self, temp_dir):
        """Test receiving message"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        mock_socket = MagicMock()
        channel.socket = mock_socket
        
        # Mock receiving JSON data
        json_data = json.dumps({
            "message_id": "msg_001",
            "sender_id": "agent_001",
            "receiver_id": "agent_002",
            "message_type": "task_request",
            "payload": {"task": "test"},
            "timestamp": 1234567890.0
        })
        
        mock_socket.recv.return_value = (json_data + "\n").encode()
        
        message = channel.receive_message()
        
        assert message.message_id == "msg_001"
        assert message.message_type == MessageType.TASK_REQUEST
    
    def test_receive_message_timeout(self, temp_dir):
        """Test message receive timeout"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        mock_socket = MagicMock()
        mock_socket.recv.side_effect = socket.timeout()
        channel.socket = mock_socket
        
        message = channel.receive_message(timeout=0.1)
        assert message is None
    
    def test_close_channel(self, temp_dir):
        """Test closing channel"""
        socket_path = f"{temp_dir}/test.sock"
        channel = UnixSocketChannel(socket_path)
        
        mock_socket = MagicMock()
        channel.socket = mock_socket
        
        # Add mock connections
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        channel.connections = [mock_conn1, mock_conn2]
        
        with patch('os.unlink') as mock_unlink:
            channel.close()
        
        # Should close all connections
        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_called_once()
        
        # Should close main socket
        mock_socket.close.assert_called_once()
        
        # Should clean up socket file
        mock_unlink.assert_called_with(socket_path)


class TestAgentProtocol:
    """Test cases for AgentProtocol class"""
    
    def test_protocol_initialization(self, temp_dir):
        """Test protocol initialization"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        assert protocol.agent_id == "agent_001"
        assert protocol.socket_path == socket_path
        assert protocol.channel is not None
        assert protocol.message_handlers == {}
    
    def test_register_handler(self, temp_dir):
        """Test registering message handler"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        def test_handler(message):
            return "handled"
        
        protocol.register_handler(MessageType.TASK_REQUEST, test_handler)
        
        assert MessageType.TASK_REQUEST in protocol.message_handlers
        assert protocol.message_handlers[MessageType.TASK_REQUEST] == test_handler
    
    def test_send_task_request(self, temp_dir):
        """Test sending task request"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        mock_channel = MagicMock()
        protocol.channel = mock_channel
        
        task_data = {
            "task_id": "task_001",
            "task_type": "code_review",
            "files": ["test.py"]
        }
        
        with patch('conductor.protocol.generate_message_id') as mock_gen_id:
            mock_gen_id.return_value = "msg_001"
            
            protocol.send_task_request("agent_002", task_data)
        
        mock_channel.send_message.assert_called_once()
        sent_message = mock_channel.send_message.call_args[0][0]
        
        assert sent_message.sender_id == "agent_001"
        assert sent_message.receiver_id == "agent_002"
        assert sent_message.message_type == MessageType.TASK_REQUEST
        assert sent_message.payload == task_data
    
    def test_send_task_response(self, temp_dir):
        """Test sending task response"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        mock_channel = MagicMock()
        protocol.channel = mock_channel
        
        result_data = {
            "task_id": "task_001",
            "status": "success",
            "result": {"issues": 3}
        }
        
        with patch('conductor.protocol.generate_message_id') as mock_gen_id:
            mock_gen_id.return_value = "msg_002"
            
            protocol.send_task_response("agent_002", result_data, "msg_001")
        
        mock_channel.send_message.assert_called_once()
        sent_message = mock_channel.send_message.call_args[0][0]
        
        assert sent_message.message_type == MessageType.TASK_RESPONSE
        assert sent_message.correlation_id == "msg_001"
        assert sent_message.payload == result_data
    
    def test_handle_message(self, temp_dir):
        """Test handling incoming message"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        # Register handler
        handled_messages = []
        def test_handler(message):
            handled_messages.append(message)
        
        protocol.register_handler(MessageType.TASK_REQUEST, test_handler)
        
        # Create test message
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_002",
            receiver_id="agent_001",
            message_type=MessageType.TASK_REQUEST,
            payload={"task": "test"},
            timestamp=time.time()
        )
        
        protocol._handle_message(message)
        
        assert len(handled_messages) == 1
        assert handled_messages[0] == message
    
    def test_handle_unknown_message_type(self, temp_dir):
        """Test handling unknown message type"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        # Create message with unregistered type
        message = AgentMessage(
            message_id="msg_001",
            sender_id="agent_002",
            receiver_id="agent_001",
            message_type=MessageType.HEALTH_CHECK,  # No handler registered
            payload={},
            timestamp=time.time()
        )
        
        # Should not raise exception
        protocol._handle_message(message)
    
    def test_start_listening(self, temp_dir):
        """Test starting message listener"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        mock_channel = MagicMock()
        protocol.channel = mock_channel
        
        # Mock receiving messages
        messages = [
            AgentMessage("msg_001", "agent_002", "agent_001", 
                        MessageType.HEALTH_CHECK, {}, time.time()),
            None  # Timeout
        ]
        mock_channel.receive_message.side_effect = messages
        
        with patch('threading.Thread') as mock_thread:
            protocol.start_listening()
            
            mock_thread.assert_called_once()
    
    def test_stop_listening(self, temp_dir):
        """Test stopping message listener"""
        socket_path = f"{temp_dir}/test.sock"
        protocol = AgentProtocol("agent_001", socket_path)
        
        protocol.listening = True
        mock_channel = MagicMock()
        protocol.channel = mock_channel
        
        protocol.stop_listening()
        
        assert protocol.listening is False
        mock_channel.close.assert_called_once()


class TestProtocolUtilities:
    """Test cases for protocol utilities"""
    
    def test_generate_message_id(self):
        """Test message ID generation"""
        from conductor.protocol import generate_message_id
        
        msg_id1 = generate_message_id()
        msg_id2 = generate_message_id()
        
        assert msg_id1 != msg_id2
        assert len(msg_id1) > 0
        assert len(msg_id2) > 0
    
    def test_protocol_error(self):
        """Test ProtocolError exception"""
        with pytest.raises(ProtocolError):
            raise ProtocolError("Test error")