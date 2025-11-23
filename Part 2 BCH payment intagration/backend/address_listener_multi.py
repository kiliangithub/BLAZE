"""
PostgreSQL Database Listener for BCH Address Monitoring
Listens to database changes and maintains a list of addresses to monitor
"""

import psycopg2
import psycopg2.extensions
import json
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass

__all__ = ["AddressConfig", "BCHDatabaseListener"]


@dataclass
class AddressConfig:
    """Configuration for an address to monitor"""
    address: str
    user_id: Optional[str]
    device_id: Optional[str]
    created_at: Optional[str]
    threshold: Optional[float]
    euro_amount: Optional[float]


 


class BCHDatabaseListener:
    """
    Listens to PostgreSQL notifications for BCH table changes
    and maintains an up-to-date list of addresses to monitor
    """
    
    def __init__(self, db_connection_string: str, notification_channel: str = "bch_table_changes"):
        """
        Initialize the database listener
        
        Args:
            db_connection_string: PostgreSQL connection string 
                                 (e.g., "dbname=mydb user=myusername password=mypasschangethis host=localhost")
            notification_channel: PostgreSQL NOTIFY channel name
        """
        self.db_connection_string = db_connection_string
        self.notification_channel = notification_channel
        self.connection = None
        self.addresses: Dict[str, AddressConfig] = {}
        self.running = False
        self.listener_thread = None
        self.lock = threading.Lock()
        
    def connect(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(self.db_connection_string)
            self.connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            print(f"✅ Connected to PostgreSQL database")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from PostgreSQL database"""
        self.running = False
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=5)
        
        if self.connection:
            try:
                self.connection.close()
                print("✅ Disconnected from database")
            except Exception as e:
                print(f"⚠️  Error disconnecting: {e}")
    
    def load_addresses(self) -> bool:
        """Load all addresses from the bch table"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT address, user_id, device_id, created_at, threshold, euro_amount
                FROM bch
            """)
            
            rows = cursor.fetchall()
            cursor.close()
            
            with self.lock:
                self.addresses.clear()
                for row in rows:
                    address_config = AddressConfig(
                        address=row[0],
                        user_id=row[1],
                        device_id=row[2],
                        created_at=str(row[3]) if row[3] is not None else None,
                        threshold=row[4],
                        euro_amount=row[5]
                    )
                    self.addresses[address_config.address] = address_config
            
            print(f"✅ Loaded {len(self.addresses)} addresses from database")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load addresses: {e}")
            return False
    
    def start_listening(self):
        """Start listening for database notifications"""
        if not self.connection:
            print("❌ Not connected to database")
            return
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"LISTEN {self.notification_channel};")
            cursor.close()
            print(f"✅ Listening on channel: {self.notification_channel}")
            
            self.running = True
            self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listener_thread.start()
            
        except Exception as e:
            print(f"❌ Failed to start listening: {e}")
    
    def _listen_loop(self):
        """Main loop for listening to notifications"""
        print("🎧 Notification listener started")
        
        while self.running:
            try:
                if self.connection.poll() == psycopg2.extensions.POLL_OK:
                    self.connection.poll()
                    
                    while self.connection.notifies:
                        notify = self.connection.notifies.pop(0)
                        print(f"📬 Received notification: {notify.payload}")
                        self._handle_notification(notify.payload)
                
                # Small sleep to avoid busy-waiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Error in listen loop: {e}")
                if not self.running:
                    break
                # Try to reconnect
                try:
                    self.connection.close()
                    time.sleep(5)
                    if self.connect():
                        cursor = self.connection.cursor()
                        cursor.execute(f"LISTEN {self.notification_channel};")
                        cursor.close()
                        print("✅ Reconnected and resumed listening")
                except Exception as reconnect_error:
                    print(f"❌ Failed to reconnect: {reconnect_error}")
                    time.sleep(5)
        
        print("🛑 Notification listener stopped")
    
    def _handle_notification(self, payload: str):
        """
        Handle incoming notification
        
        Expected payload format (JSON):
        {
            "action": "INSERT" | "UPDATE" | "DELETE",
            "address": "bitcoincash:...",
            "user_id": "user123",
            "device_id": "device456"
        }
        """
        try:
            data = json.loads(payload)
            action = data.get('action', '').upper()
            
            if action == 'INSERT' or action == 'UPDATE':
                address_config = AddressConfig(
                    address=data['address'],
                    user_id=data.get('user_id'),
                    device_id=data.get('device_id'),
                    created_at=data.get('created_at'),
                    threshold=data.get('threshold'),
                    euro_amount=data.get('euro_amount')
                )
                
                with self.lock:
                    self.addresses[address_config.address] = address_config
                
                print(f"✅ {action}: {address_config.address}")
                
            elif action == 'DELETE':
                address = data['address']
                
                with self.lock:
                    if address in self.addresses:
                        del self.addresses[address]
                        print(f"✅ DELETED: {address}")
            
            else:
                # If no specific action, reload all addresses
                self.load_addresses()
                
        except json.JSONDecodeError:
            print(f"⚠️  Invalid JSON payload: {payload}")
            # Fallback: reload all addresses
            self.load_addresses()
        except Exception as e:
            print(f"❌ Error handling notification: {e}")
    
    def get_addresses(self) -> List[AddressConfig]:
        """Get the current list of addresses (thread-safe)"""
        with self.lock:
            return list(self.addresses.values())
    
    def get_address(self, address: str) -> Optional[AddressConfig]:
        """Get configuration for a specific address (thread-safe)"""
        with self.lock:
            return self.addresses.get(address)
    
    def get_payments(self) -> List[AddressConfig]:
        """
        Return the current addresses as a list of AddressConfig objects (thread-safe),
        suitable for importing and consuming outside this module.
        """
        with self.lock:
            return list(self.addresses.values())
    
    def print_addresses(self):
        """Print all addresses in a formatted way"""
        addresses = self.get_addresses()
        print(f"\n{'='*80}")
        print(f"Monitored Addresses: {len(addresses)}")
        print(f"{'='*80}")
        
        if not addresses:
            print("No addresses configured")
        else:
            for addr_config in addresses:
                print(f"  📍 {addr_config.address}")
                print(f"     User ID: {addr_config.user_id}")
                print(f"     Device ID: {addr_config.device_id}")
                print(f"     Created At: {addr_config.created_at}")
                print(f"     Threshold: {addr_config.threshold}")
                print(f"     Euro Amount: {addr_config.euro_amount}")
                print()
        
        print(f"{'='*80}\n")


def example_usage():
    """
    Example of how to use the BCHDatabaseListener
    """
    
    # Database connection string (URI)
    DB_CONNECTION = "postgresql://mlkj:mlkjmkljklmjkmlj@10.120.200.112:5432/testing"
    
    # Create listener
    listener = BCHDatabaseListener(
        db_connection_string=DB_CONNECTION,
        notification_channel="bch_table_changes"
    )
    
    try:
        # Connect to database
        if not listener.connect():
            print("Failed to connect to database")
            return
        
        # Load initial addresses
        listener.load_addresses()
        listener.print_addresses()
        
        # Start listening for changes
        listener.start_listening()
        
        # Keep running and periodically print the address list
        print("Monitoring for changes... (Press Ctrl+C to stop)")
        while True:
            time.sleep(30)  # Print every 30 seconds
            listener.print_addresses()
            
    except KeyboardInterrupt:
        print("\n⏹️  Stopping listener...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        listener.disconnect()


if __name__ == "__main__":
    example_usage()

