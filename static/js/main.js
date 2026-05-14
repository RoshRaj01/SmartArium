// AquaMon — Main JS

function toggleSidebar() {
  const s = document.getElementById('sidebar');
  const o = document.getElementById('sidebar-overlay');
  s.classList.toggle('open');
  o.classList.toggle('open');
}

function updateClock() {
  const el = document.getElementById('clock');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

async function dismissAlert(id, btn) {
  try {
    await fetch(`/api/alerts/dismiss/${id}`, { method: 'POST' });
    const el = btn.closest('.alert-banner') || btn.closest('.notif-item');
    if (el) {
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 300);
    }
  } catch (e) { console.error(e); }
}

async function refreshDashboard() {
  try {
    const r = await fetch('/api/sensors/all');
    const data = await r.json();

    for (const [key, info] of Object.entries(data.sensors)) {
      // Update value
      const valEl = document.getElementById(`val-${key}`);
      if (valEl) valEl.textContent = info.value;

      // Update card class
      const card = document.getElementById(`card-${key}`);
      if (card) {
        card.className = `sensor-card status-${info.status}`;
      }

      // Update sidebar dots
      const dot = document.getElementById(`nav-status-${key}`);
      if (dot) {
        dot.className = `nav-status visible ${info.status}`;
      }
    }

    // Update alerts
    const alertsSection = document.getElementById('alerts-section');
    if (alertsSection) {
      alertsSection.innerHTML = '';
      for (const alert of data.alerts) {
        const div = document.createElement('div');
        div.className = `alert-banner alert-${alert.severity}`;
        div.dataset.id = alert.id;
        div.innerHTML = `
          <span class="alert-msg">${alert.message}</span>
          <button class="alert-dismiss" onclick="dismissAlert(${alert.id}, this)">✕</button>
        `;
        alertsSection.appendChild(div);
      }
    }

    // Update notif badge
    const badge = document.getElementById('notif-count');
    if (badge) {
      const count = data.alerts.length;
      badge.textContent = count;
      badge.classList.toggle('visible', count > 0);
    }

    computeStats(data.sensors);
  } catch (e) { console.error('Dashboard refresh error:', e); }
}

function computeStats(sensors) {
  if (!sensors) {
    // parse from DOM
    sensors = {};
    document.querySelectorAll('.sensor-card').forEach(card => {
      const key = card.id.replace('card-', '');
      const cls = [...card.classList].find(c => c.startsWith('status-') && c !== 'sensor-card');
      sensors[key] = { status: cls?.replace('status-', '') || 'green' };
    });
  }
  const counts = { green: 0, yellow: 0, orange: 0, red: 0 };
  Object.values(sensors).forEach(s => {
    const st = s.status || 'green';
    counts[st] = (counts[st] || 0) + 1;
  });
  const g = document.getElementById('stat-good');
  const w = document.getElementById('stat-warn');
  const c = document.getElementById('stat-crit');
  if (g) g.textContent = counts.green;
  if (w) w.textContent = (counts.yellow || 0) + (counts.orange || 0);
  if (c) c.textContent = counts.red;

  // sidebar dots for initial load
  document.querySelectorAll('.sensor-card').forEach(card => {
    const key = card.id.replace('card-', '');
    const cls = [...card.classList].find(c => c.startsWith('status-') && c !== 'sensor-card');
    const status = cls?.replace('status-', '') || 'green';
    const dot = document.getElementById(`nav-status-${key}`);
    if (dot) dot.className = `nav-status visible ${status}`;
  });
}
