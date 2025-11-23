from typing import Dict, List, Tuple, Set, Any
import time
import threading
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
import json
from urllib import request, error as urlerror
import math

from address_listener_multi import BCHDatabaseListener, AddressConfig
from fulcrum_client import FulcrumClient, TransportType


SYNC_INTERVAL_SECS = 2.0
PRICE_REFRESH_INTERVAL_SECS = 10 * 60  # 10 minutes

#
# Grain multiplier constants (EUR-tiered), defined once
#
# NOTE: The same multipliers are also defined in routers/buy.py — keep in sync.
GRAIN_MULTIPLIER_LT_20 = 4.0
GRAIN_MULTIPLIER_20_TO_49_99 = 5.0
GRAIN_MULTIPLIER_GE_50 = 6.0


def _build_address_set(payments: List[AddressConfig]) -> Set[str]:
    return {p.address for p in payments}


def on_threshold(payment: AddressConfig, event: Dict[str, Any]) -> None:
    """Triggered when an incoming UTXO meets/exceeds the threshold for the address."""
    print(
        f"🚨 Payment detected for {payment.address}: "
        f"{event.get('value_sats', 0)} sats in "
        f"{event.get('tx_hash')}:{event.get('tx_pos')}"
    )


_PRICE_CACHE_EUR: Dict[str, Any] = {"ts": 0.0, "price": None}
_PRICE_CACHE_USD: Dict[str, Any] = {"ts": 0.0, "price": None}
_PRICE_CACHE_LOCK = threading.Lock()
_PRICE_STOP_EVENT = threading.Event()
_PRICE_REFRESH_THREAD = None


def _refresh_bch_prices_once() -> None:
    """
    Fetch both EUR and USD BCH prices in a single request and update cache.
    """
    now_ts = time.time()
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin-cash&vs_currencies=eur,usd"
        with request.urlopen(url, timeout=5) as resp:
            payload = resp.read()
        data = json.loads(payload.decode("utf-8"))
        eur_val = float(data.get("bitcoin-cash", {}).get("eur") or 0.0)
        usd_val = float(data.get("bitcoin-cash", {}).get("usd") or 0.0)
        if eur_val > 0 or usd_val > 0:
            with _PRICE_CACHE_LOCK:
                if eur_val > 0:
                    _PRICE_CACHE_EUR["price"] = eur_val
                    _PRICE_CACHE_EUR["ts"] = now_ts
                if usd_val > 0:
                    _PRICE_CACHE_USD["price"] = usd_val
                    _PRICE_CACHE_USD["ts"] = now_ts
    except Exception as e:
        print(f"⚠️  Failed to refresh BCH prices: {e}")


def _start_price_refresher_thread() -> None:
    """
    Start a background daemon thread that refreshes BCH prices every 20 minutes.
    """
    global _PRICE_REFRESH_THREAD
    if _PRICE_REFRESH_THREAD is not None:
        return

    def _loop():
        # Warm-up fetch at start
        _refresh_bch_prices_once()
        while not _PRICE_STOP_EVENT.wait(PRICE_REFRESH_INTERVAL_SECS):
            _refresh_bch_prices_once()

    t = threading.Thread(target=_loop, daemon=True)
    _PRICE_REFRESH_THREAD = t
    t.start()


def get_bch_eur_price_cached(ttl_secs: float = 60.0) -> float | None:
    """
    Return last cached BCH/EUR price. Background thread refreshes every 20 minutes.
    Returns None if no cached value is available yet.
    """
    now_ts = time.time()
    with _PRICE_CACHE_LOCK:
        cached_price = _PRICE_CACHE_EUR.get("price")
        cached_ts = float(_PRICE_CACHE_EUR.get("ts", 0.0) or 0.0)
        # Return cached value if we have one, regardless of TTL, to avoid frequent API calls here
        if cached_price is not None:
            return float(cached_price)
    return None


def get_bch_usd_price_cached(ttl_secs: float = 60.0) -> float | None:
    """
    Return last cached BCH/USD price. Background thread refreshes every 20 minutes.
    Returns None if no cached value is available yet.
    """
    now_ts = time.time()
    with _PRICE_CACHE_LOCK:
        cached_price = _PRICE_CACHE_USD.get("price")
        cached_ts = float(_PRICE_CACHE_USD.get("ts", 0.0) or 0.0)
        if cached_price is not None:
            return float(cached_price)
    return None

def compute_grain_reward_eur(eur_amount: float) -> float:
    """
    Apply tiered multipliers based on EUR amount:
    - < 20  => * 6
    - 20-49.99 => * 7.5
    - >= 50 => * 8
    """
    if eur_amount < 20.0:
        multiplier = GRAIN_MULTIPLIER_LT_20
    elif eur_amount < 50.0:
        multiplier = GRAIN_MULTIPLIER_20_TO_49_99
    else:
        multiplier = GRAIN_MULTIPLIER_GE_50
    return eur_amount * multiplier


def write_payment_record(
    engine,
    tx_id: str,
    amount_sats: int,
    reference: str,
    description: str,
    address: str,
    euro_amount: float | None,
    usd_amount: float | None,
) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO bchpayment (tx_id, amount, reference, description, address, euro_amount, usd_amount, succeeded_at)
                    VALUES (:tx_id, :amount, :reference, :description, :address, :euro_amount, :usd_amount, NOW())
                    """
                ),
                {
                    "tx_id": tx_id,
                    "amount": amount_sats,
                    "reference": reference,
                    "description": description,
                    "address": address,
                    "euro_amount": euro_amount,
                    "usd_amount": usd_amount,
                },
            )
    except Exception as e:
        print(f"❌ Failed to insert payment record: {e}")


def run_monitor(
    db_connection_string: str = "postgresql://mkjkljm:Gmlkjjklmjkjmlk@10.109.201.114:5432/testing",
    fulcrum_host: str = "fulcrum.bitrally.cash",
    fulcrum_port: int = 50002,
    fulcrum_transport: TransportType = TransportType.SSL,
) -> None:
    # Start background BCH price refresher (20-minute interval)
    _start_price_refresher_thread()
    # Start DB listener
    listener = BCHDatabaseListener(db_connection_string=db_connection_string)
    if not listener.connect():
        print("❌ Could not connect to database")
        return
    listener.load_addresses()
    listener.start_listening()

    # Start Fulcrum client (Electrum protocol)
    client = FulcrumClient(
        host=fulcrum_host,
        port=fulcrum_port,
        transport=fulcrum_transport,
    )
    if not client.connect():
        print("❌ Could not connect to Fulcrum server")
        listener.disconnect()
        return

    # Known UTXOs per address to suppress historical duplicates
    known_utxos_by_addr: Dict[str, Set[Tuple[str, int]]] = {}
    # Map address -> AddressConfig for threshold lookups
    address_to_payment: Dict[str, AddressConfig] = {}

    # SQLAlchemy engine for inserts (reuse the same DB connection string)
    engine = create_engine(db_connection_string, pool_pre_ping=True, future=True)
    # Lock to serialize Fulcrum client I/O during reconnects
    client_lock = threading.Lock()

    # Handlers for Electrum notifications
    def threshold_handler(payment: AddressConfig, event: Dict[str, Any]) -> None:
        on_threshold(payment, event)
        tx_id = str(event.get("tx_hash") or "")
        amount_sats = int(event.get("value_sats", 0) or 0)
        # Resolve reference/description:
        # - If user_id present: keep reference as user_id, set description to username from users table
        # - Else if device_id present: set reference to alias from devices table (fallback to device_id)
        # - Else: reference is the address; keep default description
        user_id = getattr(payment, "user_id", None)
        device_id = getattr(payment, "device_id", None)

        reference: str
        description = f"Auto-detected payment to {payment.address} ({tx_id}:{event.get('tx_pos')})"
        euro_amount_insert: float | None = None
        usd_amount_insert: float | None = None

        if user_id is not None:
            reference = str(user_id)
            username = None
            try:
                with engine.connect() as conn:
                    username = conn.execute(
                        text("SELECT username FROM users WHERE id = :id LIMIT 1"),
                        {"id": user_id},
                    ).scalar()

            except Exception as e:
                print(f"⚠️  Failed to fetch username for user_id {user_id}: {e}")
            # Compute grain_delta:
            # - If the address was created < 30 minutes ago AND a sats threshold is set on AddressConfig,
            #   then require value_sats >= threshold_sats; if met, compute grain using stored euro_amount.
            # - If not met or window passed, fall back to payment-amount-based computation via BCH/EUR price.
            try:
                # Check address age and threshold presence (created_at guaranteed non-None)
                created_at_val = getattr(payment, "created_at")
                threshold_sats_val = getattr(payment, "threshold", None)
                # Normalize created_at to datetime with UTC
                if isinstance(created_at_val, datetime):
                    created_at_dt = created_at_val
                else:
                    # Fallback: attempt to parse if not already datetime
                    created_at_dt = datetime.fromisoformat(str(created_at_val))
                if created_at_dt.tzinfo is None:
                    created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - created_at_dt).total_seconds()
                within_window = age_seconds < 30 * 60
                threshold_sats: int | None = None
                if threshold_sats_val is not None:
                    try:
                        threshold_sats = int(float(threshold_sats_val))
                        if threshold_sats <= 0:
                            threshold_sats = None
                    except Exception:
                        threshold_sats = None

                if within_window and threshold_sats is not None:
                    # Gate by sats threshold during the initial window
                    if amount_sats >= threshold_sats:
                        # Compute grain using configured euro_amount (tiers)
                        euro_amount_cfg = getattr(payment, "euro_amount", None)
                        if euro_amount_cfg is not None and float(euro_amount_cfg) > 0:
                            eur_amount = float(euro_amount_cfg)
                            euro_amount_insert = eur_amount
                            # Compute USD snapshot for record
                            price_usd = get_bch_usd_price_cached()
                            if price_usd:
                                usd_amount_insert = float(event.get("value_bch", 0.0) or 0.0) * price_usd
                            grain_delta = math.ceil(compute_grain_reward_eur(eur_amount))
                            with engine.begin() as conn:
                                conn.execute(
                                    text(
                                        """
                                        UPDATE users
                                        SET grain_balance = COALESCE(grain_balance, 0) + :grain_delta
                                        WHERE id = :id
                                        """
                                    ),
                                    {"id": user_id, "grain_delta": grain_delta},
                                )
                            # Reflect grain addition in the payment description
                            display_name = str(username) if username else f"user {user_id}"
                            description = f"{display_name} (+{grain_delta} grain)"
                        else:
                            # euro_amount missing or invalid; fall back to price-based method
                            value_bch = float(event.get("value_bch", 0.0) or 0.0)
                            price_eur = get_bch_eur_price_cached()
                            price_usd = get_bch_usd_price_cached()
                            if price_eur:
                                eur_amount = value_bch * price_eur
                                euro_amount_insert = eur_amount
                                if price_usd:
                                    usd_amount_insert = value_bch * price_usd
                                grain_delta = math.ceil(compute_grain_reward_eur(eur_amount))
                                with engine.begin() as conn:
                                    conn.execute(
                                        text(
                                            """
                                            UPDATE users
                                            SET grain_balance = COALESCE(grain_balance, 0) + :grain_delta
                                            WHERE id = :id
                                            """
                                        ),
                                        {"id": user_id, "grain_delta": grain_delta},
                                    )
                                display_name = str(username) if username else f"user {user_id}"
                                description = f"{display_name} (+{grain_delta} grain)"
                            else:
                                print("⚠️  Skipping grain_balance update: BCH/EUR price unavailable")
                    else:
                        # Threshold not met within 30 minutes → use price-based method (same as post-window)
                        value_bch = float(event.get("value_bch", 0.0) or 0.0)
                        price_eur = get_bch_eur_price_cached()
                        price_usd = get_bch_usd_price_cached()
                        if price_eur:
                            eur_amount = value_bch * price_eur
                            euro_amount_insert = eur_amount
                            if price_usd:
                                usd_amount_insert = value_bch * price_usd
                            grain_delta = math.ceil(compute_grain_reward_eur(eur_amount))
                            with engine.begin() as conn:
                                conn.execute(
                                    text(
                                        """
                                        UPDATE users
                                        SET grain_balance = COALESCE(grain_balance, 0) + :grain_delta
                                        WHERE id = :id
                                        """
                                    ),
                                    {"id": user_id, "grain_delta": grain_delta},
                                )
                            display_name = str(username) if username else f"user {user_id}"
                            description = f"{display_name} (+{grain_delta} grain)"
                        else:
                            print("⚠️  Skipping grain_balance update: BCH/EUR price unavailable")
                else:
                    # Window passed or no threshold configured → price-based method
                    value_bch = float(event.get("value_bch", 0.0) or 0.0)
                    price_eur = get_bch_eur_price_cached()
                    price_usd = get_bch_usd_price_cached()
                    if price_eur:
                        eur_amount = value_bch * price_eur
                        euro_amount_insert = eur_amount
                        if price_usd:
                            usd_amount_insert = value_bch * price_usd
                        grain_delta = math.ceil(compute_grain_reward_eur(eur_amount))
                        with engine.begin() as conn:
                            conn.execute(
                                text(
                                    """
                                    UPDATE users
                                    SET grain_balance = COALESCE(grain_balance, 0) + :grain_delta
                                    WHERE id = :id
                                    """
                                ),
                                {"id": user_id, "grain_delta": grain_delta},
                            )
                        display_name = str(username) if username else f"user {user_id}"
                        description = f"{display_name} (+{grain_delta} grain)"
                    else:
                        print("⚠️  Skipping grain_balance update: BCH/EUR price unavailable")
            except Exception as e:
                print(f"⚠️  Failed to update grain_balance for user_id {user_id}: {e}")
        else:
            alias = None
            stream_name = None
            # For device-linked payments, compute euro_amount from current price if available
            value_bch = float(event.get("value_bch", 0.0) or 0.0)
            price_eur_for_device = get_bch_eur_price_cached()
            price_usd_for_device = get_bch_usd_price_cached()
            if price_eur_for_device:
                euro_amount_insert = value_bch * price_eur_for_device
            if price_usd_for_device:
                usd_amount_insert = value_bch * price_usd_for_device
            try:
                with engine.connect() as conn:
                    row = conn.execute(
                        text("SELECT alias, stream_name FROM devices WHERE id = :id LIMIT 1"),
                        {"id": device_id},
                    ).mappings().first()
                    if row:
                        alias = row.get("alias")
                        stream_name = row.get("stream_name")
            except Exception as e:
                print(f"⚠️  Failed to fetch alias for device_id {device_id}: {e}")
            reference = str(alias or device_id)
            if stream_name:
                description = str("Direct payment to " + stream_name)
            # Update feeding counters and last feeding timestamp for the device
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            UPDATE devices
                            SET total_feedings_today = COALESCE(total_feedings_today, 0) + 1,
                                total_feedings = COALESCE(total_feedings, 0) + 1,
                                last_feeding = :now_utc
                            WHERE id = :id
                            """
                        ),
                        {"id": device_id, "now_utc": datetime.now(timezone.utc)},
                    )
            except Exception as e:
                print(f"⚠️  Failed to update feeding counters for device_id {device_id}: {e}")
        address_str = str(event.get("address") or payment.address)
        write_payment_record(engine, tx_id, amount_sats, reference, description, address_str, euro_amount_insert, usd_amount_insert)

    def on_address_change(params: List) -> None:
        if not params:
            return
        address = params[0]

        def fetch_and_emit():
            try:
                with client_lock:
                    utxos = client.blockchain_address_listunspent(address)
                current_keys = {
                    (u.get("tx_hash"), u.get("tx_pos"))
                    for u in utxos
                    if u.get("tx_hash") is not None
                }
                known = known_utxos_by_addr.setdefault(address, set())
                new_keys = current_keys - known
                if new_keys:
                    for u in utxos:
                        key = (u.get("tx_hash"), u.get("tx_pos"))
                        if key in new_keys:
                            value_sats = int(u.get("value", 0) or 0)
                            height = int(u.get("height", -1) or -1)
                            status = (
                                "unconfirmed" if height == 0 else ("confirmed" if height > 0 else "unknown")
                            )
                            event = {
                                "address": address,
                                "tx_hash": u.get("tx_hash"),
                                "tx_pos": u.get("tx_pos"),
                                "value_sats": value_sats,
                                "value_bch": value_sats / 1e8,
                                "height": height,
                                "status": status,
                            }
                            print(
                                f"✅ {address} received {event['value_bch']:.8f} BCH ({value_sats} sats) "
                                f"in {event['tx_hash']}:{event['tx_pos']} [{status}]"
                            )
                            # Trigger logic:
                            # - User-linked address: process immediately (grain multipliers handled in handler)
                            # - Device-linked address: compute threshold from devices.crypto_feed_price (EUR → sats) and require >= threshold
                            payment = address_to_payment.get(address)
                            if payment:
                                if getattr(payment, "user_id", None) is not None:
                                    threshold_handler(payment, event)
                                else:
                                    device_id_for_payment = getattr(payment, "device_id", None)
                                    # Device-linked: compute dynamic threshold from crypto_feed_price (EUR) -> sats
                                    try:
                                        with engine.connect() as conn:
                                            crypto_price_eur = conn.execute(
                                                text("SELECT crypto_feed_price FROM devices WHERE id = :id LIMIT 1"),
                                                {"id": device_id_for_payment},
                                            ).scalar()
                                    except Exception as e:
                                        print(f"⚠️  Failed to fetch crypto_feed_price for device_id {device_id_for_payment}: {e}")
                                        crypto_price_eur = None
                                    if crypto_price_eur is None:
                                        # Fallback: process if we cannot fetch device price
                                        threshold_handler(payment, event)
                                    else:
                                        price_eur = get_bch_eur_price_cached()
                                        if price_eur and price_eur > 0:
                                            threshold_sats = int(math.floor((float(crypto_price_eur) / float(price_eur)) * 1e8))
                                        else:
                                            # Price unavailable, fallback to processing
                                            threshold_sats = 0
                                        # Allow a 5% safety margin: trigger even if value is up to 5% below threshold
                                        effective_threshold = max(int(math.floor(threshold_sats * 0.95)), 0)
                                        if value_sats >= effective_threshold:
                                            threshold_handler(payment, event)
                known.clear()
                known.update(current_keys)
            except Exception as e:
                print(f"⚠️  Error processing address {address}: {e}")

        threading.Thread(target=fetch_and_emit, daemon=True).start()

    def on_new_block(params: List) -> None:
        # Optional: react to new blocks if desired
        pass

    # Register handlers
    client.subscribe("blockchain.address.subscribe", on_address_change)
    client.subscribe("blockchain.headers.subscribe", on_new_block)
    client.blockchain_headers_subscribe()
    # Connection watchdog to auto-reconnect and re-subscribe on drops
    def _resubscribe_all():
        # Re-register handlers (idempotent) and subscribe headers/addresses
        client.subscribe("blockchain.address.subscribe", on_address_change)
        client.subscribe("blockchain.headers.subscribe", on_new_block)
        client.blockchain_headers_subscribe()
        for addr in list(current_addresses):
            try:
                utxos = client.blockchain_address_listunspent(addr)
            except Exception:
                utxos = []
            known_utxos_by_addr[addr] = {
                (u.get("tx_hash"), u.get("tx_pos"))
                for u in utxos
                if u.get("tx_hash") is not None
            }
            try:
                client.blockchain_address_subscribe(addr)
            except Exception as e:
                print(f"⚠️  Subscribe failed for {addr}: {e}")
        print(f"🔁 Resubscribed to {len(current_addresses)} addresses.")

    def _connection_watchdog():
        # Periodically ping; if failed, reconnect and resubscribe
        while True:
            time.sleep(15)
            try:
                with client_lock:
                    client.server_ping()
            except Exception:
                print("🔌 Fulcrum connection appears down. Attempting to reconnect...")
                try:
                    with client_lock:
                        try:
                            client.disconnect()
                        except Exception:
                            pass
                        time.sleep(1)
                        if client.connect():
                            print(f"✅ Reconnected to Fulcrum. Restoring subscriptions for {len(current_addresses)} addresses...")
                            _resubscribe_all()
                        else:
                            print("❌ Reconnect failed; will retry...")
                except Exception as e:
                    print(f"❌ Error during reconnect: {e}")
    threading.Thread(target=_connection_watchdog, daemon=True).start()

    # Initialize from current DB state: set known UTXOs and subscribe each address
    payments: List[AddressConfig] = listener.get_payments()
    current_addresses: Set[str] = _build_address_set(payments)
    address_to_payment = {p.address: p for p in payments}
    for addr in current_addresses:
        try:
            with client_lock:
                utxos = client.blockchain_address_listunspent(addr)
        except Exception:
            utxos = []
        known_utxos_by_addr[addr] = {
            (u.get("tx_hash"), u.get("tx_pos"))
            for u in utxos
            if u.get("tx_hash") is not None
        }
        try:
            with client_lock:
                client.blockchain_address_subscribe(addr)
        except Exception as e:
            print(f"⚠️  Subscribe failed for {addr}: {e}")

    try:
        print(f"🔔 Subscribed to {len(current_addresses)} addresses; syncing with DB changes...")
        while True:
            # Sync address list from DB listener (updated via NOTIFY)
            updated_payments: List[AddressConfig] = listener.get_payments()
            updated_addresses: Set[str] = _build_address_set(updated_payments)
            updated_map: Dict[str, AddressConfig] = {p.address: p for p in updated_payments}

            to_add = updated_addresses - current_addresses
            to_remove = current_addresses - updated_addresses

            for addr in to_remove:
                try:
                    with client_lock:
                        client.blockchain_address_unsubscribe(addr)
                except Exception:
                    pass
                known_utxos_by_addr.pop(addr, None)

            for addr in to_add:
                try:
                    with client_lock:
                        utxos = client.blockchain_address_listunspent(addr)
                except Exception:
                    utxos = []
                known_utxos_by_addr[addr] = {
                    (u.get("tx_hash"), u.get("tx_pos"))
                    for u in utxos
                    if u.get("tx_hash") is not None
                }
                try:
                    with client_lock:
                        client.blockchain_address_subscribe(addr)
                except Exception as e:
                    print(f"⚠️  Subscribe failed for {addr}: {e}")

            current_addresses = updated_addresses
            address_to_payment = updated_map
            if to_add or to_remove:
                print(f"👀 Monitoring {len(current_addresses)} addresses (added {len(to_add)}, removed {len(to_remove)}).")

            time.sleep(SYNC_INTERVAL_SECS)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping monitor...")
    except Exception as e:
        print(f"❌ Monitor error: {e}")
    finally:
        client.disconnect()
        listener.disconnect()
        # Stop price refresher thread
        try:
            _PRICE_STOP_EVENT.set()
        except Exception:
            pass


if __name__ == "__main__":
    run_monitor()
