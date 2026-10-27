import React, { useState, useMemo, useEffect } from 'react';
import MetricCard from '../components/MetricCard';
import ChartPanel from '../components/ChartPanel';
import StatusBadge from '../components/StatusBadge';
import { useTelemetry } from '../hooks/useTelemetry';
import { apiClient } from '../api/client';

/**
 * TelemetryExplorerView Component
 * Raw telemetry time-series inspector, multi-channel comparison,
 * and tabular dataset browser with multiclass fault categorization.
 */
export default function TelemetryExplorerView() {
  const [historyLimit, setHistoryLimit] = useState(50);
  const [selectedChannel, setSelectedChannel] = useState('temp_core_max');
  const [searchTerm, setSearchTerm] = useState('');
  const [dataSource, setDataSource] = useState('observed'); // 'observed' | 'synthetic' | 'all'
  const [classFilter, setClassFilter] = useState('all');
  const [syntheticRecords, setSyntheticRecords] = useState([]);
  const [synLoading, setSynLoading] = useState(false);

  // Fetch actual continuous telemetry history from backend
  const { history, latestTelemetry, loading, error, refetch } = useTelemetry({
    pollIntervalMs: 5000,
    historyLimit,
    nodeId: 'node1'
  });

  // Fetch synthetic scenarios when requested
  useEffect(() => {
    if (dataSource === 'synthetic' || dataSource === 'all') {
      let isMounted = true;
      setSynLoading(true);
      apiClient.get('/models/multiclass-predictions', {
        params: { origin: dataSource === 'all' ? 'all' : 'synthetic', limit: historyLimit }
      }).then((res) => {
        if (isMounted) {
          const recs = res.data?.records || [];
          setSyntheticRecords(recs);
          setSynLoading(false);
        }
      }).catch(() => {
        if (isMounted) setSynLoading(false);
      });
      return () => { isMounted = false; };
    }
  }, [dataSource, historyLimit]);

  const channels = [
    { id: 'temp_core_max', label: 'Core Temp Max (°C)', unit: '°C', color: '#00f2fe' },
    { id: 'total_power', label: 'Total Power Draw (W)', unit: 'W', color: '#38bdf8' },
    { id: 'fan_rpm', label: 'Chassis Fan Velocity (RPM)', unit: 'RPM', color: '#34d399' },
    { id: 'inlet_temp', label: 'Inlet Ambient Temp (°C)', unit: '°C', color: '#a855f7' }
  ];

  const currentChannelMeta = channels.find((c) => c.id === selectedChannel) || channels[0];

  // Map history to ChartPanel format based on selected channel
  const chartData = useMemo(() => {
    return history
      .map((row) => {
        let val = row[selectedChannel];
        if (typeof val !== 'number') {
          if (selectedChannel === 'total_power') val = row.power;
          if (selectedChannel === 'temp_core_max') val = row.temperature;
        }

        return {
          timestamp: row.timestamp
            ? new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : '—',
          value: typeof val === 'number' ? Number(val.toFixed(2)) : null,
          is_anomaly: Boolean(row.is_anomaly)
        };
      })
      .filter((pt) => pt.value !== null);
  }, [history, selectedChannel]);

  // Combine records based on dataSource selection
  const activeRecords = useMemo(() => {
    if (dataSource === 'synthetic') {
      return syntheticRecords.map((r) => ({
        ...r,
        temp_core_max: r.p0_vdd_temp,
        power: r.total_power,
        fan_rpm: r.fan0_0,
        inlet_temp: r.ambient,
        is_anomaly: r.predicted_class !== 'normal'
      }));
    }
    if (dataSource === 'all') {
      const synMapped = syntheticRecords.map((r) => ({
        ...r,
        temp_core_max: r.p0_vdd_temp,
        power: r.total_power,
        fan_rpm: r.fan0_0,
        inlet_temp: r.ambient,
        is_anomaly: r.predicted_class !== 'normal'
      }));
      return [...history, ...synMapped];
    }
    return history;
  }, [dataSource, history, syntheticRecords]);

  // Filter table rows by search term and classFilter
  const filteredRecords = useMemo(() => {
    let list = activeRecords;
    if (classFilter !== 'all') {
      list = list.filter((r) => {
        const cls = String(r.predicted_class || (r.is_anomaly ? 'anomaly' : 'normal')).toLowerCase();
        return cls === classFilter.toLowerCase();
      });
    }
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      list = list.filter((r) => {
        const ts = String(r.timestamp || '').toLowerCase();
        const status = r.is_anomaly ? 'anomaly' : 'normal';
        const pClass = String(r.predicted_class || '').toLowerCase();
        const origin = String(r.data_origin || (r.is_simulated ? 'simulated' : 'observed')).toLowerCase();
        const scId = String(r.scenario_id || '').toLowerCase();
        return ts.includes(term) || status.includes(term) || pClass.includes(term) || origin.includes(term) || scId.includes(term);
      });
    }
    return list;
  }, [activeRecords, searchTerm, classFilter]);

  // Compute empirical stats over current window
  const summaryStats = useMemo(() => {
    const vals = chartData.map((d) => d.value).filter((v) => typeof v === 'number');
    if (vals.length === 0) {
      return { min: '—', max: '—', avg: '—', count: 0 };
    }
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    return {
      min: min.toFixed(1),
      max: max.toFixed(1),
      avg: avg.toFixed(1),
      count: vals.length
    };
  }, [chartData]);

  // Export current loaded records to standard CSV file
  const handleExportCSV = () => {
    if (!history || history.length === 0) return;
    const headers = ['timestamp', 'temp_core_max', 'total_power', 'fan_rpm', 'inlet_temp', 'is_anomaly'];
    const rows = history.map((r) => [
      r.timestamp || '',
      r.temp_core_max ?? r.temperature ?? '',
      r.total_power ?? r.power ?? '',
      r.fan_rpm ?? '',
      r.inlet_temp ?? '',
      r.is_anomaly ? '1' : '0'
    ]);

    const csvContent = [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `m100_node1_telemetry_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header and Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 className="gradient-text-aurora" style={{ margin: 0, fontSize: '18px', color: '#f8fafc', fontWeight: 700 }}>
            Raw Telemetry Stream & Channel Explorer
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
            Empirical multi-channel inspection for IBM Power AC922 (m100_node1) sensor streams.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          {/* History Limit Selector */}
          <select
            value={historyLimit}
            onChange={(e) => setHistoryLimit(Number(e.target.value))}
            style={{
              backgroundColor: 'rgba(30, 41, 59, 0.7)',
              color: '#cbd5e1',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '6px',
              padding: '6px 10px',
              fontSize: '11px',
              cursor: 'pointer'
            }}
          >
            <option value={25}>Latest 25 samples</option>
            <option value={50}>Latest 50 samples</option>
            <option value={100}>Latest 100 samples</option>
          </select>

          {/* Refresh Button */}
          <button
            onClick={refetch}
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              color: '#38bdf8',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            ↻ Refresh
          </button>

          {/* Export CSV Button */}
          <button
            onClick={handleExportCSV}
            style={{
              backgroundColor: '#0284c7',
              color: '#ffffff',
              border: 'none',
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Channel Toggles */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {channels.map((chan) => {
          const isActive = selectedChannel === chan.id;
          return (
            <button
              key={chan.id}
              onClick={() => setSelectedChannel(chan.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                borderRadius: '8px',
                border: isActive ? `1px solid ${chan.color}` : '1px solid rgba(56, 189, 248, 0.15)',
                backgroundColor: isActive ? 'rgba(14, 165, 233, 0.2)' : 'rgba(30, 41, 59, 0.45)',
                color: isActive ? '#f8fafc' : '#94a3b8',
                fontSize: '12px',
                fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: chan.color,
                  boxShadow: isActive ? `0 0 8px ${chan.color}` : 'none'
                }}
              />
              <span>{chan.label}</span>
            </button>
          );
        })}
      </div>

      {/* Selected Channel Summary Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <MetricCard
          title="Channel Current Value"
          value={
            latestTelemetry && latestTelemetry[selectedChannel] != null
              ? Number(latestTelemetry[selectedChannel]).toFixed(1)
              : 'Unavailable'
          }
          unit={currentChannelMeta.unit}
          status="NORMAL"
          source="m100_node1 sensor"
          timestamp={latestTelemetry?.timestamp ? new Date(latestTelemetry.timestamp).toLocaleTimeString() : undefined}
          icon="⚡"
        />

        <MetricCard
          title="Window Average (Mean)"
          value={summaryStats.avg}
          unit={currentChannelMeta.unit}
          status="OPTIMAL"
          source={`${summaryStats.count} Valid Observations`}
          subtext="Computed over window"
          icon="✓"
        />

        <MetricCard
          title="Window Minimum"
          value={summaryStats.min}
          unit={currentChannelMeta.unit}
          status="NORMAL"
          source="Observed Min Bound"
          icon="↓"
        />

        <MetricCard
          title="Window Maximum"
          value={summaryStats.max}
          unit={currentChannelMeta.unit}
          status="NORMAL"
          source="Observed Peak Bound"
          icon="↑"
        />
      </div>

      {/* Main Single-Channel Stream Chart */}
      <ChartPanel
        title={`${currentChannelMeta.label} Trajectory Over Time`}
        historicalData={chartData}
        forecastData={[]}
        yKey="value"
        unit={currentChannelMeta.unit}
        height={280}
      />

      {/* Tabular Telemetry Inspector */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.85)',
          border: '1px solid rgba(56, 189, 248, 0.18)',
          borderRadius: '10px',
          padding: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
              Dataset Observation Ledger
            </span>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              ({filteredRecords.length} records in buffer)
            </span>

            {/* Data Source Selector */}
            <div style={{ display: 'inline-flex', background: 'rgba(30, 41, 59, 0.6)', borderRadius: '6px', padding: '2px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
              <button
                onClick={() => setDataSource('observed')}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: dataSource === 'observed' ? 'rgba(6, 182, 212, 0.25)' : 'transparent',
                  color: dataSource === 'observed' ? '#22d3ee' : '#94a3b8'
                }}
              >
                ● Observed Telemetry
              </button>
              <button
                onClick={() => setDataSource('synthetic')}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: dataSource === 'synthetic' ? 'rgba(139, 92, 246, 0.25)' : 'transparent',
                  color: dataSource === 'synthetic' ? '#a78bfa' : '#94a3b8'
                }}
              >
                ★ Synthetic Scenarios
              </button>
              <button
                onClick={() => setDataSource('all')}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: dataSource === 'all' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                  color: dataSource === 'all' ? '#38bdf8' : '#94a3b8'
                }}
              >
                All Records
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Class Filter Dropdown */}
            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value)}
              style={{
                backgroundColor: 'rgba(30, 41, 59, 0.7)',
                color: '#cbd5e1',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '6px',
                padding: '6px 10px',
                fontSize: '11px',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="all">All Fault Categories</option>
              <option value="normal">Normal</option>
              <option value="thermal_anomaly">Thermal Anomaly</option>
              <option value="fan_performance_anomaly">Fan Performance Anomaly</option>
              <option value="power_anomaly">Power Anomaly</option>
              <option value="combined_anomaly">Combined Anomaly</option>
            </select>

            {/* Search Box */}
            <input
              type="text"
              placeholder="Search timestamp, class, origin..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                backgroundColor: 'rgba(30, 41, 59, 0.7)',
                color: '#cbd5e1',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '6px',
                padding: '6px 12px',
                fontSize: '11px',
                outline: 'none',
                width: '180px'
              }}
            />
          </div>
        </div>

        {/* Observation Table with Multiclass Classification */}
        <div style={{ overflowX: 'auto', maxHeight: '380px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(51, 65, 85, 0.6)', color: '#94a3b8', position: 'sticky', top: 0, backgroundColor: 'rgba(15, 23, 42, 0.95)', zIndex: 10 }}>
                <th style={{ padding: '8px 12px' }}>Timestamp</th>
                <th style={{ padding: '8px 12px' }}>Core Temp (°C)</th>
                <th style={{ padding: '8px 12px' }}>Total Power (W)</th>
                <th style={{ padding: '8px 12px' }}>Chassis Fan (RPM)</th>
                <th style={{ padding: '8px 12px' }}>Inlet Ambient (°C)</th>
                <th style={{ padding: '8px 12px' }}>Multiclass Classification</th>
                <th style={{ padding: '8px 12px' }}>Confidence</th>
                <th style={{ padding: '8px 12px' }}>Data Origin</th>
                <th style={{ padding: '8px 12px' }}>Outlier Gate</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                    {loading || synLoading ? 'Streaming observations from dataset...' : 'No telemetry records match query.'}
                  </td>
                </tr>
              ) : (
                filteredRecords.map((r, idx) => {
                  const coreTemp = r.temp_core_max ?? r.temperature ?? r.p0_vdd_temp;
                  const power = r.total_power ?? r.power;
                  const fan = r.fan_rpm ?? r.fan0_0;
                  const ambient = r.inlet_temp ?? r.ambient;
                  const predClass = r.predicted_class || (r.is_anomaly ? 'thermal_anomaly' : 'normal');
                  const conf = typeof r.confidence === 'number' ? (r.confidence * 100).toFixed(1) + '%' : '—';
                  const isSim = Boolean(r.is_simulated || r.data_origin === 'synthetic');
                  const originLabel = isSim ? 'SIMULATED' : 'OBSERVED';

                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid rgba(51, 65, 85, 0.35)',
                        backgroundColor: predClass !== 'normal'
                          ? 'rgba(239, 68, 68, 0.08)'
                          : isSim
                          ? 'rgba(139, 92, 246, 0.04)'
                          : 'transparent'
                      }}
                    >
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#cbd5e1', fontSize: '11px' }}>
                        {r.timestamp || 'Recorded Sample'}
                        {r.scenario_id && r.scenario_id !== 'observed_stream' && (
                          <span style={{ display: 'block', fontSize: '10px', color: '#a78bfa' }}>
                            {r.scenario_id}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#00f2fe' }}>
                        {typeof coreTemp === 'number' ? Number(coreTemp).toFixed(1) : 'Unavailable'}
                      </td>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#38bdf8' }}>
                        {typeof power === 'number' ? Number(power).toFixed(1) : 'Unavailable'}
                      </td>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#34d399' }}>
                        {fan != null ? fan : 'Unavailable'}
                      </td>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#a855f7' }}>
                        {ambient != null ? `${Number(ambient).toFixed(1)}` : 'Unavailable'}
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <StatusBadge
                          status={predClass.toUpperCase()}
                          label={predClass.replace(/_/g, ' ')}
                          size="sm"
                        />
                      </td>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: '#e2e8f0', fontSize: '11px' }}>
                        {conf}
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <StatusBadge
                          status={originLabel}
                          label={originLabel}
                          size="sm"
                        />
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <StatusBadge
                          status={r.is_anomaly ? 'ANOMALOUS' : 'NORMAL'}
                          size="sm"
                        />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}