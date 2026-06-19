"""
MQTT Subscriber
===============
Connects to HiveMQ public broker and listens on TWO topics:

  Topic 1: abdul_bms/power_temp
    Payload: {"voltage": 12.50, "current": 2.50, "power": 31.25, "temp": 28.40}

  Topic 2: abdul_bms/cell_voltages
    Payload: {"cell1": 4.12, "cell2": 4.10, "cell3": 4.15}

Battery pack: 3S5P — 15 cells total (3 groups in series, 5 in parallel per group)
  - Pack voltage  ≈ 12V  (sum of 3 series groups, each ~4V)
  - Pack capacity ≈ 15Ah (5× single-cell capacity in parallel)
  - Cell voltages measured per SERIES GROUP (one reading per group)

Data flow:
  Both topics are received → merged into a combined reading →
  ML inference runs → result written to Supabase.

Merging strategy:
  A short-lived buffer (_pending) holds the most recent payload from each topic.
  When both topics have been received (within MERGE_WINDOW_SEC of each other),
  inference + DB write fire once and the buffer is cleared.

Also exposes get_mqtt_status() so the /status API endpoint
can report connection state to the mobile app.
"""

import json
import os
import threading
import time
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from ml_inference import predict_soc
from supabase_client import insert_battery_reading

load_dotenv()

MQTT_HOST         = os.getenv("MQTT_HOST",  "broker.hivemq.com")
MQTT_PORT         = int(os.getenv("MQTT_PORT", 1883))
TOPIC_POWER_TEMP  = os.getenv("MQTT_TOPIC_POWER_TEMP",   "abdul_bms/power_temp")
TOPIC_CELL_V      = os.getenv("MQTT_TOPIC_CELL_VOLTAGES", "abdul_bms/cell_voltages")

# How many seconds apart the two topic payloads can arrive and still be merged.
MERGE_WINDOW_SEC  = 5.0

# ── Shared state ───────────────────────────────────────────────────────────────
_lock = threading.Lock()

# Tracks MQTT connection status for /status API endpoint
_status = {
    "connected":       False,
    "last_message_at": None,   # ISO timestamp of last message received
}

# Buffer to merge payloads arriving on the two separate topics
_pending = {
    "power_temp":    None,   # dict from abdul_bms/power_temp
    "cell_voltages": None,   # dict from abdul_bms/cell_voltages
    "pt_time":       None,   # epoch seconds when power_temp arrived
    "cv_time":       None,   # epoch seconds when cell_voltages arrived
}


# ── Status accessor (called by main.py /status route) ─────────────────────────
def get_mqtt_status() -> dict:
    with _lock:
        return dict(_status)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _try_merge_and_process():
    """
    Called after every message. If both payloads are present and were received
    within MERGE_WINDOW_SEC of each other, run inference and write to Supabase.
    Must be called while holding _lock.
    """
    pt = _pending["power_temp"]
    cv = _pending["cell_voltages"]

    if pt is None or cv is None:
        return  # still waiting for the other topic

    # Check timestamps are close enough
    age = abs((_pending["pt_time"] or 0) - (_pending["cv_time"] or 0))
    if age > MERGE_WINDOW_SEC:
        # The older payload is stale — drop it and wait for a fresh pair
        if (_pending["pt_time"] or 0) < (_pending["cv_time"] or 0):
            _pending["power_temp"] = None
            _pending["pt_time"]    = None
        else:
            _pending["cell_voltages"] = None
            _pending["cv_time"]       = None
        print(f"[MQTT] Payloads too far apart ({age:.1f}s) - waiting for fresh pair")
        return

    # ── Both payloads ready — extract fields ─────────────────────────────────
    # power_temp payload: voltage, current, power, temp  (all floats, 2 d.p.)
    voltage = pt.get("voltage")
    current = pt.get("current")
    power   = pt.get("power")
    temp    = pt.get("temp")          # NOTE: field is "temp" not "temperature"

    # cell_voltages payload: cell1, cell2, cell3  (floats, 2 d.p.)
    cell1 = cv.get("cell1")
    cell2 = cv.get("cell2")
    cell3 = cv.get("cell3")

    # Clear the buffer so the next round starts fresh
    _pending["power_temp"]    = None
    _pending["cell_voltages"] = None
    _pending["pt_time"]       = None
    _pending["cv_time"]       = None

    # Validate required fields
    if None in (voltage, current, power, temp):
        print(f"[MQTT] ⚠️  Missing power/temp fields — got: {pt}")
        return

    print(f"[MQTT] V={voltage}V  I={current}A  P={power}W  T={temp}C")
    if all(v is not None for v in [cell1, cell2, cell3]):
        print(f"[MQTT] Cell groups -> C1={cell1}V  C2={cell2}V  C3={cell3}V")
    else:
        print("[MQTT] Cell voltages missing - will use fallback avg")

    # ── ML Inference ─────────────────────────────────────────────────────────
    prediction = None
    try:
        prediction = predict_soc(
            voltage=voltage,
            current=current,
            temperature=temp,     # map "temp" → "temperature" for the model
            power=power,
            cell1=cell1,
            cell2=cell2,
            cell3=cell3,
        )
    except Exception as e:
        print(f"[ML] Inference error: {e}")

    # ── Write to Supabase ─────────────────────────────────────────────────────
    try:
        insert_battery_reading(
            voltage=     voltage,
            current=     current,
            power=       power,
            temperature= temp,
            soc=         prediction["soc"]          if prediction else None,
            soh=         prediction["soh"]          if prediction else None,
            min_cell_soc=prediction["min_cell_soc"] if prediction else None,
            cell1_soc=   prediction["cell1_soc"]    if prediction else None,
            cell2_soc=   prediction["cell2_soc"]    if prediction else None,
            cell3_soc=   prediction["cell3_soc"]    if prediction else None,
            is_charging= prediction["is_charging"]  if prediction else None,
            soc_method=  prediction["soc_method"]   if prediction else None,
            c_rate=      prediction["c_rate"]       if prediction else None,
            cell1=cell1,
            cell2=cell2,
            cell3=cell3,
        )
        print("[DB] Written to Supabase")
    except Exception as e:
        print(f"[DB] Supabase write error: {e}")



# ── MQTT callbacks ─────────────────────────────────────────────────────────────

def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        # Subscribe to BOTH topics
        client.subscribe(TOPIC_POWER_TEMP, qos=0)
        client.subscribe(TOPIC_CELL_V,     qos=0)
        print(f"[MQTT] Subscribed to: {TOPIC_POWER_TEMP}")
        print(f"[MQTT] Subscribed to: {TOPIC_CELL_V}")
        with _lock:
            _status["connected"] = True
    else:
        print(f"[MQTT] Connection failed with code {rc}")
        with _lock:
            _status["connected"] = False


def _on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8")

    # Update last-seen timestamp on every message
    now = time.time()
    with _lock:
        _status["last_message_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print(f"[MQTT] Bad JSON on {topic}: {payload}")
        return

    with _lock:
        if topic == TOPIC_POWER_TEMP:
            _pending["power_temp"] = data
            _pending["pt_time"]    = now
            print(f"[MQTT] power_temp received -> V={data.get('voltage')}  I={data.get('current')}  P={data.get('power')}  T={data.get('temp')}")
            _try_merge_and_process()

        elif topic == TOPIC_CELL_V:
            _pending["cell_voltages"] = data
            _pending["cv_time"]       = now
            print(f"[MQTT] cell_voltages received -> C1={data.get('cell1')}  C2={data.get('cell2')}  C3={data.get('cell3')}")
            _try_merge_and_process()

        else:
            print(f"[MQTT] Unknown topic: {topic}")


def _on_disconnect(client, userdata, rc, properties=None):
    print(f"[MQTT] Disconnected (rc={rc}). Will auto-reconnect...")
    with _lock:
        _status["connected"] = False


# ── Start client ───────────────────────────────────────────────────────────────

def start_mqtt_client():
    """Create and start the MQTT client (runs in background thread)."""
    client = mqtt.Client(
        client_id="bms_fastapi_backend",
        protocol=mqtt.MQTTv5,
    )
    client.on_connect    = _on_connect
    client.on_message    = _on_message
    client.on_disconnect = _on_disconnect

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()   # non-blocking background thread
    return client
