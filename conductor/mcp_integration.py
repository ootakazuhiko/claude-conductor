#!/usr/bin/env python3
"""
MCP (Model Context Protocol) サーバー統合
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
import aiohttp
import websockets
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class MCPMessageType(Enum):
    """MCPメッセージタイプ"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"

class MCPCapability(Enum):
    """MCPサーバーの能力"""
    SEARCH = "search"
    FETCH = "fetch"
    COMPUTE = "compute"
    ANALYZE = "analyze"
    TRANSFORM = "transform"
    STORAGE = "storage"

@dataclass
class MCPServer:
    """MCPサーバー定義"""
    name: str
    url: str
    capabilities: Set[MCPCapability] = field(default_factory=set)
    version: str = "1.0"
    auth_token: Optional[str] = None
    max_concurrent_requests: int = 10
    timeout: float = 30.0
    retry_count: int = 3
    health_check_interval: float = 60.0
    is_healthy: bool = True
    last_health_check: float = 0.0
    
@dataclass
class MCPRequest:
    """MCPリクエスト"""
    request_id: str
    method: str
    params: Dict[str, Any]
    server_name: str
    timestamp: float = field(default_factory=time.time)
    
@dataclass
class MCPResponse:
    """MCPレスポンス"""
    request_id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0

class MCPClient:
    """MCPクライアント実装"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.active_requests: Dict[str, MCPRequest] = {}
        self.request_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.health_check_tasks: Dict[str, asyncio.Task] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        """クライアントを開始"""
        self._session = aiohttp.ClientSession()
        logger.info("MCP client started")
        
    async def stop(self):
        """クライアントを停止"""
        # ヘルスチェックタスクをキャンセル
        for task in self.health_check_tasks.values():
            task.cancel()
            
        # セッションをクローズ
        if self._session:
            await self._session.close()
            
        logger.info("MCP client stopped")
        
    async def register_server(
        self,
        server: MCPServer,
        start_health_check: bool = True
    ):
        """MCPサーバーを登録"""
        self.servers[server.name] = server
        
        # リクエスト制限用のセマフォを作成
        self.request_semaphores[server.name] = asyncio.Semaphore(
            server.max_concurrent_requests
        )
        
        # 初期ヘルスチェック
        await self._health_check(server)
        
        # 定期的なヘルスチェックを開始
        if start_health_check:
            task = asyncio.create_task(
                self._health_check_loop(server)
            )
            self.health_check_tasks[server.name] = task
            
        logger.info(
            f"Registered MCP server: {server.name} at {server.url} "
            f"with capabilities: {[c.value for c in server.capabilities]}"
        )
        
    async def unregister_server(self, server_name: str):
        """MCPサーバーの登録を解除"""
        if server_name in self.servers:
            # ヘルスチェックを停止
            if server_name in self.health_check_tasks:
                self.health_check_tasks[server_name].cancel()
                del self.health_check_tasks[server_name]
                
            del self.servers[server_name]
            del self.request_semaphores[server_name]
            
            logger.info(f"Unregistered MCP server: {server_name}")
            
    async def call(
        self,
        server_name: str,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> MCPResponse:
        """MCPサーバーを呼び出し"""
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
            
        server = self.servers[server_name]
        
        # サーバーの健全性をチェック
        if not server.is_healthy:
            raise RuntimeError(f"Server {server_name} is not healthy")
            
        # リクエストを作成
        request_id = f"{server_name}_{int(time.time() * 1000)}"
        request = MCPRequest(
            request_id=request_id,
            method=method,
            params=params,
            server_name=server_name
        )
        
        # 同時実行数を制限
        async with self.request_semaphores[server_name]:
            self.active_requests[request_id] = request
            
            try:
                # リトライロジック付きで実行
                response = await self._execute_with_retry(
                    server,
                    request,
                    timeout or server.timeout
                )
                
                return response
                
            finally:
                # クリーンアップ
                if request_id in self.active_requests:
                    del self.active_requests[request_id]
                    
    async def call_multiple(
        self,
        calls: List[Dict[str, Any]]
    ) -> List[MCPResponse]:
        """複数のMCPサーバーを並列で呼び出し"""
        tasks = []
        
        for call_def in calls:
            task = self.call(
                server_name=call_def["server"],
                method=call_def["method"],
                params=call_def.get("params", {}),
                timeout=call_def.get("timeout")
            )
            tasks.append(task)
            
        # 並列実行
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # エラーをMCPResponseに変換
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                error_response = MCPResponse(
                    request_id=f"batch_{i}",
                    error={
                        "code": -32603,
                        "message": str(response),
                        "data": {"type": type(response).__name__}
                    }
                )
                results.append(error_response)
            else:
                results.append(response)
                
        return results
        
    async def find_capable_servers(
        self,
        capability: MCPCapability
    ) -> List[str]:
        """特定の能力を持つサーバーを検索"""
        capable_servers = []
        
        for name, server in self.servers.items():
            if capability in server.capabilities and server.is_healthy:
                capable_servers.append(name)
                
        return capable_servers
        
    async def _execute_with_retry(
        self,
        server: MCPServer,
        request: MCPRequest,
        timeout: float
    ) -> MCPResponse:
        """リトライロジック付きでリクエストを実行"""
        last_error = None
        
        for attempt in range(server.retry_count):
            try:
                # プロトコルに応じて実行
                parsed_url = urlparse(server.url)
                
                if parsed_url.scheme in ["http", "https"]:
                    response = await self._execute_http(
                        server, request, timeout
                    )
                elif parsed_url.scheme in ["ws", "wss"]:
                    response = await self._execute_websocket(
                        server, request, timeout
                    )
                else:
                    raise ValueError(
                        f"Unsupported protocol: {parsed_url.scheme}"
                    )
                    
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Request to {server.name} failed (attempt {attempt + 1}/{server.retry_count}): {e}"
                )
                
                # 指数バックオフ
                if attempt < server.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
                    
        # すべての試行が失敗
        return MCPResponse(
            request_id=request.request_id,
            error={
                "code": -32000,
                "message": f"All retry attempts failed: {last_error}",
                "data": {"server": server.name}
            }
        )
        
    async def _execute_http(
        self,
        server: MCPServer,
        request: MCPRequest,
        timeout: float
    ) -> MCPResponse:
        """HTTP/HTTPSプロトコルで実行"""
        start_time = time.time()
        
        # リクエストボディを構築
        body = {
            "jsonrpc": "2.0",
            "id": request.request_id,
            "method": request.method,
            "params": request.params
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # 認証トークンを追加
        if server.auth_token:
            headers["Authorization"] = f"Bearer {server.auth_token}"
            
        # リクエストを送信
        async with self._session.post(
            server.url,
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as response:
            response_data = await response.json()
            
        duration = time.time() - start_time
        
        # レスポンスを解析
        if "error" in response_data:
            return MCPResponse(
                request_id=request.request_id,
                error=response_data["error"],
                duration=duration
            )
        else:
            return MCPResponse(
                request_id=request.request_id,
                result=response_data.get("result"),
                duration=duration
            )
            
    async def _execute_websocket(
        self,
        server: MCPServer,
        request: MCPRequest,
        timeout: float
    ) -> MCPResponse:
        """WebSocketプロトコルで実行"""
        start_time = time.time()
        
        # WebSocket接続を確立
        headers = {}
        if server.auth_token:
            headers["Authorization"] = f"Bearer {server.auth_token}"
            
        async with websockets.connect(
            server.url,
            extra_headers=headers
        ) as websocket:
            # リクエストを送信
            message = {
                "jsonrpc": "2.0",
                "id": request.request_id,
                "method": request.method,
                "params": request.params
            }
            
            await websocket.send(json.dumps(message))
            
            # レスポンスを待機
            try:
                response_text = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=timeout
                )
                response_data = json.loads(response_text)
            except asyncio.TimeoutError:
                return MCPResponse(
                    request_id=request.request_id,
                    error={
                        "code": -32300,
                        "message": "Request timeout",
                        "data": {"timeout": timeout}
                    }
                )
                
        duration = time.time() - start_time
        
        # レスポンスを解析
        if "error" in response_data:
            return MCPResponse(
                request_id=request.request_id,
                error=response_data["error"],
                duration=duration
            )
        else:
            return MCPResponse(
                request_id=request.request_id,
                result=response_data.get("result"),
                duration=duration
            )
            
    async def _health_check(self, server: MCPServer):
        """サーバーのヘルスチェック"""
        try:
            # ヘルスチェックリクエスト
            response = await self.call(
                server.name,
                "system.health",
                {},
                timeout=10.0
            )
            
            server.is_healthy = response.error is None
            server.last_health_check = time.time()
            
            if server.is_healthy:
                logger.debug(f"Health check passed for {server.name}")
            else:
                logger.warning(
                    f"Health check failed for {server.name}: {response.error}"
                )
                
        except Exception as e:
            server.is_healthy = False
            server.last_health_check = time.time()
            logger.error(f"Health check error for {server.name}: {e}")
            
    async def _health_check_loop(self, server: MCPServer):
        """定期的なヘルスチェックループ"""
        while True:
            try:
                await asyncio.sleep(server.health_check_interval)
                await self._health_check(server)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Error in health check loop for {server.name}: {e}"
                )


class MCPToolAdapter:
    """MCPサーバーをエージェントツールとして適応"""
    
    def __init__(self, mcp_client: MCPClient):
        self.mcp_client = mcp_client
        self.tool_mappings: Dict[str, Dict[str, Any]] = {}
        
    def register_tool(
        self,
        tool_name: str,
        server_name: str,
        method: str,
        description: str,
        param_schema: Dict[str, Any],
        capability: MCPCapability
    ):
        """MCPメソッドをツールとして登録"""
        self.tool_mappings[tool_name] = {
            "server": server_name,
            "method": method,
            "description": description,
            "param_schema": param_schema,
            "capability": capability
        }
        
        logger.info(
            f"Registered MCP tool: {tool_name} -> {server_name}.{method}"
        )
        
    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ツールを実行"""
        if tool_name not in self.tool_mappings:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        mapping = self.tool_mappings[tool_name]
        
        # パラメータを検証
        # TODO: param_schemaに基づく検証を実装
        
        # MCPサーバーを呼び出し
        response = await self.mcp_client.call(
            server_name=mapping["server"],
            method=mapping["method"],
            params=params
        )
        
        if response.error:
            raise RuntimeError(
                f"Tool execution failed: {response.error['message']}"
            )
            
        return {
            "tool": tool_name,
            "result": response.result,
            "duration": response.duration
        }
        
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """利用可能なツール一覧を取得"""
        tools = []
        
        for tool_name, mapping in self.tool_mappings.items():
            # サーバーが健全な場合のみ含める
            server = self.mcp_client.servers.get(mapping["server"])
            if server and server.is_healthy:
                tools.append({
                    "name": tool_name,
                    "description": mapping["description"],
                    "capability": mapping["capability"].value,
                    "server": mapping["server"]
                })
                
        return tools
        
    async def discover_tools(self, server_name: str):
        """MCPサーバーからツールを自動発見"""
        try:
            # サーバーの能力を問い合わせ
            response = await self.mcp_client.call(
                server_name,
                "system.listMethods",
                {}
            )
            
            if response.error:
                logger.error(
                    f"Failed to discover tools from {server_name}: "
                    f"{response.error}"
                )
                return
                
            methods = response.result
            
            # 各メソッドをツールとして登録
            for method_info in methods:
                method_name = method_info["name"]
                
                # システムメソッドはスキップ
                if method_name.startswith("system."):
                    continue
                    
                # ツール名を生成
                tool_name = f"{server_name}_{method_name.replace('.', '_')}"
                
                # 能力を推測
                capability = self._infer_capability(method_name)
                
                self.register_tool(
                    tool_name=tool_name,
                    server_name=server_name,
                    method=method_name,
                    description=method_info.get("description", ""),
                    param_schema=method_info.get("params", {}),
                    capability=capability
                )
                
            logger.info(
                f"Discovered {len(methods)} tools from {server_name}"
            )
            
        except Exception as e:
            logger.error(f"Error discovering tools from {server_name}: {e}")
            
    def _infer_capability(self, method_name: str) -> MCPCapability:
        """メソッド名から能力を推測"""
        method_lower = method_name.lower()
        
        if "search" in method_lower or "find" in method_lower:
            return MCPCapability.SEARCH
        elif "fetch" in method_lower or "get" in method_lower:
            return MCPCapability.FETCH
        elif "compute" in method_lower or "calculate" in method_lower:
            return MCPCapability.COMPUTE
        elif "analyze" in method_lower or "inspect" in method_lower:
            return MCPCapability.ANALYZE
        elif "transform" in method_lower or "convert" in method_lower:
            return MCPCapability.TRANSFORM
        elif "store" in method_lower or "save" in method_lower:
            return MCPCapability.STORAGE
        else:
            return MCPCapability.COMPUTE  # デフォルト


class MCPRegistry:
    """MCPサーバーレジストリ"""
    
    def __init__(self):
        self.registry: Dict[str, Dict[str, Any]] = {}
        
    def add_server(
        self,
        name: str,
        url: str,
        capabilities: List[str],
        auth_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """サーバーをレジストリに追加"""
        self.registry[name] = {
            "url": url,
            "capabilities": capabilities,
            "auth_config": auth_config or {},
            "metadata": metadata or {},
            "registered_at": time.time()
        }
        
    def remove_server(self, name: str):
        """サーバーをレジストリから削除"""
        if name in self.registry:
            del self.registry[name]
            
    def get_server_config(self, name: str) -> Optional[Dict[str, Any]]:
        """サーバー設定を取得"""
        return self.registry.get(name)
        
    def find_servers_by_capability(
        self,
        capability: str
    ) -> List[str]:
        """能力でサーバーを検索"""
        servers = []
        
        for name, config in self.registry.items():
            if capability in config["capabilities"]:
                servers.append(name)
                
        return servers
        
    def save_to_file(self, filepath: str):
        """レジストリをファイルに保存"""
        with open(filepath, 'w') as f:
            json.dump(self.registry, f, indent=2)
            
    def load_from_file(self, filepath: str):
        """ファイルからレジストリを読み込み"""
        with open(filepath, 'r') as f:
            self.registry = json.load(f)