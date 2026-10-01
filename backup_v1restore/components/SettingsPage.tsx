'use client'

import React, { useState } from 'react'
import { Settings, Brain, Palette, Bell, Info, ChevronRight } from 'lucide-react'
import { useJarvisStore } from '@/store/jarvisStore'

const inputCls = 'w-full bg-white/5 border border-jarvis-border rounded-lg px-3 py-2 text-xs text-jarvis-text font-mono outline-none focus:border-jarvis-accent/50 placeholder-jarvis-muted/50'

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="glass rounded-xl p-5">
      <h3 className="text-[11px] text-jarvis-accent uppercase tracking-wider font-semibold mb-4 flex items-center gap-2">
        <Icon size={13} />
        {title}
      </h3>
      <div className="space-y-4">{children}</div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <span className="text-xs text-jarvis-muted shrink-0">{label}</span>
      <div className="flex-1 max-w-xs">{children}</div>
    </div>
  )
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`relative w-9 h-5 rounded-full transition-colors ${value ? 'bg-jarvis-accent' : 'bg-white/10'}`}
    >
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${value ? 'left-4' : 'left-0.5'}`} />
    </button>
  )
}

export function SettingsPage() {
  const { connected, llmInfo } = useJarvisStore()

  const [llmSettings, setLlmSettings] = useState({
    apiKey: '',
    model: 'gpt-4o-mini',
    temperature: '0.7',
    maxTokens: '2048',
  })

  const [notifications, setNotifications] = useState({
    priceAlerts: true,
    marketOpen: true,
    systemAlerts: false,
  })

  const [appearance, setAppearance] = useState({
    accentColor: '#06b6d4',
    compactMode: false,
    animations: true,
  })

  const [stockSettings, setStockSettings] = useState({
    defaultSymbol: 'RELIANCE',
    refreshInterval: '5',
    currency: 'INR',
  })

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="max-w-2xl mx-auto space-y-4">

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <Settings size={18} className="text-jarvis-accent" />
          <h1 className="text-base font-bold text-jarvis-text uppercase tracking-wider">Settings</h1>
        </div>

        {/* LLM / AI */}
        <Section title="AI & LLM" icon={Brain}>
          <Row label="API Key">
            <input
              className={inputCls}
              type="password"
              placeholder="sk-... or leave blank for fallback"
              value={llmSettings.apiKey}
              onChange={e => setLlmSettings(s => ({ ...s, apiKey: e.target.value }))}
            />
          </Row>
          <Row label="Model">
            <select
              className={inputCls}
              value={llmSettings.model}
              onChange={e => setLlmSettings(s => ({ ...s, model: e.target.value }))}
            >
              {['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo', 'claude-3-haiku', 'gemini-pro', 'ollama-local'].map(m => (
                <option key={m} value={m} className="bg-gray-900">{m}</option>
              ))}
            </select>
          </Row>
          <Row label="Temperature">
            <input
              className={inputCls}
              type="number" min="0" max="2" step="0.1"
              value={llmSettings.temperature}
              onChange={e => setLlmSettings(s => ({ ...s, temperature: e.target.value }))}
            />
          </Row>
          <Row label="Max Tokens">
            <input
              className={inputCls}
              type="number" min="256" max="8192" step="256"
              value={llmSettings.maxTokens}
              onChange={e => setLlmSettings(s => ({ ...s, maxTokens: e.target.value }))}
            />
          </Row>
          <div className="flex items-center gap-2 pt-1">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-jarvis-neon-green' : 'bg-jarvis-neon-red'}`} />
            <span className="text-[11px] text-jarvis-muted">
              Backend: {connected ? 'connected' : 'offline'} · Provider: {llmInfo.provider}
            </span>
          </div>
        </Section>

        {/* Markets */}
        <Section title="Markets" icon={ChevronRight}>
          <Row label="Default Symbol">
            <input
              className={inputCls}
              placeholder="e.g. RELIANCE"
              value={stockSettings.defaultSymbol}
              onChange={e => setStockSettings(s => ({ ...s, defaultSymbol: e.target.value }))}
            />
          </Row>
          <Row label="WS Refresh (sec)">
            <select
              className={inputCls}
              value={stockSettings.refreshInterval}
              onChange={e => setStockSettings(s => ({ ...s, refreshInterval: e.target.value }))}
            >
              {['3', '5', '10', '15', '30'].map(v => (
                <option key={v} value={v} className="bg-gray-900">{v}s</option>
              ))}
            </select>
          </Row>
          <Row label="Currency">
            <select
              className={inputCls}
              value={stockSettings.currency}
              onChange={e => setStockSettings(s => ({ ...s, currency: e.target.value }))}
            >
              {['INR', 'USD', 'EUR'].map(c => (
                <option key={c} value={c} className="bg-gray-900">{c}</option>
              ))}
            </select>
          </Row>
        </Section>

        {/* Notifications */}
        <Section title="Notifications" icon={Bell}>
          <Row label="Price Alerts">
            <Toggle value={notifications.priceAlerts} onChange={v => setNotifications(s => ({ ...s, priceAlerts: v }))} />
          </Row>
          <Row label="Market Open/Close">
            <Toggle value={notifications.marketOpen} onChange={v => setNotifications(s => ({ ...s, marketOpen: v }))} />
          </Row>
          <Row label="System Alerts">
            <Toggle value={notifications.systemAlerts} onChange={v => setNotifications(s => ({ ...s, systemAlerts: v }))} />
          </Row>
        </Section>

        {/* Appearance */}
        <Section title="Appearance" icon={Palette}>
          <Row label="Accent Color">
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={appearance.accentColor}
                onChange={e => setAppearance(s => ({ ...s, accentColor: e.target.value }))}
                className="w-8 h-8 rounded cursor-pointer bg-transparent border-0"
              />
              <span className="text-xs font-mono text-jarvis-muted">{appearance.accentColor}</span>
            </div>
          </Row>
          <Row label="Compact Mode">
            <Toggle value={appearance.compactMode} onChange={v => setAppearance(s => ({ ...s, compactMode: v }))} />
          </Row>
          <Row label="Animations">
            <Toggle value={appearance.animations} onChange={v => setAppearance(s => ({ ...s, animations: v }))} />
          </Row>
        </Section>

        {/* About */}
        <Section title="About" icon={Info}>
          <div className="space-y-2 text-xs text-jarvis-muted font-mono">
            <div className="flex justify-between"><span>Version</span><span className="text-jarvis-text">v1.0.0-alpha</span></div>
            <div className="flex justify-between"><span>Backend</span><span className="text-jarvis-text">FastAPI · Python 3.7</span></div>
            <div className="flex justify-between"><span>Frontend</span><span className="text-jarvis-text">Next.js · TypeScript</span></div>
            <div className="flex justify-between"><span>Data Source</span><span className="text-jarvis-text">Yahoo Finance (15m delay)</span></div>
            <div className="flex justify-between"><span>Market</span><span className="text-jarvis-text">NSE · Nifty 50</span></div>
          </div>
        </Section>

      </div>
    </div>
  )
}
