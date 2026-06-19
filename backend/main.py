"""
FastAPI Backend — Battery Monitoring System
==========================================
Start with:  uvicorn main:app --reload --port 8000

Endpoints:
  GET  /           → health check + server status
  GET  /status     → MQTT connection state + last reading timestamp
  GET  /latest     → most recent single reading (used by mobile app)
  GET  /readings   → latest N readings from Supabase
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mqtt_client import start_mqtt_client, get_mqtt_status
from supabase_client import get_latest_readings
from models import LatestResponse

# ── MQTT lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MQTT subscriber when FastAPI starts up."""
    print("=" * 60)
    print("  Battery Monitoring Backend Starting...")
    print("=" * 60)
    mqtt = start_mqtt_client()
    yield
    # Shutdown
    mqtt.loop_stop()
    mqtt.disconnect()
    print("[MQTT] Disconnected cleanly")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Battery BMS API",
    description="Receives battery data via MQTT, runs ML inference, stores to Supabase",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # allows React Native app to call this server
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    """Basic health check — confirms the server is running."""
    return {
        "status":       "running",
        "service":      "Battery BMS Backend",
        "mqtt_broker":  "broker.hivemq.com:1883",
        "topics":       ["abdul_bms/power_temp", "abdul_bms/cell_voltages"],
        "docs":         "/docs",
    }


@app.get("/status")
def get_status():
    """
    Returns MQTT connection state + timestamp of last received reading.
    Used by the mobile app to show LIVE / DISCONNECTED indicator.
    """
    mqtt_status = get_mqtt_status()
    readings = get_latest_readings(limit=1)
    last_ts = readings[0]["timestamp"] if readings else None
    return {
        "mqtt_connected": mqtt_status["connected"],
        "last_message_at": mqtt_status["last_message_at"],
        "last_reading_timestamp": last_ts,
    }


@app.get("/latest", response_model=LatestResponse)
def get_latest():
    """
    Return the single most recent battery reading.
    This is the primary endpoint consumed by the React Native mobile app.
    Polled every 3 seconds by the app.
    """
    try:
        data = get_latest_readings(limit=1)
        if not data:
            raise HTTPException(status_code=404, detail="No readings yet — is the ESP32 sending data?")
        row = data[0]
        return LatestResponse(
            voltage=       row.get("voltage"),
            current=       row.get("current"),
            power=         row.get("power"),
            temperature=   row.get("temperature"),
            soc=           row.get("soc"),
            soh=           row.get("soh"),
            is_charging=   row.get("is_charging"),
            soc_method=    row.get("soc_method"),
            c_rate=        row.get("c_rate"),
            cell1_voltage= row.get("cell1_voltage"),
            cell2_voltage= row.get("cell2_voltage"),
            cell3_voltage= row.get("cell3_voltage"),
            cell1_soc=     row.get("cell1_soc"),
            cell2_soc=     row.get("cell2_soc"),
            cell3_soc=     row.get("cell3_soc"),
            min_cell_soc=  row.get("min_cell_soc"),
            timestamp=     row.get("timestamp"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/readings")
def get_readings(limit: int = 50):
    """Return the latest N battery readings from Supabase."""
    try:
        data = get_latest_readings(limit=limit)
        return {"count": len(data), "readings": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
