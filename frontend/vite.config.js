import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import os from 'node:os'

// Pick the laptop's most-likely LAN-routable IPv4 so the QR can encode a URL
// the phone can actually reach. Order of preference (most → least likely to
// be the home/office Wi-Fi address):
//   192.168.x.x  →  10.x.x.x  →  172.16-31.x.x  → anything else non-internal
// Skips loopback, IPv6, and Docker bridge ranges (172.17–31 is filtered by
// being last and never the *first* match on a normal laptop).
function detectLanIp() {
  const nets = os.networkInterfaces()
  const candidates = []
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      if (net.family !== 'IPv4' || net.internal) continue
      let rank = 4
      if (net.address.startsWith('192.168.')) rank = 0
      else if (net.address.startsWith('10.')) rank = 1
      else if (/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(net.address)) rank = 2
      candidates.push({ ip: net.address, rank, iface: name })
    }
  }
  candidates.sort((a, b) => a.rank - b.rank)
  return candidates[0]?.ip || null
}

const LAN_IP = detectLanIp()
if (LAN_IP) {
  // eslint-disable-next-line no-console
  console.log(`\n  ➜  LAN address for the QR/phone: ${LAN_IP}  (Vite's Network URL below uses this)\n`)
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,    // bind to 0.0.0.0 so phones on the same Wi-Fi can hit the dev server
    port: 5173,
    // Proxy backend API paths to Django so the phone only ever talks to the
    // Vite port — no firewall rule for 8000 and no DJANGO_ALLOWED_HOSTS tweak
    // needed for LAN or tunnel access.
    proxy: {
      '/users':     'http://localhost:8000',
      '/moods':     'http://localhost:8000',
      '/playlists': 'http://localhost:8000',
      '/groups':    'http://localhost:8000',
      '/tracks':    'http://localhost:8000',
      '/feedback':  'http://localhost:8000',
      '/admin':     'http://localhost:8000',
    },
  },
  define: {
    // Available as `__LAN_IP__` everywhere in the app. Null if Vite couldn't
    // find a routable interface (rare — laptop with no Wi-Fi/Ethernet).
    __LAN_IP__: JSON.stringify(LAN_IP),
  },
})
