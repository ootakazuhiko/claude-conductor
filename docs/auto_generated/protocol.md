# protocol

Agent2Agent Communication Protocol Implementation

## Classes

### MessageType

**Inherits from:** Enum

メッセージタイプ

### AgentMessage

エージェント間メッセージ

#### Attributes

- `message_id` (str)
- `sender_id` (str)
- `receiver_id` (str)
- `message_type` (MessageType)
- `payload` (Dict[(str, Any)])
- `timestamp` (float)
- `correlation_id` (Optional[str])

#### Methods

##### to_json

`to_json()` -> str

##### from_json

`from_json(cls, json_str: str)` -> 'AgentMessage'

**Parameters:**
- `cls`
- `json_str` (str)

### UnixSocketChannel

Unix Socket を使った通信チャネル

#### Methods

##### send

`send(message: AgentMessage)`

メッセージを送信

**Parameters:**
- `message` (AgentMessage)

##### receive

`receive(timeout: Optional[float] = None)` -> Optional[AgentMessage]

メッセージを受信

**Parameters:**
- `timeout` (Optional[float]) = None

##### close

`close()`

接続を閉じる

### Agent2AgentProtocol

Agent2Agentプロトコルの実装

#### Methods

##### register_handler

`register_handler(message_type: MessageType, handler: Callable)`

メッセージハンドラーを登録

**Parameters:**
- `message_type` (MessageType)
- `handler` (Callable)

##### send_task_request

`send_task_request(receiver_id: str, task: Dict[(str, Any)], callback: Optional[Callable] = None)` -> str

タスクリクエストを送信

**Parameters:**
- `receiver_id` (str)
- `task` (Dict[(str, Any)])
- `callback` (Optional[Callable]) = None

##### send_task_response

`send_task_response(request_message: AgentMessage, result: Dict[(str, Any)])`

タスクレスポンスを送信

**Parameters:**
- `request_message` (AgentMessage)
- `result` (Dict[(str, Any)])

##### process_messages

`process_messages()`

受信メッセージを処理
