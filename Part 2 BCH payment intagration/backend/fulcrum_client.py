"""
Fulcrum Electrum Cash Protocol Client
A comprehensive Python client for communicating with Fulcrum servers
Supports protocol methods over TCP/SSL transports
"""

import json
import socket
import ssl
import threading
import hashlib
from typing import Dict, List, Optional, Union, Callable, Any
from dataclasses import dataclass
from enum import Enum
__all__ = ["TransportType", "ServerInfo", "FulcrumClient"]


class TransportType(Enum):
    TCP = "tcp"
    SSL = "ssl"


@dataclass
class ServerInfo:
    host: str
    port: int
    transport: TransportType = TransportType.TCP


class FulcrumClient:
    """
    A comprehensive client for the Fulcrum Electrum Cash Protocol
    """
    
    def __init__(self, host: str, port: int, transport: TransportType = TransportType.TCP,
                 client_name: str = "PythonFulcrumClient", protocol_version: str = "1.5.0"):
        self.host = host
        self.port = port
        self.transport = transport
        self.client_name = client_name
        self.protocol_version = protocol_version
        self.protocol_min = "1.4"
        
        self.socket = None
        self.connected = False
        self.request_id = 0
        self.subscriptions = {}
        self.notification_handlers = {}
        self.response_queue = {}
        self.response_events = {}
        
        # Threading
        self.receive_thread = None
        self.stop_event = threading.Event()
        
    def connect(self) -> bool:
        """Connect to the Fulcrum server"""
        try:
            if self.transport in [TransportType.TCP, TransportType.SSL]:
                return self._connect_socket()
            else:
                raise ValueError(f"Unsupported transport: {self.transport}")
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def _connect_socket(self) -> bool:
        """Connect using TCP or SSL"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            if self.transport == TransportType.SSL:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.socket = context.wrap_socket(self.socket, server_hostname=self.host)
            
            self.socket.connect((self.host, self.port))
            self.connected = True
            
            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_messages_socket)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            # Negotiate protocol version
            return self._negotiate_version()
            
        except Exception as e:
            print(f"Socket connection failed: {e}")
            return False
    
    def _negotiate_version(self) -> bool:
        """Negotiate protocol version with server"""
        try:
            response = self.server_version(self.client_name, self.protocol_version)
            if response:
                print(f"Connected to {response[0]}, using protocol {response[1]}")
                return True
        except Exception as e:
            print(f"Version negotiation failed: {e}")
        return False
    
    def disconnect(self):
        """Disconnect from the server"""
        self.connected = False
        self.stop_event.set()
        
        if self.socket:
            self.socket.close()
        
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1)
    
    def _get_next_id(self) -> int:
        """Get next request ID"""
        self.request_id += 1
        return self.request_id
    
    def _send_request(self, method: str, params: Union[List, Dict] = None) -> Any:
        """Send a JSON-RPC request and wait for response"""
        if not self.connected:
            raise ConnectionError("Not connected to server")
        
        request_id = self._get_next_id()
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": request_id
        }
        
        # Create event for this request
        self.response_events[request_id] = threading.Event()
        
        try:
            if self.transport in [TransportType.TCP, TransportType.SSL]:
                message = json.dumps(request) + '\n'
                self.socket.send(message.encode('utf-8'))
            
            # Wait for response
            if self.response_events[request_id].wait(timeout=30):
                response = self.response_queue.pop(request_id, None)
                if response:
                    if 'error' in response:
                        raise Exception(f"Server error: {response['error']}")
                    return response.get('result')
            else:
                raise TimeoutError("Request timeout")
                
        finally:
            # Cleanup
            self.response_events.pop(request_id, None)
            self.response_queue.pop(request_id, None)
    
    def _receive_messages_socket(self):
        """Receive messages from socket connection"""
        buffer = ""
        
        while not self.stop_event.is_set() and self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    # Remote closed connection
                    self.connected = False
                    break
                
                buffer += data
                
                # Process complete messages (newline-delimited)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._handle_message(json.loads(line.strip()))
                        
            except Exception as e:
                if self.connected:  # Only print if we're still supposed to be connected
                    print(f"Receive error: {e}")
                # Mark as disconnected so callers can detect and reconnect
                self.connected = False
                break
    
    def _handle_message(self, message: Dict):
        """Handle incoming message"""
        if 'id' in message:
            # Response to request
            request_id = message['id']
            self.response_queue[request_id] = message
            if request_id in self.response_events:
                self.response_events[request_id].set()
        else:
            # Notification
            method = message.get('method')
            params = message.get('params', [])
            
            if method in self.notification_handlers:
                try:
                    self.notification_handlers[method](params)
                except Exception as e:
                    print(f"Notification handler error for {method}: {e}")
    
    def subscribe(self, method: str, handler: Callable):
        """Register a notification handler"""
        self.notification_handlers[method] = handler
    
    # Utility Functions
    @staticmethod
    def address_to_scripthash(address: str) -> str:
        """Convert Bitcoin Cash address to script hash"""
        # This is a simplified version - you'd want to use a proper library
        # like bitcoincash or cashaddress for production use
        try:
            import cashaddress
            # Decode address to get the hash160
            addr_type, hash160 = cashaddress.decode(address)
            
            if addr_type == 'P2PKH':
                script = bytes([0x76, 0xa9, 0x14]) + hash160 + bytes([0x88, 0xac])
            elif addr_type == 'P2SH':
                script = bytes([0xa9, 0x14]) + hash160 + bytes([0x87])
            else:
                raise ValueError(f"Unsupported address type: {addr_type}")
            
            # SHA256 hash and reverse
            scripthash = hashlib.sha256(script).digest()[::-1]
            return scripthash.hex()
            
        except ImportError:
            raise ImportError("cashaddress library required for address conversion")
    
    # ============================================================================
    # BLOCKCHAIN METHODS
    # ============================================================================
    
    # Address methods
    def blockchain_address_get_balance(self, address: str, token_filter: str = None) -> Dict:
        """Get balance for a Bitcoin Cash address"""
        params = [address]
        if token_filter:
            params.append(token_filter)
        return self._send_request("blockchain.address.get_balance", params)
    
    def blockchain_address_get_first_use(self, address: str) -> Dict:
        """Get first use information for an address"""
        return self._send_request("blockchain.address.get_first_use", [address])
    
    def blockchain_address_get_history(self, address: str, from_height: int = 0, to_height: int = -1) -> List[Dict]:
        """Get transaction history for an address"""
        return self._send_request("blockchain.address.get_history", [address, from_height, to_height])
    
    def blockchain_address_get_mempool(self, address: str) -> List[Dict]:
        """Get mempool transactions for an address"""
        return self._send_request("blockchain.address.get_mempool", [address])
    
    def blockchain_address_get_scripthash(self, address: str) -> str:
        """Convert address to script hash"""
        return self._send_request("blockchain.address.get_scripthash", [address])
    
    def blockchain_address_listunspent(self, address: str, token_filter: str = None) -> List[Dict]:
        """List unspent outputs for an address"""
        params = [address]
        if token_filter:
            params.append(token_filter)
        return self._send_request("blockchain.address.listunspent", params)
    
    def blockchain_address_subscribe(self, address: str) -> str:
        """Subscribe to address changes"""
        return self._send_request("blockchain.address.subscribe", [address])
    
    def blockchain_address_unsubscribe(self, address: str) -> bool:
        """Unsubscribe from address"""
        return self._send_request("blockchain.address.unsubscribe", [address])
    
    # Block methods
    def blockchain_block_header(self, height: int, cp_height: int = 0) -> Union[str, Dict]:
        """Get block header"""
        return self._send_request("blockchain.block.header", [height, cp_height])
    
    def blockchain_block_headers(self, start_height: int, count: int, cp_height: int = 0) -> Dict:
        """Get multiple block headers"""
        return self._send_request("blockchain.block.headers", [start_height, count, cp_height])
    
    def blockchain_estimatefee(self, number: int, mode: str = None) -> float:
        """Estimate transaction fee"""
        params = [number]
        if mode:
            params.append(mode)
        return self._send_request("blockchain.estimatefee", params)
    
    def blockchain_header_get(self, block_hash: str) -> Dict:
        """Get header by hash or height"""
        return self._send_request("blockchain.header.get", [block_hash])
    
    def blockchain_headers_get_tip(self) -> Dict:
        """Get latest block header"""
        return self._send_request("blockchain.headers.get_tip")
    
    def blockchain_headers_subscribe(self) -> Dict:
        """Subscribe to new block headers"""
        return self._send_request("blockchain.headers.subscribe")
    
    def blockchain_headers_unsubscribe(self) -> bool:
        """Unsubscribe from block headers"""
        return self._send_request("blockchain.headers.unsubscribe")
    
    def blockchain_relayfee(self) -> float:
        """Get relay fee (deprecated)"""
        return self._send_request("blockchain.relayfee")
    
    # RPA methods
    def blockchain_rpa_get_history(self, rpa_prefix: str, from_height: int, to_height: int = -1) -> List[Dict]:
        """Get RPA prefix history"""
        return self._send_request("blockchain.rpa.get_history", [rpa_prefix, from_height, to_height])
    
    def blockchain_rpa_get_mempool(self, rpa_prefix: str) -> List[Dict]:
        """Get RPA prefix mempool"""
        return self._send_request("blockchain.rpa.get_mempool", [rpa_prefix])
    
    # Script hash methods
    def blockchain_scripthash_get_balance(self, scripthash: str, token_filter: str = None) -> Dict:
        """Get balance for script hash"""
        params = [scripthash]
        if token_filter:
            params.append(token_filter)
        return self._send_request("blockchain.scripthash.get_balance", params)
    
    def blockchain_scripthash_get_first_use(self, scripthash: str) -> Dict:
        """Get first use for script hash"""
        return self._send_request("blockchain.scripthash.get_first_use", [scripthash])
    
    def blockchain_scripthash_get_history(self, scripthash: str, from_height: int = 0, to_height: int = -1) -> List[Dict]:
        """Get history for script hash"""
        return self._send_request("blockchain.scripthash.get_history", [scripthash, from_height, to_height])
    
    def blockchain_scripthash_get_mempool(self, scripthash: str) -> List[Dict]:
        """Get mempool for script hash"""
        return self._send_request("blockchain.scripthash.get_mempool", [scripthash])
    
    def blockchain_scripthash_listunspent(self, scripthash: str, token_filter: str = None) -> List[Dict]:
        """List unspent for script hash"""
        params = [scripthash]
        if token_filter:
            params.append(token_filter)
        return self._send_request("blockchain.scripthash.listunspent", params)
    
    def blockchain_scripthash_subscribe(self, scripthash: str) -> str:
        """Subscribe to script hash"""
        return self._send_request("blockchain.scripthash.subscribe", [scripthash])
    
    def blockchain_scripthash_unsubscribe(self, scripthash: str) -> bool:
        """Unsubscribe from script hash"""
        return self._send_request("blockchain.scripthash.unsubscribe", [scripthash])
    
    # Transaction methods
    def blockchain_transaction_broadcast(self, raw_tx: str) -> str:
        """Broadcast transaction"""
        return self._send_request("blockchain.transaction.broadcast", [raw_tx])
    
    def blockchain_transaction_broadcast_package(self, raw_txs: List[str], verbose: bool = False) -> Dict:
        """Broadcast transaction package (BTC only)"""
        return self._send_request("blockchain.transaction.broadcast_package", [raw_txs, verbose])
    
    def blockchain_transaction_get(self, tx_hash: str, verbose: bool = False) -> Union[str, Dict]:
        """Get transaction"""
        return self._send_request("blockchain.transaction.get", [tx_hash, verbose])
    
    def blockchain_transaction_get_confirmed_blockhash(self, tx_hash: str, include_header: bool = False) -> Dict:
        """Get block hash for confirmed transaction"""
        return self._send_request("blockchain.transaction.get_confirmed_blockhash", [tx_hash, include_header])
    
    def blockchain_transaction_get_height(self, tx_hash: str) -> Optional[int]:
        """Get transaction height"""
        return self._send_request("blockchain.transaction.get_height", [tx_hash])
    
    def blockchain_transaction_get_merkle(self, tx_hash: str, height: int = None) -> Dict:
        """Get merkle proof for transaction"""
        params = [tx_hash]
        if height is not None:
            params.append(height)
        return self._send_request("blockchain.transaction.get_merkle", params)
    
    def blockchain_transaction_id_from_pos(self, height: int, tx_pos: int, merkle: bool = False) -> Union[str, Dict]:
        """Get transaction ID from position"""
        return self._send_request("blockchain.transaction.id_from_pos", [height, tx_pos, merkle])
    
    def blockchain_transaction_subscribe(self, tx_hash: str) -> Optional[int]:
        """Subscribe to transaction"""
        return self._send_request("blockchain.transaction.subscribe", [tx_hash])
    
    def blockchain_transaction_unsubscribe(self, tx_hash: str) -> bool:
        """Unsubscribe from transaction"""
        return self._send_request("blockchain.transaction.unsubscribe", [tx_hash])
    
    # Double-spend proof methods
    def blockchain_transaction_dsproof_get(self, hash_value: str) -> Optional[Dict]:
        """Get double-spend proof"""
        return self._send_request("blockchain.transaction.dsproof.get", [hash_value])
    
    def blockchain_transaction_dsproof_list(self) -> List[str]:
        """List transactions with double-spend proofs"""
        return self._send_request("blockchain.transaction.dsproof.list")
    
    def blockchain_transaction_dsproof_subscribe(self, tx_hash: str) -> Optional[Dict]:
        """Subscribe to double-spend proofs"""
        return self._send_request("blockchain.transaction.dsproof.subscribe", [tx_hash])
    
    def blockchain_transaction_dsproof_unsubscribe(self, tx_hash: str) -> bool:
        """Unsubscribe from double-spend proofs"""
        return self._send_request("blockchain.transaction.dsproof.unsubscribe", [tx_hash])
    
    # UTXO methods
    def blockchain_utxo_get_info(self, tx_hash: str, out_n: int) -> Optional[Dict]:
        """Get UTXO information"""
        return self._send_request("blockchain.utxo.get_info", [tx_hash, out_n])
    
    # ============================================================================
    # MEMPOOL METHODS
    # ============================================================================
    
    def mempool_get_fee_histogram(self) -> List[List[Union[int, float]]]:
        """Get mempool fee histogram"""
        return self._send_request("mempool.get_fee_histogram")
    
    def mempool_get_info(self) -> Dict:
        """Get mempool information"""
        return self._send_request("mempool.get_info")
    
    # ============================================================================
    # SERVER METHODS
    # ============================================================================
    
    def server_add_peer(self, features: Dict) -> bool:
        """Add peer server"""
        return self._send_request("server.add_peer", [features])
    
    def server_banner(self) -> str:
        """Get server banner"""
        return self._send_request("server.banner")
    
    def server_donation_address(self) -> str:
        """Get donation address"""
        return self._send_request("server.donation_address")
    
    def server_features(self) -> Dict:
        """Get server features"""
        return self._send_request("server.features")
    
    def server_peers_subscribe(self) -> List[List]:
        """Get peer list"""
        return self._send_request("server.peers.subscribe")
    
    def server_ping(self) -> None:
        """Ping server"""
        return self._send_request("server.ping")
    
    def server_version(self, client_name: str = None, protocol_version: str = None) -> List[str]:
        """Get server version and negotiate protocol"""
        client_name = client_name or self.client_name
        protocol_version = protocol_version or self.protocol_version
        return self._send_request("server.version", [client_name, protocol_version])
    
    # ============================================================================
    # DAEMON METHODS
    # ============================================================================
    
    def daemon_passthrough(self, method: str, params: List = None) -> Any:
        """Direct RPC call to daemon"""
        request_dict = {
            "method": method,
            "params": params or []
        }
        return self._send_request("daemon.passthrough", request_dict)


