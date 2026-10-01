/**
 * Small dependency-free chart components used by the Task 7 escalation-risk
 * progression and the Task 8 analytics dashboard.
 *
 * Everything is hand-rolled SVG so the project keeps its existing
 * dependency set (react + react-router-dom + axios only).
 */

// ---------------------------------------------------------------- helpers
export function clampNumber(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  return Math.min(max, Math.max(min, number));
}

function polarPoint(cx, cy, radius, angleDeg) {
  const radians = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

function arcPath(cx, cy, radius, startAngle, endAngle) {
  const start = polarPoint(cx, cy, radius, endAngle);
  const end = polarPoint(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? 0 : 1;
  return [
    `M ${start.x} ${start.y}`,
    `A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y}`,
  ].join(" ");
}

const DEFAULT_COLOR = "#2563eb";

// ------------------------------------------------------------------ Line
export function LineChart({
  data = [],
  yMax = 100,
  color = DEFAULT_COLOR,
  height = 180,
  valueSuffix = "",
  emptyLabel = "Not enough data yet.",
}) {
  const points = (data || []).filter(
    (item) => item && Number.isFinite(Number(item.value))
  );

  if (points.length === 0) {
    return <div className="t7-chart-empty">{emptyLabel}</div>;
  }

  const width = 600;
  const padding = { top: 16, right: 16, bottom: 30, left: 40 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const step = points.length > 1 ? innerWidth / (points.length - 1) : 0;

  const coords = points.map((item, index) => ({
    x: padding.left + step * index,
    y:
      padding.top +
      innerHeight -
      (clampNumber(item.value, 0, yMax) / yMax) * innerHeight,
    ...item,
  }));

  const line = coords
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");

  const area =
    `${line} L ${coords[coords.length - 1].x} ${padding.top + innerHeight}` +
    ` L ${coords[0].x} ${padding.top + innerHeight} Z`;

  const gridLines = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg
      className="t7-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      preserveAspectRatio="none"
    >
      {gridLines.map((ratio) => {
        const y = padding.top + innerHeight - ratio * innerHeight;
        return (
          <g key={ratio}>
            <line
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth="1"
            />
            <text x={padding.left - 8} y={y + 4} textAnchor="end">
              {Math.round(yMax * ratio)}
            </text>
          </g>
        );
      })}

      <path d={area} fill={color} opacity="0.12" />
      <path d={line} fill="none" stroke={color} strokeWidth="2.5" />

      {coords.map((point, index) => (
        <g key={`${point.label}-${index}`}>
          <circle cx={point.x} cy={point.y} r="4" fill={color}>
            <title>{`${point.label}: ${point.value}${valueSuffix}`}</title>
          </circle>
          <text x={point.x} y={height - 10} textAnchor="middle">
            {point.label}
          </text>
        </g>
      ))}
    </svg>
  );
}


// ------------------------------------------------------------------ Bars
export function BarChart({
  data = [],
  max = null,
  color = DEFAULT_COLOR,
  height = 200,
  valueSuffix = "",
  emptyLabel = "No data available yet.",
}) {
  const bars = (data || []).filter(
    (item) => item && Number.isFinite(Number(item.value))
  );

  if (bars.length === 0) {
    return <div className="t7-chart-empty">{emptyLabel}</div>;
  }

  const width = 600;
  const padding = { top: 18, right: 16, bottom: 34, left: 40 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const top = max || Math.max(...bars.map((item) => Number(item.value)), 1);
  const slot = innerWidth / bars.length;
  const barWidth = Math.max(10, Math.min(56, slot * 0.6));

  return (
    <svg
      className="t7-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      preserveAspectRatio="none"
    >
      {[0, 0.5, 1].map((ratio) => {
        const y = padding.top + innerHeight - ratio * innerHeight;
        return (
          <line
            key={ratio}
            x1={padding.left}
            y1={y}
            x2={width - padding.right}
            y2={y}
            stroke="#e5e7eb"
          />
        );
      })}

      {bars.map((item, index) => {
        const value = clampNumber(item.value, 0, top);
        const barHeight = (value / top) * innerHeight;
        const x =
          padding.left + slot * index + (slot - barWidth) / 2;
        const y = padding.top + innerHeight - barHeight;

        return (
          <g key={`${item.label}-${index}`}>
            <rect
              x={x}
              y={y}
              width={barWidth}
              height={Math.max(barHeight, 2)}
              rx="4"
              fill={item.color || color}
            >
              <title>{`${item.label}: ${item.value}${valueSuffix}`}</title>
            </rect>
            <text
              x={x + barWidth / 2}
              y={y - 6}
              textAnchor="middle"
              className="t7-chart-value"
            >
              {item.value}
              {valueSuffix}
            </text>
            <text
              x={x + barWidth / 2}
              y={height - 12}
              textAnchor="middle"
            >
              {item.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------- Donut
export function DonutChart({
  data = [],
  size = 200,
  thickness = 26,
  centerLabel = null,
  emptyLabel = "No data available yet.",
}) {
  const slices = (data || []).filter(
    (item) => item && Number(item.value) > 0
  );

  const total = slices.reduce((sum, item) => sum + Number(item.value), 0);

  if (total <= 0) {
    return <div className="t7-chart-empty">{emptyLabel}</div>;
  }

  const radius = size / 2 - thickness / 2 - 4;
  const cx = size / 2;
  const cy = size / 2;
  const colors = [
    "#2563eb",
    "#16a34a",
    "#f59e0b",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
  ];

  let angle = 0;

  return (
    <div className="t7-donut-wrap">
      <svg
        className="t7-donut"
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        width={size}
        height={size}
      >
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="#eef2f7"
          strokeWidth={thickness}
        />

        {slices.map((item, index) => {
          const share = Number(item.value) / total;
          const sweep = share * 360;
          const path = arcPath(
            cx,
            cy,
            radius,
            angle,
            angle + Math.min(sweep, 359.99)
          );
          angle += sweep;

          return (
            <path
              key={`${item.label}-${index}`}
              d={path}
              fill="none"
              stroke={item.color || colors[index % colors.length]}
              strokeWidth={thickness}
              strokeLinecap="butt"
            >
              <title>{`${item.label}: ${item.value} (${Math.round(
                share * 100
              )}%)`}</title>
            </path>
          );
        })}

        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          className="t7-donut-total"
        >
          {total}
        </text>
        {centerLabel && (
          <text
            x={cx}
            y={cy + 18}
            textAnchor="middle"
            className="t7-donut-caption"
          >
            {centerLabel}
          </text>
        )}
      </svg>

      <ul className="t7-donut-legend">
        {slices.map((item, index) => (
          <li key={`${item.label}-legend-${index}`}>
            <span
              className="t7-donut-swatch"
              style={{
                background: item.color || colors[index % colors.length],
              }}
            />
            <span className="t7-donut-label">{item.label}</span>
            <strong>{item.value}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

