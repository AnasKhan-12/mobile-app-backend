/**
 * Battery Monitor — React Native App
 * ====================================
 * Connects to the FastAPI backend and displays live battery data.
 *
 * HOW TO CONFIGURE:
 *   Change API_BASE_URL below to your PC's local WiFi IP address.
 *   Your PC and phone must be on the same WiFi network.
 *
 *   Find your PC's IP:
 *     Windows → open Command Prompt → run: ipconfig
 *     Look for "IPv4 Address" under your WiFi adapter.
 *
 *   Example: const API_BASE_URL = 'http://192.168.1.100:8000';
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    View,
    Text,
    ScrollView,
    Animated,
    Dimensions,
    TouchableOpacity,
    StatusBar,
    SafeAreaView,
    useColorScheme,
    ActivityIndicator,
} from 'react-native';

// ─── ⚙️  CONFIG — Change this to your PC's WiFi IP ───────────────────────────
const API_BASE_URL = 'https://bms-backend-lbk7.onrender.com';
const POLL_INTERVAL_MS = 3000;   // fetch new data every 3 seconds
// ──────────────────────────────────────────────────────────────────────────────

const { width } = Dimensions.get('window');

// ─── Theme Definitions ────────────────────────────────────────────────────────
const SKY      = '#38bdf8';
const SKY_DARK = '#0ea5e9';

const THEMES = {
    dark: {
        bg:          '#080c14',
        surface:     'rgba(255,255,255,0.03)',
        border:      'rgba(255,255,255,0.07)',
        headerBorder:'rgba(255,255,255,0.05)',
        trackColor:  'rgba(255,255,255,0.08)',
        text:        '#ffffff',
        textSub:     'rgba(255,255,255,0.35)',
        textMuted:   'rgba(255,255,255,0.45)',
        textFaint:   'rgba(255,255,255,0.2)',
        accent:      SKY,
        cycleBarBg:  'rgba(255,255,255,0.08)',
        statusBar:   'light-content',
        statusBarBg: '#080c14',
        shadow:      {},
    },
    light: {
        bg:          '#f0f7ff',
        surface:     '#ffffff',
        border:      SKY + '60',
        headerBorder:SKY + '30',
        trackColor:  '#daeefa',
        text:        '#0c1a2e',
        textSub:     '#4a6a8a',
        textMuted:   '#5a7a9a',
        textFaint:   '#93b3cc',
        accent:      SKY_DARK,
        cycleBarBg:  '#cce8f8',
        statusBar:   'dark-content',
        statusBarBg: '#f0f7ff',
        shadow: {
            shadowColor:   SKY_DARK,
            shadowOffset:  { width: 0, height: 2 },
            shadowOpacity: 0.12,
            shadowRadius:  8,
            elevation:     3,
        },
    },
};

// ─── Default empty state (shown before first fetch) ───────────────────────────
const EMPTY_BATTERY = {
    soc:          null,
    soh:          null,
    voltage:      null,
    current:      null,
    power:        null,
    temperature:  null,
    isCharging:   null,
    cell1Voltage: null,
    cell2Voltage: null,
    cell3Voltage: null,
    cell1Soc:     null,
    cell2Soc:     null,
    cell3Soc:     null,
    minCellSoc:   null,
    socMethod:    null,
    cRate:        null,
    timestamp:    null,
};

// ─── Arc Drawing ──────────────────────────────────────────────────────────────
const Arc = ({ value, size, strokeWidth, color }) => {
    const angle      = (value / 100) * 360;
    const firstHalf  = Math.min(angle, 180);
    const secondHalf = Math.max(0, angle - 180);
    return (
        <View style={{ position: 'absolute', width: size, height: size }}>
            <View style={{ position: 'absolute', width: size, height: size, borderRadius: size / 2, overflow: 'hidden' }}>
                <View style={{ position: 'absolute', width: size / 2, height: size, left: size / 2, overflow: 'hidden' }}>
                    <View style={{
                        width: size, height: size, borderRadius: size / 2,
                        borderWidth: strokeWidth, borderColor: firstHalf > 0 ? color : 'transparent',
                        position: 'absolute', left: -size / 2,
                        transform: [{ rotate: `${-90 + firstHalf}deg` }],
                    }} />
                </View>
            </View>
            {secondHalf > 0 && (
                <View style={{ position: 'absolute', width: size, height: size, borderRadius: size / 2, overflow: 'hidden' }}>
                    <View style={{ position: 'absolute', width: size / 2, height: size, left: 0, overflow: 'hidden' }}>
                        <View style={{
                            width: size, height: size, borderRadius: size / 2,
                            borderWidth: strokeWidth, borderColor: color,
                            position: 'absolute', left: 0,
                            transform: [{ rotate: `${90 + secondHalf - 180}deg` }],
                        }} />
                    </View>
                </View>
            )}
        </View>
    );
};

// ─── Circular Gauge ───────────────────────────────────────────────────────────
const CircularGauge = ({ value, size, strokeWidth, color, label, unit, sublabel, T }) => {
    const displayValue = value !== null && value !== undefined ? Math.round(value) : null;
    const arcValue = displayValue !== null ? displayValue : 0;
    return (
        <View style={{ alignItems: 'center', width: size }}>
            <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
                <View style={{
                    position: 'absolute', width: size, height: size,
                    borderRadius: size / 2, borderWidth: strokeWidth, borderColor: T.trackColor,
                }} />
                <Arc value={arcValue} size={size} strokeWidth={strokeWidth} color={color} />
                <View style={{ alignItems: 'center' }}>
                    {displayValue !== null ? (
                        <Text style={{ color: T.text, fontSize: size * 0.22, fontWeight: '700', letterSpacing: -1 }}>
                            {displayValue}
                            <Text style={{ fontSize: size * 0.12, fontWeight: '400', color: T.textMuted }}>{unit}</Text>
                        </Text>
                    ) : (
                        <Text style={{ color: T.textMuted, fontSize: size * 0.14, fontWeight: '400' }}>--</Text>
                    )}
                    {sublabel ? (
                        <Text style={{ color: T.accent, fontSize: 9, marginTop: 2, letterSpacing: 1.5, textTransform: 'uppercase', fontWeight: '700' }}>
                            {sublabel}
                        </Text>
                    ) : null}
                </View>
            </View>
            <Text style={{ color: T.textMuted, fontSize: 10, marginTop: 8, letterSpacing: 2, textTransform: 'uppercase' }}>{label}</Text>
        </View>
    );
};

// ─── Metric Card ──────────────────────────────────────────────────────────────
const MetricCard = ({ label, value, unit, icon, color, T, isLight }) => {
    const anim = useRef(new Animated.Value(0)).current;
    useEffect(() => {
        Animated.spring(anim, { toValue: 1, useNativeDriver: true, tension: 60, friction: 8 }).start();
    }, []);
    const displayValue = value !== null && value !== undefined
        ? (typeof value === 'number' ? value.toFixed(2) : value)
        : '--';
    return (
        <Animated.View style={[{
            backgroundColor: T.surface,
            borderRadius: 16,
            borderWidth: isLight ? 1.5 : 1,
            borderColor: isLight ? SKY + '60' : T.border,
            padding: 14,
            width: (width - 42) / 2,
            ...T.shadow,
        }, { opacity: anim, transform: [{ scale: anim }] }]}>
            <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: color + '22', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>
                <Text style={{ fontSize: 18 }}>{icon}</Text>
            </View>
            <Text style={{ color: T.textMuted, fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase' }}>{label}</Text>
            <Text style={{ color, fontSize: 22, fontWeight: '700', marginTop: 4, letterSpacing: -0.5 }}>
                {displayValue}
                {value !== null && value !== undefined && (
                    <Text style={{ fontSize: 11, fontWeight: '400', color: T.textMuted }}> {unit}</Text>
                )}
            </Text>
        </Animated.View>
    );
};

// ─── Cell SoC Row ─────────────────────────────────────────────────────────────
const CellSocRow = ({ cell1Soc, cell2Soc, cell3Soc, minCellSoc, T, isLight }) => {
    const cells = [
        { label: 'Cell 1', value: cell1Soc },
        { label: 'Cell 2', value: cell2Soc },
        { label: 'Cell 3', value: cell3Soc },
    ];
    const getColor = (v) => {
        if (v === null || v === undefined) return T.textMuted;
        if (v > 60) return '#4ade80';
        if (v > 30) return '#facc15';
        return '#f87171';
    };
    return (
        <View style={{
            backgroundColor: T.surface, borderRadius: 16, padding: 16,
            borderWidth: isLight ? 1.5 : 1,
            borderColor: isLight ? SKY + '60' : T.border,
            ...T.shadow,
        }}>
            <Text style={{ color: T.textMuted, fontSize: 10, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 }}>
                Per-Cell State of Charge
            </Text>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                {cells.map((cell, i) => {
                    const color = getColor(cell.value);
                    const pct = cell.value !== null ? cell.value : 0;
                    return (
                        <View key={i} style={{ alignItems: 'center', flex: 1 }}>
                            <Text style={{ color: T.textFaint, fontSize: 9, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 6 }}>
                                {cell.label}
                            </Text>
                            {/* Mini bar */}
                            <View style={{ width: 28, height: 60, backgroundColor: T.trackColor, borderRadius: 6, justifyContent: 'flex-end', overflow: 'hidden' }}>
                                <View style={{
                                    width: '100%',
                                    height: `${pct}%`,
                                    backgroundColor: color,
                                    borderRadius: 6,
                                }} />
                            </View>
                            <Text style={{ color, fontSize: 13, fontWeight: '700', marginTop: 6 }}>
                                {cell.value !== null && cell.value !== undefined ? `${cell.value.toFixed(1)}%` : '--'}
                            </Text>
                        </View>
                    );
                })}
            </View>
            {minCellSoc !== null && minCellSoc !== undefined && (
                <View style={{ marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: T.border, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text style={{ color: T.textMuted, fontSize: 10, letterSpacing: 1 }}>Weakest Cell (limits pack)</Text>
                    <Text style={{ color: getColor(minCellSoc), fontSize: 14, fontWeight: '700' }}>
                        {minCellSoc.toFixed(1)}%
                    </Text>
                </View>
            )}
        </View>
    );
};

// ─── Connection Status Badge ───────────────────────────────────────────────────
const ConnectionBadge = ({ connected, loading }) => {
    const pulse = useRef(new Animated.Value(1)).current;
    useEffect(() => {
        if (!connected || loading) return;
        const loop = Animated.loop(Animated.sequence([
            Animated.timing(pulse, { toValue: 1.4, duration: 800, useNativeDriver: true }),
            Animated.timing(pulse, { toValue: 1,   duration: 800, useNativeDriver: true }),
        ]));
        loop.start();
        return () => loop.stop();
    }, [connected, loading]);

    if (loading) {
        return (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <ActivityIndicator size="small" color={SKY} />
                <Text style={{ fontSize: 10, fontWeight: '700', letterSpacing: 2, color: SKY }}>CONNECTING</Text>
            </View>
        );
    }
    const color = connected ? '#4ade80' : '#f87171';
    const label = connected ? 'LIVE' : 'DISCONNECTED';
    return (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Animated.View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: color, transform: [{ scale: connected ? pulse : 1 }] }} />
            <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 2, color }}>{label}</Text>
        </View>
    );
};

// ─── Battery Status Badge ─────────────────────────────────────────────────────
const BatteryStatusBadge = ({ soc, isCharging }) => {
    if (isCharging !== null && isCharging !== undefined) {
        if (isCharging) {
            return (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Text style={{ width: 7, height: 7, fontSize: 10 }}>⚡</Text>
                    <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 2, color: '#4ade80' }}>CHARGING</Text>
                </View>
            );
        }
    }
    if (soc === null || soc === undefined) return null;
    let label = 'NORMAL';
    let color = '#4ade80';
    if (soc < 20)      { label = 'CRITICAL'; color = '#f87171'; }
    else if (soc < 40) { label = 'LOW';      color = '#facc15'; }
    return (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: color }} />
            <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 2, color }}>{label}</Text>
        </View>
    );
};

// ─── Theme Controls ───────────────────────────────────────────────────────────
const ThemeControls = ({ themeMode, onToggle, T }) => (
    <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
        {['auto', 'light', 'dark'].map((mode) => {
            const active = themeMode === mode;
            const label  = mode === 'auto' ? '⚙ AUTO' : mode === 'light' ? '☀️' : '🌙';
            return (
                <TouchableOpacity
                    key={mode}
                    onPress={() => onToggle(mode)}
                    style={{
                        paddingHorizontal: 9, paddingVertical: 3, borderRadius: 20,
                        backgroundColor: active ? T.accent + '25' : 'transparent',
                        borderWidth: 1,
                        borderColor: active ? T.accent : T.border,
                    }}
                >
                    <Text style={{ fontSize: mode === 'auto' ? 9 : 12, color: active ? T.accent : T.textMuted, fontWeight: '700' }}>
                        {label}
                    </Text>
                </TouchableOpacity>
            );
        })}
    </View>
);

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
    const systemScheme = useColorScheme();
    const [themeMode, setThemeMode] = useState('auto');
    const theme   = themeMode === 'auto' ? (systemScheme || 'dark') : themeMode;
    const T       = THEMES[theme];
    const isLight = theme === 'light';

    // ── Data state
    const [battery, setBattery]       = useState(EMPTY_BATTERY);
    const [connected, setConnected]   = useState(false);
    const [loading, setLoading]       = useState(true);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [socHistory, setSocHistory]  = useState([]);

    const headerAnim = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        Animated.timing(headerAnim, { toValue: 1, duration: 600, useNativeDriver: true }).start();
    }, []);

    // ── Fetch latest reading from FastAPI backend ─────────────────────────────
    const fetchLatest = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/latest`, {
                method:  'GET',
                headers: { 'Content-Type': 'application/json' },
                // 5 second timeout
                signal:  AbortSignal.timeout(5000),
            });

            if (!response.ok) {
                // Server reachable but no data yet (404 = no readings yet)
                if (response.status === 404) {
                    setConnected(true);   // server is up, just no ESP32 data
                    setLoading(false);
                    return;
                }
                throw new Error(`Server error: ${response.status}`);
            }

            const row = await response.json();

            // Map API response → app state
            setBattery({
                soc:          row.soc          ?? row.soc_percent          ?? null,
                soh:          row.soh          ?? row.soh_percent          ?? null,
                voltage:      row.voltage      ?? null,
                current:      row.current      ?? null,
                power:        row.power        ?? null,
                temperature:  row.temperature  ?? null,
                isCharging:   row.is_charging  ?? null,
                cell1Voltage: row.cell1_voltage ?? null,
                cell2Voltage: row.cell2_voltage ?? null,
                cell3Voltage: row.cell3_voltage ?? null,
                cell1Soc:     row.cell1_soc    ?? null,
                cell2Soc:     row.cell2_soc    ?? null,
                cell3Soc:     row.cell3_soc    ?? null,
                minCellSoc:   row.min_cell_soc ?? null,
                socMethod:    row.soc_method   ?? null,
                cRate:        row.c_rate       ?? null,
                timestamp:    row.timestamp    ?? null,
            });

            // Maintain a short SoC history for the sparkline
            if (row.soc !== null && row.soc !== undefined) {
                setSocHistory(prev => [...prev.slice(-11), row.soc]);
            }

            setConnected(true);
            setLoading(false);
            setLastUpdated(new Date().toLocaleTimeString());

        } catch (err) {
            // Network unreachable or timeout
            setConnected(false);
            setLoading(false);
            console.warn('[BMS] Fetch error:', err.message);
        }
    }, []);

    // ── Poll every POLL_INTERVAL_MS ───────────────────────────────────────────
    useEffect(() => {
        fetchLatest();  // immediate first fetch
        const interval = setInterval(fetchLatest, POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [fetchLatest]);

    // ── Derived colors ────────────────────────────────────────────────────────
    const socColor = battery.soc === null ? T.trackColor
        : battery.soc > 60 ? '#4ade80' : battery.soc > 30 ? '#facc15' : '#f87171';
    const sohColor = isLight ? SKY_DARK : SKY;

    // ── SoC sparkline (last 12 readings) ─────────────────────────────────────
    const SocSparkline = () => {
        if (socHistory.length < 2) return null;
        const max = Math.max(...socHistory, 1);
        return (
            <View style={{
                backgroundColor: T.surface, borderRadius: 16, padding: 16,
                borderWidth: isLight ? 1.5 : 1,
                borderColor: isLight ? SKY + '60' : T.border,
                ...T.shadow,
            }}>
                <Text style={{ color: T.textMuted, fontSize: 10, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 }}>
                    SoC History (last {socHistory.length} readings)
                </Text>
                <View style={{ flexDirection: 'row', alignItems: 'flex-end', height: 64, gap: 4 }}>
                    {socHistory.map((val, i) => (
                        <View key={i} style={{ flex: 1, justifyContent: 'flex-end', height: 64 }}>
                            <View style={{
                                width: '100%',
                                height: Math.max(4, (val / max) * 60),
                                backgroundColor: i === socHistory.length - 1 ? socColor : socColor + '55',
                                borderRadius: 3,
                            }} />
                        </View>
                    ))}
                </View>
            </View>
        );
    };

    return (
        <SafeAreaView style={{ flex: 1, backgroundColor: T.bg }}>
            <StatusBar barStyle={T.statusBar} backgroundColor={T.statusBarBg} />
            <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>

                {/* ── Header ── */}
                <Animated.View style={{
                    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start',
                    paddingHorizontal: 20, paddingTop: 16, paddingBottom: 14,
                    borderBottomWidth: 1, borderBottomColor: T.headerBorder,
                    opacity: headerAnim,
                    transform: [{ translateY: headerAnim.interpolate({ inputRange: [0, 1], outputRange: [-20, 0] }) }],
                }}>
                    <View>
                        <Text style={{ color: T.text, fontSize: 16, fontWeight: '700', letterSpacing: 3 }}>Battery Monitor</Text>
                        <Text style={{ color: T.textSub, fontSize: 11, letterSpacing: 1, marginTop: 2 }}>3S5P Pack · Hybrid OCV + LightGBM</Text>
                    </View>
                    <View style={{ alignItems: 'flex-end' }}>
                        <ConnectionBadge connected={connected} loading={loading} />
                        <ThemeControls themeMode={themeMode} onToggle={setThemeMode} T={T} />
                    </View>
                </Animated.View>

                {/* ── Server disconnected banner ── */}
                {!loading && !connected && (
                    <View style={{
                        marginHorizontal: 16, marginTop: 12, borderRadius: 12,
                        backgroundColor: '#f8717120', borderWidth: 1, borderColor: '#f87171',
                        padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10,
                    }}>
                        <Text style={{ fontSize: 18 }}>⚠️</Text>
                        <View style={{ flex: 1 }}>
                            <Text style={{ color: '#f87171', fontWeight: '700', fontSize: 12 }}>Cannot reach server</Text>
                            <Text style={{ color: '#f8717188', fontSize: 10, marginTop: 2 }}>
                                Make sure the FastAPI server is running at {API_BASE_URL}
                            </Text>
                        </View>
                    </View>
                )}

                {/* ── No data yet banner (server up, ESP32 off) ── */}
                {!loading && connected && battery.soc === null && (
                    <View style={{
                        marginHorizontal: 16, marginTop: 12, borderRadius: 12,
                        backgroundColor: '#facc1520', borderWidth: 1, borderColor: '#facc15',
                        padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10,
                    }}>
                        <Text style={{ fontSize: 18 }}>🔋</Text>
                        <View style={{ flex: 1 }}>
                            <Text style={{ color: '#facc15', fontWeight: '700', fontSize: 12 }}>Server connected — waiting for ESP32</Text>
                            <Text style={{ color: '#facc1588', fontSize: 10, marginTop: 2 }}>
                                No readings yet. Power on the ESP32 to start receiving data.
                            </Text>
                        </View>
                    </View>
                )}

                {/* ── Gauges ── */}
                <View style={{
                    flexDirection: 'row', justifyContent: 'space-around',
                    paddingVertical: 32, paddingHorizontal: 16,
                    backgroundColor: T.surface,
                    marginTop: 12, marginHorizontal: 16, borderRadius: 20,
                    borderWidth: isLight ? 1.5 : 1,
                    borderColor: isLight ? SKY + '60' : T.border,
                    ...T.shadow,
                }}>
                    <CircularGauge value={battery.soc}  size={140} strokeWidth={10} color={socColor} label="State of Charge" unit="%" sublabel={battery.socMethod === 'ocv_lookup' ? 'SoC · OCV' : battery.socMethod === 'lightgbm' ? 'SoC · ML' : 'SoC'} T={T} />
                    <CircularGauge value={battery.soh}  size={140} strokeWidth={10} color={sohColor} label="State of Health"  unit="%" sublabel={battery.soh ? 'SoH' : 'Not Available'} T={T} />
                </View>

                {/* ── Battery Status Row ── */}
                <View style={{
                    marginHorizontal: 16, marginTop: 10,
                    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
                }}>
                    <BatteryStatusBadge soc={battery.soc} isCharging={battery.isCharging} />
                    {lastUpdated && (
                        <Text style={{ color: T.textFaint, fontSize: 10, letterSpacing: 1 }}>
                            Last update: {lastUpdated}
                        </Text>
                    )}
                </View>

                {/* ── Metric Cards ── */}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: 16, marginTop: 14, gap: 10 }}>
                    <MetricCard label="Voltage"     value={battery.voltage}     unit="V"   icon="⚡" color="#f59e0b" T={T} isLight={isLight} />
                    <MetricCard label="Current"     value={battery.current}     unit="A"   icon="🔌" color="#a78bfa" T={T} isLight={isLight} />
                    <MetricCard label="Temperature" value={battery.temperature} unit="°C"  icon="🌡" color="#fb923c" T={T} isLight={isLight} />
                    <MetricCard label="Power"       value={battery.power}       unit="W"   icon="💡" color="#34d399" T={T} isLight={isLight} />
                </View>

                {/* ── Per-Cell SoC ── */}
                <View style={{ marginHorizontal: 16, marginTop: 14 }}>
                    <CellSocRow
                        cell1Soc={battery.cell1Soc}
                        cell2Soc={battery.cell2Soc}
                        cell3Soc={battery.cell3Soc}
                        minCellSoc={battery.minCellSoc}
                        T={T}
                        isLight={isLight}
                    />
                </View>

                {/* ── SoC History Sparkline ── */}
                {socHistory.length >= 2 && (
                    <View style={{ marginHorizontal: 16, marginTop: 14 }}>
                        <SocSparkline />
                    </View>
                )}

                {/* ── Footer ── */}
                <Text style={{ textAlign: 'center', color: T.textFaint, fontSize: 10, letterSpacing: 1, marginTop: 20 }}>
                    {connected
                        ? `Polling every ${POLL_INTERVAL_MS / 1000}s · ${API_BASE_URL}`
                        : 'Not connected · Check server and WiFi'}
                </Text>

            </ScrollView>
        </SafeAreaView>
    );
}