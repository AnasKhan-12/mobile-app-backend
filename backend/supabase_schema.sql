-- =============================================================
-- Battery BMS — Supabase Schema (Updated: per-cell SoC)
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- =============================================================

-- 1. Main readings table
CREATE TABLE IF NOT EXISTS battery_readings (
    id              BIGSERIAL PRIMARY KEY,

    -- Power & Temperature (from topic: abdul_bms/power_temp)
    voltage         FLOAT NOT NULL,       -- total pack voltage (~12V)
    current         FLOAT NOT NULL,       -- pack current (A)
    power           FLOAT NOT NULL,       -- total pack power (W)
    temperature     FLOAT NOT NULL,       -- temperature (°C)

    -- Cell voltages (from topic: abdul_bms/cell_voltages)
    cell1_voltage   FLOAT,               -- individual cell 1 voltage (V)
    cell2_voltage   FLOAT,               -- individual cell 2 voltage (V)
    cell3_voltage   FLOAT,               -- individual cell 3 voltage (V)

    -- Pack-level ML Predictions
    soc             FLOAT,               -- avg pack SoC (0–100 %)
    soh             FLOAT,               -- pack SoH (0–100 %)
    min_cell_soc    FLOAT,               -- weakest cell SoC — used for alerts
    is_charging     BOOLEAN,
    soc_method      TEXT,                -- ocv_lookup | lightgbm | mixed
    c_rate          FLOAT,               -- per-cell C-rate used for inference

    -- Per-cell ML Predictions
    cell1_soc       FLOAT,               -- SoC of cell 1 (0–100 %)
    cell2_soc       FLOAT,               -- SoC of cell 2 (0–100 %)
    cell3_soc       FLOAT,               -- SoC of cell 3 (0–100 %)

    -- Timestamp
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Index for fast time-ordered queries
CREATE INDEX IF NOT EXISTS idx_battery_readings_timestamp
    ON battery_readings (timestamp DESC);

-- 3. Enable Supabase Realtime (so React Native gets live push updates)
ALTER PUBLICATION supabase_realtime ADD TABLE battery_readings;

-- 4. Row-Level Security
ALTER TABLE battery_readings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read"
    ON battery_readings FOR SELECT
    USING (true);

CREATE POLICY "Allow service-role insert"
    ON battery_readings FOR INSERT
    WITH CHECK (true);


-- =============================================================
-- IF TABLE ALREADY EXISTS — run this instead to add new columns
-- =============================================================
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS cell1_soc    FLOAT;
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS cell2_soc    FLOAT;
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS cell3_soc    FLOAT;
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS min_cell_soc FLOAT;
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS soh          FLOAT;
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS soc_method   TEXT;
-- ALTER TABLE battery_readings ADD COLUMN IF NOT EXISTS c_rate       FLOAT;
