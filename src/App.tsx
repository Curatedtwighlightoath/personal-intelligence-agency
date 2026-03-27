/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  ShieldAlert, 
  FlaskConical, 
  Megaphone, 
  Settings, 
  Search, 
  Bell, 
  User, 
  LogOut, 
  Activity, 
  Lock, 
  Cpu, 
  Globe, 
  Zap,
  ChevronRight,
  Plus,
  History,
  AlertTriangle,
  CheckCircle2,
  Fingerprint,
  ShieldCheck,
  RefreshCw,
  ArrowRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// --- Types ---

type View = 'dashboard' | 'watchdog' | 'rnd' | 'marketing' | 'settings' | 'login' | 'error';

// --- Components ---

const Sidebar = ({ currentView, setView }: { currentView: View, setView: (v: View) => void }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'watchdog', label: 'Watchdog', icon: ShieldAlert },
    { id: 'rnd', label: 'R&D', icon: FlaskConical },
    { id: 'marketing', label: 'Marketing', icon: Megaphone },
  ] as const;

  return (
    <aside className="fixed left-0 top-0 h-full w-64 z-40 bg-surface-container-low flex flex-col border-r border-outline-variant/10">
      <div className="p-6 flex flex-col gap-1">
        <span className="text-xl font-black tracking-tighter text-primary font-headline">INTEL_CORE</span>
        <span className="font-headline uppercase tracking-widest text-[10px] text-outline">OPERATIONAL_UNIT_01</span>
      </div>
      
      <div className="bg-surface-container-lowest h-[1px] w-full mb-4"></div>
      
      <nav className="flex-1 flex flex-col">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setView(item.id)}
            className={`flex items-center gap-4 px-6 py-4 font-headline uppercase tracking-widest text-xs transition-all duration-200 ${
              currentView === item.id 
                ? 'text-secondary border-l-2 border-secondary bg-surface-container' 
                : 'text-outline hover:text-neutral-200 hover:bg-surface-bright'
            }`}
          >
            <item.icon size={18} />
            <span>{item.label}</span>
          </button>
        ))}
        
        <div className="mt-auto">
          <button
            onClick={() => setView('settings')}
            className={`flex items-center gap-4 px-6 py-4 w-full font-headline uppercase tracking-widest text-xs transition-all duration-200 ${
              currentView === 'settings' 
                ? 'text-secondary border-l-2 border-secondary bg-surface-container' 
                : 'text-outline hover:text-neutral-200 hover:bg-surface-bright'
            }`}
          >
            <Settings size={18} />
            <span>Settings</span>
          </button>
        </div>
      </nav>
      
      <div className="p-6 mt-auto">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 border border-outline-variant/30 overflow-hidden bg-surface-container flex items-center justify-center">
            <User size={24} className="text-outline" />
          </div>
          <div className="flex flex-col">
            <span className="font-headline text-[10px] uppercase tracking-tighter text-on-surface">Agent_09</span>
            <span className="font-headline text-[9px] uppercase tracking-tighter text-secondary">Authorized</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

const Header = ({ title }: { title: string }) => {
  return (
    <header className="fixed top-0 right-0 left-64 h-16 flex justify-between items-center px-8 z-50 bg-surface-dim/60 backdrop-blur-md border-b border-outline-variant/10">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-black text-white tracking-widest uppercase font-headline">TACTICAL_MONOLITH_OS</h1>
        <div className="h-4 w-[1px] bg-outline-variant/30"></div>
        <span className="font-headline text-[10px] text-primary tracking-widest">{title}</span>
      </div>
      
      <div className="flex items-center gap-6">
        <div className="relative group">
          <input 
            className="bg-surface-container-highest/50 border-0 border-b border-outline-variant/50 focus:border-secondary focus:ring-0 text-[10px] font-headline tracking-widest w-64 px-4 py-1.5 transition-all duration-300 outline-none" 
            placeholder="ENCRYPTED_SEARCH..." 
            type="text"
          />
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-outline" size={14} />
        </div>
        
        <div className="flex gap-4">
          <button className="text-outline hover:text-secondary transition-colors relative">
            <Bell size={20} />
            <span className="absolute top-0 right-0 w-1.5 h-1.5 bg-secondary"></span>
          </button>
          <button className="text-outline hover:text-secondary transition-colors">
            <User size={20} />
          </button>
        </div>
      </div>
    </header>
  );
};

// --- Views ---

const DashboardView = () => {
  return (
    <div className="space-y-8">
      {/* Telemetry Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-1">
        {[
          { label: 'Network_Latency', value: '12.4', unit: 'MS', progress: 25, color: 'secondary' },
          { label: 'Active_Encryptions', value: '1,024', unit: 'AES', progress: 75, color: 'secondary' },
          { label: 'Threat_Alerts', value: '02', unit: 'CRIT', progress: 10, color: 'error', pulse: true },
          { label: 'Uptime_Sequence', value: '99.99', unit: '%', progress: 99, color: 'secondary' },
        ].map((item, i) => (
          <div key={i} className="bg-surface-container-low p-6 flex flex-col gap-2 relative group overflow-hidden">
            <div className="scanline opacity-20"></div>
            <span className="font-headline text-[10px] uppercase tracking-widest text-outline">{item.label}</span>
            <div className="flex items-end gap-2">
              <span className={`text-3xl font-bold font-headline ${item.color === 'error' ? 'text-error' : 'text-white'}`}>{item.value}</span>
              <span className="text-primary font-headline text-xs mb-1">{item.unit}</span>
            </div>
            <div className="w-full h-1 bg-surface-container-highest mt-2">
              <div 
                className={`h-full ${item.color === 'error' ? 'bg-error' : 'bg-secondary'} ${item.pulse ? 'animate-pulse' : ''}`} 
                style={{ width: `${item.progress}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-1 h-[600px]">
        <div className="col-span-12 lg:col-span-8 bg-surface-container-low p-1 overflow-hidden relative group">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none"></div>
          <div className="h-full w-full bg-surface p-6 flex flex-col">
            <div className="flex justify-between items-start mb-8">
              <div>
                <h2 className="font-headline text-xl font-bold text-white tracking-tight uppercase">Central_Protocol_Monitor</h2>
                <p className="font-headline text-[10px] text-outline tracking-widest uppercase">Live data feed visualization</p>
              </div>
              <div className="flex items-center gap-2 px-3 py-1 bg-secondary/10 border border-secondary/20">
                <span className="w-2 h-2 bg-secondary rounded-full animate-ping"></span>
                <span className="font-headline text-[10px] text-secondary tracking-widest uppercase font-bold">SYSTEM_LIVE</span>
              </div>
            </div>
            
            <div className="flex-1 border border-outline-variant/10 relative overflow-hidden flex items-center justify-center bg-surface-container-lowest">
              <div className="absolute inset-0 opacity-10 blueprint-grid"></div>
              <img 
                alt="Central Telemetry Map" 
                className="w-full h-full object-cover mix-blend-screen opacity-60" 
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDvot__ZY2-CdeycdGrMRy0rVM-GhcZ3qkqQdmnTIkXh3iyClSR98K9UMn1XRUURNhvc3EppX_R-OldJjhygz7wC_F-kda2f4ViUtmsQ3tXxOEksqO9C4hNtUNU3SmdJyGT2Ze4hfTmACH3-EQHyoTA0y_3Vt9wtLkVB_3J788D0-E-AIajqrcTL-YQ_JKZRWYUI17PVO26kHDB5lhGbhFHhNYIVnakE5mbCTxMtkLCaswYjBQO6p9XipyvY7mcjcSek3-r9Hwx5kA"
                referrerPolicy="no-referrer"
              />
              <div className="absolute top-10 left-10 p-2 border border-secondary bg-surface-dim/80 backdrop-blur-sm">
                <span className="font-headline text-[9px] text-secondary tracking-tighter">NODE_01: STABLE</span>
              </div>
              <div className="absolute bottom-20 right-40 p-2 border border-primary bg-surface-dim/80 backdrop-blur-sm">
                <span className="font-headline text-[9px] text-primary tracking-tighter">DATA_SYNC: 84%</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-1 mt-1">
              <button className="bg-surface-container-high p-4 text-[10px] font-headline uppercase tracking-widest text-outline hover:text-white hover:bg-surface-bright transition-all">Relay_Scan</button>
              <button className="bg-surface-container-high p-4 text-[10px] font-headline uppercase tracking-widest text-outline hover:text-white hover:bg-surface-bright transition-all">Node_Refresh</button>
              <button className="bg-secondary p-4 text-[10px] font-headline uppercase tracking-widest text-on-secondary font-bold transition-all">Init_Deep_Sync</button>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 bg-surface-container-low flex flex-col">
          <div className="p-6 border-b border-surface-container">
            <h2 className="font-headline text-sm font-bold text-white tracking-widest uppercase">Activity_Log</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-0 custom-scrollbar">
            {[
              { time: '14:22:01', tag: 'Watchdog_Relay', text: 'External packet handshake established. SSL verification complete.', color: 'secondary' },
              { time: '14:19:44', tag: 'R&D_Internal', text: 'Module_V3.5 compiled. 14 warnings suppressed.', color: 'primary' },
              { time: '14:15:10', tag: 'Security_Alert', text: 'Unauthorized access attempt detected from IP: 192.168.1.104. Firewall blocking active.', color: 'error' },
              { time: '13:58:30', tag: 'Marketing_Core', text: 'Campaign data batch processed. Sentiment analysis: Positive (0.88).', color: 'secondary' },
            ].map((log, i) => (
              <div key={i} className={`p-4 border-b border-outline-variant/5 flex gap-4 items-start ${log.color === 'error' ? 'bg-error/5' : 'bg-surface-container-lowest/30'}`}>
                <span className="font-headline text-[9px] text-primary whitespace-nowrap pt-0.5">{log.time}</span>
                <div className="flex flex-col gap-1">
                  <span className={`font-headline text-[10px] uppercase tracking-tighter text-${log.color}`}>{log.tag}</span>
                  <p className="text-[11px] text-outline font-body leading-relaxed">{log.text}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="p-4 bg-surface-container-highest">
            <button className="w-full text-center font-headline text-[9px] text-outline tracking-[0.2em] uppercase hover:text-white transition-colors">Export_Full_Log</button>
          </div>
        </div>
      </div>

      {/* Server Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-1">
        {[
          { name: 'Watchdog_SVR', status: 'OPERATIONAL', cpu: 12, mem: '4.2 / 16 GB', memP: 26, color: 'secondary', icon: ShieldAlert },
          { name: 'R&D_SVR', status: 'PROCESSING', cpu: 88, mem: '14.1 / 32 GB', memP: 44, color: 'primary', icon: FlaskConical },
          { name: 'Marketing_SVR', status: 'IDLE', cpu: 2, mem: '1.1 / 8 GB', memP: 14, color: 'outline', icon: Megaphone },
        ].map((svr, i) => (
          <div key={i} className={`bg-surface-container-low p-6 space-y-4 border-l-2 border-${svr.color}/50`}>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <svr.icon size={18} className={`text-${svr.color}`} />
                <h3 className="font-headline text-xs font-bold uppercase tracking-widest text-white">{svr.name}</h3>
              </div>
              <span className={`font-headline text-[9px] text-${svr.color} uppercase tracking-tighter font-bold`}>{svr.status}</span>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between text-[10px] font-headline">
                <span className="text-outline uppercase">CPU_LOAD</span>
                <span className="text-white">{svr.cpu}%</span>
              </div>
              <div className="w-full h-1 bg-surface-container-highest">
                <div className={`h-full bg-${svr.color}`} style={{ width: `${svr.cpu}%` }}></div>
              </div>
              <div className="flex justify-between text-[10px] font-headline">
                <span className="text-outline uppercase">MEM_USAGE</span>
                <span className="text-white">{svr.mem}</span>
              </div>
              <div className="w-full h-1 bg-surface-container-highest">
                <div className={`h-full bg-${svr.color}`} style={{ width: `${svr.memP}%` }}></div>
              </div>
            </div>
            <div className="pt-2 flex justify-end">
              <button className="text-[9px] font-headline uppercase tracking-widest text-primary border border-primary/20 px-3 py-1 hover:bg-primary/10 transition-colors">Diagnostics</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const WatchdogView = () => {
  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row justify-between items-end gap-4 mb-8">
        <div>
          <h3 className="font-headline text-3xl font-bold tracking-tighter uppercase text-white">Watchdog Department</h3>
          <p className="font-headline text-xs text-outline tracking-widest mt-1 uppercase">Surveillance Cluster // RSS_PROTOCOL_V4.2</p>
        </div>
        <div className="flex gap-2">
          <button className="px-4 py-2 bg-surface-container-highest border border-outline-variant/20 font-headline text-[10px] tracking-widest uppercase hover:bg-surface-bright transition-all flex items-center gap-2">
            <Plus size={14} />
            Register New Feed
          </button>
          <button className="px-4 py-2 bg-primary text-on-primary-fixed font-headline text-[10px] tracking-widest uppercase font-bold hover:brightness-110 transition-all flex items-center gap-2">
            <RefreshCw size={14} />
            Manual Sync
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-1 bg-background border border-outline-variant/10">
        <section className="col-span-12 lg:col-span-8 bg-surface-container-low p-6">
          <div className="flex justify-between items-center mb-6">
            <h4 className="font-headline text-xs font-bold tracking-[0.2em] uppercase text-primary flex items-center gap-2">
              <Activity size={14} />
              Active Surveillance Feeds
            </h4>
            <span className="font-mono text-[10px] text-outline">ACTIVE_NODES: 12</span>
          </div>
          <div className="space-y-1">
            {[
              { name: 'CRYPTO_EXCHANGE_LEAKS', url: 'rss.intel/node/ex-leaks', threshold: '85 / 70', color: 'error', icon: AlertTriangle, alert: true },
              { name: 'GLOBAL_SECURITY_BLOG', url: 'feed.monolith.net/sec-pulse', threshold: '12 / 80', color: 'secondary', icon: Globe },
              { name: 'DEEPWEB_FORUM_SCRAPER', url: 'onion.intel/ingress/v4', threshold: '45 / 90', color: 'primary', icon: Globe },
              { name: 'OFFLINE_ARCHIVE_NODE', url: 'backup.intel/node/arc-01', status: 'DORMANT', color: 'outline', icon: Zap, dormant: true },
            ].map((feed, i) => (
              <div key={i} className={`group relative bg-surface-container p-4 flex items-center justify-between border-l-2 border-${feed.color}`}>
                {feed.alert && <div className="absolute inset-0 bg-error/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>}
                <div className="flex items-center gap-4 relative z-10">
                  <div className={`w-10 h-10 ${feed.alert ? 'bg-error/20' : 'bg-surface-container-highest'} flex items-center justify-center`}>
                    <feed.icon size={18} className={`text-${feed.color} ${feed.alert ? 'animate-pulse' : ''}`} />
                  </div>
                  <div>
                    <h5 className="font-headline text-sm font-bold text-white uppercase tracking-tight">{feed.name}</h5>
                    <p className="font-mono text-[10px] text-outline mt-0.5">{feed.url}</p>
                  </div>
                </div>
                <div className="flex items-center gap-8 relative z-10">
                  <div className="text-right">
                    <p className="font-headline text-[10px] text-outline uppercase">{feed.threshold ? 'Threshold' : 'Status'}</p>
                    <p className={`font-mono ${feed.threshold ? 'text-sm font-bold' : 'text-xs'} text-${feed.color}`}>
                      {feed.threshold || feed.status}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button className="w-8 h-8 bg-surface-bright flex items-center justify-center hover:bg-primary transition-colors">
                      <Settings size={14} />
                    </button>
                    <button className="w-8 h-8 bg-surface-bright flex items-center justify-center hover:bg-neutral-600 transition-colors">
                      <RefreshCw size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="col-span-12 lg:col-span-4 bg-surface-container p-6 border-l border-outline-variant/10">
          <div className="flex justify-between items-center mb-6">
            <h4 className="font-headline text-xs font-bold tracking-[0.2em] uppercase text-secondary flex items-center gap-2">
              <Activity size={14} />
              Live Ingress Feed
            </h4>
            <div className="flex gap-1">
              <div className="w-1 h-1 bg-secondary animate-pulse"></div>
              <div className="w-1 h-1 bg-secondary/50"></div>
              <div className="w-1 h-1 bg-secondary/20"></div>
            </div>
          </div>
          <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
            {[
              { id: '#INTEL_7721', time: '02:14:45 UTC', title: 'Unusual movement in classified cloud storage...', text: 'Telemetry detected a 400% increase in egress traffic from European data nodes located in Frankfurt cluster. Origin unknown.', source: 'TechLeaks', score: '92.4', high: true },
              { id: '#INTEL_7720', time: '02:12:10 UTC', title: 'New advisory published: CVE-2024-9981', text: 'Critical vulnerability in kernel level drivers affects all 9th gen processing units. Patch status: NOT_AVAILABLE.', source: 'SecPortal', score: '14.8' },
              { id: '#INTEL_7719', time: '02:08:33 UTC', title: 'Deep Web Forum discussion spike', text: 'Topic "The Monolith" mentioned 45 times in last 10 minutes on /v/intel board. Monitoring for entity identification.', source: 'OnionScraper', score: '55.2' },
            ].map((item, i) => (
              <article key={i} className="p-3 bg-surface-container-low border border-outline-variant/10 relative overflow-hidden">
                {item.high && <div className="absolute top-0 right-0 p-1 bg-error text-on-error font-headline text-[8px] px-2 font-bold uppercase tracking-widest">High Score</div>}
                <div className="flex justify-between items-start mb-2">
                  <span className="font-mono text-[9px] text-primary">{item.id}</span>
                  <span className="font-mono text-[9px] text-outline">{item.time}</span>
                </div>
                <h6 className="font-headline text-xs font-bold text-white uppercase tracking-tight mb-1">{item.title}</h6>
                <p className="text-[10px] text-outline leading-relaxed mb-2 line-clamp-2">{item.text}</p>
                <div className="flex justify-between items-center pt-2 border-t border-outline-variant/10">
                  <span className="font-headline text-[9px] text-secondary tracking-widest uppercase">Source: {item.source}</span>
                  <span className={`font-mono text-xs font-bold ${item.high ? 'text-error' : 'text-secondary'}`}>SCORE: {item.score}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};

const RnDView = () => {
  return (
    <div className="space-y-8">
      <section className="mb-10">
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="font-headline text-4xl font-black text-white tracking-tighter uppercase">Operational_Sectors</h2>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-secondary rounded-full"></div>
            <span className="font-headline text-[10px] text-secondary tracking-widest uppercase">Systems_Live</span>
          </div>
        </div>
        <div className="h-[1px] w-full bg-gradient-to-r from-primary/50 to-transparent"></div>
      </section>

      <div className="grid grid-cols-12 gap-1 auto-rows-[220px]">
        <div className="col-span-12 lg:col-span-8 bg-surface-container-low p-6 flex flex-col justify-between group border-l-2 border-primary">
          <div>
            <div className="flex justify-between items-start">
              <div>
                <span className="font-headline text-[10px] text-primary uppercase tracking-[0.2em] mb-2 block">Division: Research_Development</span>
                <h3 className="font-headline text-2xl font-bold text-white mb-2">PROJECT ALPHA: NEURAL_RECON</h3>
              </div>
              <span className="font-headline text-xs text-secondary border border-secondary/20 px-2 py-1 bg-secondary/5">STATUS: OPTIMIZING</span>
            </div>
            <p className="text-outline text-sm max-w-xl font-body mt-4 leading-relaxed">
              Synthesizing autonomous reconnaissance protocols for low-latency feedback loops. Initial phase testing successfully bypassed legacy firewall structures in isolated simulation environments.
            </p>
          </div>
          <div className="mt-6">
            <div className="flex justify-between items-end mb-2">
              <span className="font-headline text-[10px] text-primary uppercase">Synchronization_Progress</span>
              <span className="font-headline text-xs text-white">74.82%</span>
            </div>
            <div className="h-1 w-full bg-surface-container-highest">
              <div className="h-full bg-primary w-[74.82%] shadow-[0_0_8px_rgba(133,173,255,0.6)]"></div>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 bg-surface-container p-6 flex flex-col justify-center">
          <div className="space-y-4">
            {[
              { label: 'Core_Temp', value: '32.4°C' },
              { label: 'Neural_Load', value: 'MODERATE', color: 'text-secondary' },
              { label: 'Packet_Loss', value: '0.0001%' },
              { label: 'Uptime', value: '412:12:05' },
            ].map((stat, i) => (
              <div key={i} className="flex items-center justify-between border-b border-outline-variant/10 pb-2">
                <span className="font-headline text-[10px] text-neutral-400 uppercase">{stat.label}</span>
                <span className={`font-headline text-xs ${stat.color || 'text-white'}`}>{stat.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5 bg-surface-container-low p-6 flex flex-col justify-between border-l-2 border-secondary">
          <div>
            <span className="font-headline text-[10px] text-secondary uppercase tracking-[0.2em] mb-2 block">Division: Strategic_Growth</span>
            <h3 className="font-headline text-2xl font-bold text-white mb-2">CAMPAIGN BETA: SILENT_PULSE</h3>
            <div className="mt-4 aspect-video w-full bg-surface-container-highest relative overflow-hidden group">
              <img 
                alt="Cyberpunk interface" 
                className="w-full h-full object-cover opacity-40 group-hover:scale-105 transition-transform duration-700" 
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCrMUXKRWgUfJ--uEg8qA8Xh6NPxDcz7TrIrz3U7AfNibvI3sOClGIwv_Y7qaF3xHIprz8_myCODZ3_RZu8y9mSNUZdwTo3S97Eu8urr-6ONAb4cEcW3jQBWqpAkE1ikKt-NgDyWyU5JYH16C0C7VKdCgL48LP5nL-Lx3V13LAjOoP9wz-cYSUChmzsynPNIa_1XB4dAcFABLYmv_SMDmnfhL_4GGWvaM0bfHzxZJlFfAk27GIz4cWLU-iiMUXtRt-e6BTLDEPYPGk"
                referrerPolicy="no-referrer"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface-container-low to-transparent"></div>
              <div className="absolute bottom-4 left-4">
                <span className="font-headline text-[10px] text-white bg-black/50 px-2 py-1 backdrop-blur-sm">ASSET_MKTG_001.JPG</span>
              </div>
            </div>
          </div>
          <div className="flex justify-between items-center mt-4">
            <span className="font-headline text-[10px] text-neutral-500 uppercase">Reach_Target</span>
            <span className="font-headline text-sm text-secondary font-bold">1.2M_NODES</span>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7 bg-surface-container p-6 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-headline text-xs font-bold text-white uppercase tracking-widest">Active_Development_Logs</h4>
            <History size={14} className="text-primary" />
          </div>
          <div className="flex-1 space-y-3 font-mono text-[11px] overflow-y-auto pr-2 custom-scrollbar">
            {[
              { time: '14:22:09', text: 'NEURAL_RECON: Integration with Module_C successful. Encryption key rotated.', color: 'text-primary' },
              { time: '13:05:44', text: 'CAMPAIGN_BETA: Asset 001-004 deployed to secure relays. Awaiting initial traffic telemetry.', color: 'text-primary' },
              { time: '11:58:12', text: 'SYSTEM: Background optimization routine completed. No anomalies detected.', color: 'text-primary' },
              { time: '09:30:00', text: 'R&D_CORE: Prototype MCP "Wraith" initiated standby sequence.', color: 'text-primary' },
              { time: '08:15:33', text: 'ALERT: Minor latency spike detected in Sector 4. Resolution auto-applied.', color: 'text-error' },
            ].map((log, i) => (
              <div key={i} className="flex gap-4">
                <span className={`${log.color} shrink-0`}>[{log.time}]</span>
                <span className="text-outline">{log.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const MarketingView = () => {
  return (
    <div className="space-y-8">
      <section className="relative z-20 py-12">
        <div className="flex flex-col md:flex-row gap-12 items-start">
          <div className="w-full md:w-3/5">
            <div className="bg-tertiary inline-block px-4 py-1 mb-6">
              <span className="text-on-tertiary-fixed font-black text-xs tracking-[0.4em] uppercase">Tactical_Outreach_Unit</span>
            </div>
            <h1 className="text-5xl md:text-8xl font-black uppercase leading-[0.85] tracking-tighter text-tertiary mb-8">
              AGGRESSIVE<br/>INFLUENCE<br/>ENGINE.
            </h1>
            <p className="text-outline max-w-lg text-lg mb-10 leading-relaxed">
              Deploying hyper-targeted narrative payloads across distributed node networks. The Silent Pulse protocol is now active.
            </p>
            <div className="flex flex-wrap gap-4">
              <button className="bg-tertiary text-on-tertiary-fixed font-black px-12 py-6 text-xl tracking-tighter uppercase hover:bg-tertiary-dim active:translate-y-1">
                Deploy_Campaign
              </button>
              <button className="border-2 border-outline-variant text-on-surface font-bold px-10 py-6 text-xl tracking-tighter uppercase hover:bg-surface-bright active:translate-y-1">
                Operational_Specs
              </button>
            </div>
          </div>
          <div className="w-full md:w-2/5 relative">
            <div className="aspect-square bg-surface-container-high relative overflow-hidden">
              <img 
                className="w-full h-full object-cover mix-blend-overlay opacity-80" 
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuBmDqOSoqP3tJaacD89WnGRdldBFt6F9Yu7tZNcquCWEVIXsfnHSNUQOFYUzbCXNwxeVyA5zJpUuvJx2pIkpQACdlmIynBVKy0r8hG2vp-NpncEra1UKDWFPC0U8GJRDeDVlnx4SlAn4xRCkvs_cFIRx5TTmnuJoDlPRuVubXLyII1MGs1ISr6T4PI_11smZzzQ0OIwKzPAron4om09paR62snd-vR-RMzeoG3jJm4M8w_4tcPKGhJg8QyRVrLaIViJtKClr7qHGC4"
                referrerPolicy="no-referrer"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-surface via-transparent to-transparent"></div>
              <div className="absolute bottom-6 left-6 right-6">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2 h-2 bg-error rounded-full animate-pulse"></span>
                  <span className="text-[10px] font-bold tracking-widest text-error">LIVE_INFILTRATION_FEED</span>
                </div>
                <div className="text-xs font-mono text-tertiary opacity-70">NODE_LATENCY: 12ms // VECTOR: SEC_04</div>
              </div>
            </div>
            <div className="absolute -bottom-8 -right-8 w-48 h-48 bg-error/10 backdrop-blur-md border border-error/30 p-4 flex flex-col justify-end">
              <div className="text-3xl font-black text-error">94.2%</div>
              <div className="text-[10px] font-bold tracking-widest text-outline uppercase">Saturation_Index</div>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="md:col-span-2 bg-surface-container p-8 flex flex-col justify-between group hover:bg-surface-bright transition-all cursor-pointer border-l-4 border-tertiary">
          <div>
            <div className="flex justify-between items-start mb-12">
              <Zap size={32} className="text-tertiary" />
              <span className="text-[10px] font-bold tracking-[0.3em] text-outline uppercase">Active_Session</span>
            </div>
            <h3 className="text-4xl font-black text-on-surface mb-2 uppercase tracking-tighter">Silent_Pulse</h3>
            <p className="text-outline text-sm font-medium">Global sentiment manipulation via low-frequency digital echoes.</p>
          </div>
          <div className="mt-12 space-y-4">
            <div className="h-[2px] w-full bg-outline-variant">
              <div className="h-full bg-tertiary w-3/4 shadow-[0_0_10px_#abfc00]"></div>
            </div>
            <div className="flex justify-between text-[10px] font-bold tracking-widest uppercase">
              <span className="text-tertiary">Propagation_Complete</span>
              <span className="text-outline">75% / 100%</span>
            </div>
          </div>
        </div>

        <div className="bg-surface-container p-8 border-t-4 border-secondary">
          <div className="flex justify-between items-start mb-8">
            <Globe size={24} className="text-secondary" />
            <div className="px-2 py-0.5 bg-secondary/10 border border-secondary/30 text-secondary text-[8px] font-black uppercase">Encrypted</div>
          </div>
          <h4 className="text-2xl font-black text-on-surface uppercase tracking-tighter mb-4">Influence_Hub</h4>
          <div className="space-y-3">
            {[
              { label: 'TIER_1_NODES', value: '1,242' },
              { label: 'REACH_ESTIMATE', value: '14.2M' },
              { label: 'CONVERSION_RT', value: '8.4%', color: 'text-tertiary' },
            ].map((item, i) => (
              <div key={i} className="flex justify-between text-[10px] text-outline">
                <span>{item.label}</span>
                <span className={`${item.color || 'text-on-surface'} font-bold`}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-error p-8 flex flex-col justify-between cursor-crosshair group relative overflow-hidden">
          <div className="absolute inset-0 opacity-10 bg-[repeating-linear-gradient(45deg,transparent,transparent_20px,white_20px,white_40px)]"></div>
          <h4 className="text-2xl font-black text-on-error uppercase tracking-tighter relative z-10 leading-none">Emergency_Broadcast_Protocol</h4>
          <div className="relative z-10">
            <ArrowRight size={48} className="text-on-error group-hover:translate-x-4 transition-transform" />
          </div>
        </div>
      </div>
    </div>
  );
};

const LoginView = ({ onLogin }: { onLogin: () => void }) => {
  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <header className="w-full flex justify-between items-center px-8 py-6 z-50">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-primary flex items-center justify-center">
            <ShieldCheck size={24} className="text-on-primary-container" />
          </div>
          <span className="font-headline font-bold text-xl tracking-tighter text-primary">OBSIDIAN_PROTOCOL</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-secondary rounded-full animate-pulse"></div>
            <span className="font-headline text-xs tracking-widest text-secondary uppercase">Secure_Link_Established</span>
          </div>
        </div>
      </header>

      <main className="flex-grow flex items-center justify-center relative px-4 py-12">
        <div className="absolute inset-0 scanline pointer-events-none opacity-20"></div>
        <div className="w-full max-w-lg relative group">
          <div className="absolute -top-1 -left-1 w-6 h-6 border-t-2 border-l-2 border-primary/40"></div>
          <div className="absolute -top-1 -right-1 w-6 h-6 border-t-2 border-r-2 border-primary/40"></div>
          <div className="absolute -bottom-1 -left-1 w-6 h-6 border-b-2 border-l-2 border-primary/40"></div>
          <div className="absolute -bottom-1 -right-1 w-6 h-6 border-b-2 border-r-2 border-primary/40"></div>
          
          <section className="bg-surface-container-low relative overflow-hidden border border-white/5 shadow-[0_0_40px_rgba(0,112,235,0.08)]">
            <div className="p-8 md:p-12">
              <div className="mb-10">
                <h1 className="font-headline text-2xl font-bold tracking-[0.1em] text-on-surface mb-2 uppercase">Requesting Clearance</h1>
                <p className="font-headline text-xs text-outline-variant tracking-widest uppercase">System: Node_Alpha // Access_Vector: Manual_Entry</p>
              </div>
              
              <div className="space-y-8">
                <div className="space-y-2 group">
                  <label className="font-headline text-xs font-bold tracking-[0.15em] text-primary uppercase block">Operator ID</label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 text-outline" size={16} />
                    <input 
                      className="w-full bg-surface-container-highest border-0 border-b border-outline-variant py-4 pl-12 pr-4 text-on-surface placeholder:text-outline-variant/50 focus:ring-0 focus:border-secondary transition-all font-body text-sm outline-none" 
                      placeholder="AGENT_ID_0000" 
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="font-headline text-xs font-bold tracking-[0.15em] text-primary uppercase block">Neural Hash</label>
                  <div className="relative">
                    <Fingerprint className="absolute left-4 top-1/2 -translate-y-1/2 text-outline" size={16} />
                    <input 
                      className="w-full bg-surface-container-highest border-0 border-b border-outline-variant py-4 pl-12 pr-4 text-on-surface placeholder:text-outline-variant/50 focus:ring-0 focus:border-secondary transition-all font-body text-sm outline-none" 
                      type="password" 
                      placeholder="••••••••••••••••" 
                    />
                  </div>
                </div>

                <div className="pt-4">
                  <button 
                    onClick={onLogin}
                    className="w-full bg-primary hover:bg-primary-dim text-on-primary-fixed py-5 font-headline font-bold text-sm tracking-[0.2em] transition-all hover:scale-[0.99] active:scale-95 uppercase flex items-center justify-center gap-3"
                  >
                    INITIALIZE_OPERATOR_SYNC
                    <RefreshCw size={16} />
                  </button>
                  <p className="mt-6 text-center font-headline text-[10px] text-outline-variant tracking-widest uppercase">
                    Already identified? <span className="text-primary hover:underline cursor-pointer">Bypass_Registration</span>
                  </p>
                </div>
              </div>
            </div>
            <div className="h-1 w-full bg-gradient-to-r from-primary-dim via-secondary to-primary-dim opacity-40"></div>
          </section>
        </div>
      </main>
    </div>
  );
};

const Error404View = ({ onBack }: { onBack: () => void }) => {
  return (
    <div className="flex flex-col items-center justify-center h-[70vh] space-y-8">
      <div className="relative">
        <div className="text-[12rem] font-black font-headline text-surface-container-highest tracking-tighter leading-none">404</div>
        <div className="absolute inset-0 flex items-center justify-center">
          <AlertTriangle size={80} className="text-error animate-pulse" />
        </div>
      </div>
      <div className="text-center space-y-2">
        <h2 className="text-3xl font-black font-headline uppercase tracking-widest text-white">Target_Node_Not_Found</h2>
        <p className="text-outline font-headline text-xs tracking-[0.3em] uppercase">The requested coordinate does not exist in the current reality.</p>
      </div>
      <button 
        onClick={onBack}
        className="px-8 py-4 bg-primary text-on-primary-fixed font-headline font-bold text-xs tracking-widest uppercase hover:bg-primary-dim transition-all flex items-center gap-3"
      >
        <ArrowRight size={16} className="rotate-180" />
        Return_To_Safe_Zone
      </button>
    </div>
  );
};

// --- Main App ---

export default function App() {
  const [view, setView] = useState<View>('login');
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  const handleLogin = () => {
    setIsLoggedIn(true);
    setView('dashboard');
  };

  if (!isLoggedIn) {
    return <LoginView onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidebar currentView={view} setView={setView} />
      <Header title={view.toUpperCase()} />
      
      <main className="ml-64 pt-16 min-h-screen">
        <div className="p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={view}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {view === 'dashboard' && <DashboardView />}
              {view === 'watchdog' && <WatchdogView />}
              {view === 'rnd' && <RnDView />}
              {view === 'marketing' && <MarketingView />}
              {view === 'error' && <Error404View onBack={() => setView('dashboard')} />}
              {view === 'settings' && (
                <div className="flex items-center justify-center h-[60vh]">
                  <div className="text-center space-y-4">
                    <Settings size={64} className="mx-auto text-outline animate-spin-slow" />
                    <h2 className="text-2xl font-headline font-bold uppercase tracking-widest">Settings_Module_Offline</h2>
                    <p className="text-outline">Access to system configuration is restricted to Level 10 clearance.</p>
                    <button 
                      onClick={() => setView('error')}
                      className="text-error font-headline text-[10px] uppercase tracking-widest hover:underline"
                    >
                      Force_Access_Attempt
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Floating System Warning */}
      <div className="fixed bottom-8 right-8 z-50">
        <button className="group relative flex items-center justify-center w-14 h-14 bg-error text-on-error shadow-[0px_0px_20px_rgba(255,113,108,0.4)] transition-all active:scale-95">
          <AlertTriangle size={24} />
          <div className="absolute right-full mr-4 opacity-0 group-hover:opacity-100 transition-opacity bg-surface-bright p-3 w-48 border border-error/50 pointer-events-none">
            <span className="font-headline text-[10px] uppercase tracking-widest text-error font-bold block mb-1">System_Threat</span>
            <p className="font-body text-[11px] text-on-surface">2 critical intrusions intercepted in the last 60 seconds.</p>
          </div>
        </button>
      </div>
    </div>
  );
}
