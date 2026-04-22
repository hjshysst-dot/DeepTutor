"use client";

import { useEffect, useState } from "react";

interface HealthStatus {
  backend: { listening: boolean };
  frontend: { listening: boolean };
  backend_api: { success: boolean; latency_ms?: number };
  llm_api: { success: boolean; latency_ms?: number; error?: string };
  memory: { percent?: number; used_gb?: number; total_gb?: number };
  disk: { percent?: number; free_gb?: number; total_gb?: number };
  diagnosis: { status: string; issues: string[]; suggestions: string[] };
  log_errors: { errors?: string[] };
  timestamp: string;
}

export default function MonitorPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  async function fetchHealth() {
    try {
      const res = await fetch("http://localhost:3783/api/health");
      const data = await res.json();
      setHealth(data);
    } catch {
      // Monitor not reachable
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-4xl mb-4 animate-spin">🔄</div>
          <p className="text-muted-foreground">正在连接监控服务...</p>
        </div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold mb-2">监控服务未启动</h2>
          <p className="text-muted-foreground text-sm">
            请在终端运行：cd /Volumes/ORICO/DeepTutor && python3.11 scripts/monitor.py
          </p>
        </div>
      </div>
    );
  }

  const diag = health.diagnosis;
  const isHealthy = diag.status === "healthy";
  
  const mem = health.memory || { percent: 0, used_gb: 0, total_gb: 0 };
  const disk = health.disk || { percent: 0, free_gb: 0, total_gb: 0 };
  
  const memPercent = mem.percent || 0;
  const diskPercent = disk.percent || 0;

  return (
    <div className="h-full overflow-y-auto bg-background p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">🔍 DeepTutor 监控面板</h1>
            <p className="text-sm text-muted-foreground">{health.timestamp}</p>
          </div>
          <button
            onClick={fetchHealth}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
          >
            🔄 刷新
          </button>
        </div>

        {/* Status Banner */}
        <div className={`p-4 rounded-xl border ${isHealthy ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
          <h2 className={`text-lg font-bold ${isHealthy ? "text-green-600" : "text-red-600"}`}>
            {isHealthy ? "✅ 系统正常" : "⚠️ 系统异常"}
          </h2>
        </div>

        {/* Services Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Services */}
          <div className="bg-card rounded-xl p-5 border">
            <h3 className="text-sm font-medium text-muted-foreground mb-4">🔌 服务状态</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">Backend (8001)</span>
                <span className={health.backend.listening ? "text-green-500 font-medium" : "text-red-500 font-medium"}>
                  {health.backend.listening ? "✅ 运行中" : "❌ 离线"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Frontend (3782)</span>
                <span className={health.frontend.listening ? "text-green-500 font-medium" : "text-red-500 font-medium"}>
                  {health.frontend.listening ? "✅ 运行中" : "❌ 离线"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Backend API</span>
                <span className={health.backend_api.success ? "text-green-500 font-medium" : "text-red-500 font-medium"}>
                  {health.backend_api.success ? `✅ ${health.backend_api.latency_ms}ms` : "❌ 失败"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">LLM API</span>
                <span className={health.llm_api.success ? "text-green-500 font-medium" : "text-red-500 font-medium"}>
                  {health.llm_api.success ? `✅ ${health.llm_api.latency_ms}ms` : "❌ 失败"}
                </span>
              </div>
            </div>
          </div>

          {/* Resources */}
          <div className="bg-card rounded-xl p-5 border">
            <h3 className="text-sm font-medium text-muted-foreground mb-4">💾 系统资源</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>内存使用</span>
                  <span className="font-medium">{memPercent}%</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all ${memPercent > 85 ? "bg-red-500" : memPercent > 70 ? "bg-yellow-500" : "bg-green-500"}`}
                    style={{ width: `${memPercent}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {mem.used_gb}GB / {mem.total_gb}GB
                </p>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>ORICO 磁盘</span>
                  <span className="font-medium">{diskPercent}%</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all ${diskPercent > 90 ? "bg-red-500" : "bg-green-500"}`}
                    style={{ width: `${diskPercent}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  剩余 {disk.free_gb}GB
                </p>
              </div>
            </div>
          </div>

          {/* LLM Status */}
          <div className="bg-card rounded-xl p-5 border">
            <h3 className="text-sm font-medium text-muted-foreground mb-4">🤖 LLM 状态</h3>
            {health.llm_api.success ? (
              <div>
                <div className="text-2xl font-bold text-green-500">✅ 正常</div>
                <p className="text-sm text-muted-foreground mt-2">
                  模型: MiniMax-M2.7<br/>
                  响应: {health.llm_api.latency_ms}ms
                </p>
              </div>
            ) : (
              <div>
                <div className="text-2xl font-bold text-red-500">❌ 异常</div>
                <p className="text-sm text-muted-foreground mt-2 break-all">
                  {health.llm_api.error || "Unknown error"}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Diagnosis */}
        {diag.issues.length > 0 && (
          <div className="bg-card rounded-xl p-5 border">
            <h3 className="text-sm font-medium text-muted-foreground mb-4">🔧 诊断与建议</h3>
            <div className="space-y-4">
              <div>
                <h4 className="text-xs font-medium text-red-500 mb-2">问题</h4>
                <ul className="space-y-1">
                  {diag.issues.map((issue, i) => (
                    <li key={i} className="text-sm bg-red-50 px-3 py-2 rounded-lg">
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-xs font-medium text-blue-500 mb-2">建议修复</h4>
                <ul className="space-y-1">
                  {diag.suggestions.map((s, i) => (
                    <li key={i} className="text-sm bg-blue-50 px-3 py-2 rounded-lg font-mono">
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Log Errors */}
        {health.log_errors.errors && health.log_errors.errors.length > 0 && (
          <div className="bg-card rounded-xl p-5 border">
            <h3 className="text-sm font-medium text-muted-foreground mb-4">📋 最近错误日志</h3>
            <div className="space-y-2">
              {health.log_errors.errors.slice(0, 3).map((err, i) => (
                <div key={i} className="text-xs bg-red-50 text-red-600 px-3 py-2 rounded font-mono overflow-hidden">
                  {err}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
