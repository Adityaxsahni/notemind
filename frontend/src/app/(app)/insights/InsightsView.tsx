"use client";

import { useEffect, useState } from "react";

import { Alert, Card, Spinner } from "@/components/ui";
import { type Analytics, ApiError, type AuditEntry, getAnalytics, getAuditLog } from "@/lib/api";
import { useApiErrorHandler } from "@/lib/auth";

/** Admin-only. The API enforces it (403 for everyone else); this page just presents the data. */
export function InsightsView() {
  const handleError = useApiErrorHandler();
  const [stats, setStats] = useState<Analytics | null>(null);
  const [log, setLog] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getAnalytics(30), getAuditLog(50)])
      .then(([a, l]) => {
        setStats(a);
        setLog(l);
      })
      .catch((err) =>
        setError(err instanceof ApiError && err.status === 403 ? "This page is for administrators only." : handleError(err)),
      );
  }, [handleError]);

  if (error) return <Alert>{error}</Alert>;
  if (!stats || !log) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted">
        <Spinner /> Loading…
      </p>
    );
  }

  const peak = Math.max(1, ...stats.per_day.map((d) => d.views));
  return (
    <div className="space-y-6">
      <div>
        <h1 className="display text-5xl">Insights</h1>
        <p className="text-sm text-muted">Anonymous page views from visitors who accepted analytics, last {stats.days} days. Viewing this page is audited.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-sm text-muted">Page views</p>
          <p className="mt-1 text-3xl font-black">{stats.total_views}</p>
        </Card>
        {stats.devices.map((d) => (
          <Card key={d.key}>
            <p className="text-sm capitalize text-muted">{d.key}</p>
            <p className="mt-1 text-3xl font-black">{d.views}</p>
          </Card>
        ))}
      </div>
      <Card>
        <h2 className="display text-3xl">Views per day</h2>
        {stats.per_day.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No views yet.</p>
        ) : (
          <div className="mt-4 flex h-32 items-end gap-1" role="img" aria-label="Bar chart of views per day">
            {stats.per_day.map((d) => (
              <div key={d.day} title={`${d.day}: ${d.views}`} className="flex-1 rounded-t bg-accent" style={{ height: `${(d.views / peak) * 100}%` }} />
            ))}
          </div>
        )}
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="display text-3xl">Top pages</h2>
          <Table rows={stats.top_pages.map((p) => [p.key, p.views])} />
        </Card>
        <Card>
          <h2 className="display text-3xl">Referrers</h2>
          <Table rows={stats.referrers.map((r) => [r.key ?? "Direct", r.views])} />
        </Card>
      </div>
      <Card>
        <h2 className="display text-3xl">Audit log</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="py-2 pr-4">When</th>
                <th className="py-2 pr-4">Who</th>
                <th className="py-2 pr-4">Action</th>
                <th className="py-2">Target</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {log.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap py-2 pr-4 text-muted">{new Date(e.at).toLocaleString()}</td>
                  <td className="py-2 pr-4">{e.actor}</td>
                  <td className="py-2 pr-4 font-mono text-xs">{e.action}</td>
                  <td className="py-2 font-mono text-xs text-muted">{e.target ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Table({ rows }: { rows: [string, number][] }) {
  if (rows.length === 0) return <p className="mt-2 text-sm text-muted">Nothing yet.</p>;
  return (
    <ul className="mt-3 divide-y divide-border text-sm">
      {rows.map(([key, views]) => (
        <li key={key} className="flex justify-between py-2">
          <span className="truncate pr-4">{key}</span>
          <span className="font-semibold">{views}</span>
        </li>
      ))}
    </ul>
  );
}
