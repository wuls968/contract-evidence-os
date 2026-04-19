import { useEffect, useMemo, useState } from "react";

export async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload?.detail?.error || payload?.detail?.reason || payload?.error || response.statusText;
    throw new Error(message);
  }
  return payload;
}

export function useJson(url, { enabled = true, dependencies = [] } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(Boolean(enabled));

  const refreshKey = useMemo(() => JSON.stringify(dependencies), dependencies);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    requestJson(url)
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [url, enabled, refreshKey]);

  return { data, error, loading, setData };
}

export function formatCost(value) {
  return `$${Number(value || 0).toFixed(4)}`;
}

export function formatNumber(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

export async function copyText(text) {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

