import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export function EChart({ option, height = 280 }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return undefined;
    const chart = echarts.init(ref.current, null, { renderer: "canvas" });
    chart.setOption(option, true);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);

  return <div className="chart-shell" ref={ref} style={{ height }} />;
}

export function buildUsageTrendOption(trends = []) {
  const timestamps = Array.from(
    new Set(
      trends.flatMap((trend) => (trend.points || []).map((point) => point.timestamp)),
    ),
  ).sort();
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { textStyle: { color: "#8ca7c2" } },
    grid: { left: 12, right: 12, top: 36, bottom: 24, containLabel: true },
    xAxis: {
      type: "category",
      data: timestamps,
      axisLabel: { color: "#8ca7c2", hideOverlap: true },
      axisLine: { lineStyle: { color: "rgba(169, 214, 255, 0.14)" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#8ca7c2" },
      splitLine: { lineStyle: { color: "rgba(169, 214, 255, 0.08)" } },
    },
    series: trends.map((trend, index) => {
      const pointMap = new Map((trend.points || []).map((point) => [point.timestamp, point.total_tokens]));
      return {
        name: trend.provider_name,
        type: "line",
        smooth: true,
        stack: "tokens",
        areaStyle: { opacity: 0.15 },
        emphasis: { focus: "series" },
        color: CHART_COLORS[index % CHART_COLORS.length],
        data: timestamps.map((timestamp) => Number(pointMap.get(timestamp) || 0)),
      };
    }),
  };
}

export function buildTimelineOption(timeline) {
  const lanes = Array.from(new Set((timeline?.events || []).map((event) => event.lane)));
  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        const event = params.data?.event || {};
        return `${event.label || params.name}<br/>${event.kind || ""}<br/>${event.timestamp || ""}`;
      },
    },
    grid: { left: 12, right: 12, top: 24, bottom: 24, containLabel: true },
    xAxis: {
      type: "time",
      axisLabel: { color: "#8ca7c2" },
      splitLine: { lineStyle: { color: "rgba(169, 214, 255, 0.08)" } },
    },
    yAxis: {
      type: "category",
      data: lanes,
      axisLabel: { color: "#8ca7c2" },
      axisLine: { lineStyle: { color: "rgba(169, 214, 255, 0.14)" } },
    },
    series: [
      {
        type: "scatter",
        symbolSize: 14,
        itemStyle: {
          color: (params) => CHART_COLORS[params.dataIndex % CHART_COLORS.length],
        },
        data: (timeline?.events || []).map((event, index) => ({
          value: [event.timestamp, event.lane],
          name: event.label,
          event,
          itemStyle: { color: CHART_COLORS[index % CHART_COLORS.length] },
        })),
      },
    ],
  };
}

export function buildAuditTrendOption(points = []) {
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    grid: { left: 12, right: 12, top: 20, bottom: 24, containLabel: true },
    xAxis: {
      type: "category",
      data: points.map((point) => point.timestamp),
      axisLabel: { color: "#8ca7c2", hideOverlap: true },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#8ca7c2" },
      splitLine: { lineStyle: { color: "rgba(169, 214, 255, 0.08)" } },
    },
    series: [
      {
        type: "bar",
        data: points.map((point) => point.count),
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: "#52d0c9",
        },
      },
    ],
  };
}

export function buildSimpleBarOption(items = [], valueKey = "score", labelKey = "title") {
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    grid: { left: 12, right: 12, top: 20, bottom: 24, containLabel: true },
    xAxis: {
      type: "category",
      data: items.map((item) => item[labelKey] || item.case_id || item.run_id || item.provider_name),
      axisLabel: { color: "#8ca7c2", interval: 0, rotate: 20 },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#8ca7c2" },
      splitLine: { lineStyle: { color: "rgba(169, 214, 255, 0.08)" } },
    },
    series: [
      {
        type: "bar",
        data: items.map((item) => Number(item[valueKey] || 0)),
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: "#ffb454",
        },
      },
    ],
  };
}

const CHART_COLORS = ["#52d0c9", "#ffb454", "#7aa2ff", "#ff7b72", "#9fefcf", "#8bcbff"];
