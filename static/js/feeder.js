// AquaMon — Feeder Page JS

let currentMode = 'every_8h';
let currentAmount = 5.0;
let customTimes = [];
let startTime = '08:00';

function initFeeder(schedule) {
  currentMode = schedule.mode || 'every_8h';
  currentAmount = schedule.quantity_grams || 5.0;
  startTime = schedule.start_time || '08:00';
  document.getElementById('amount-num').textContent = currentAmount.toFixed(1);
  if (document.getElementById('start-time')) {
    document.getElementById('start-time').value = startTime;
  }

  if (schedule.custom_times) {
    try {
      customTimes = JSON.parse(schedule.custom_times);
    } catch {
      customTimes = [];
    }
  }
  renderCustomTimes();
  updateCyclePreview();
}

function setMode(mode, btn) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const customSection = document.getElementById('custom-section');
  const presetSection = document.getElementById('preset-config');
  customSection.style.display = mode === 'custom' ? 'block' : 'none';
  presetSection.style.display = mode === 'custom' ? 'none' : 'block';
  updateCyclePreview();
}

function updateCyclePreview() {
  const preview = document.getElementById('cycle-preview');
  const startInput = document.getElementById('start-time');
  if (!preview || !startInput) return;
  
  if (currentMode === 'custom') {
    preview.innerHTML = '';
    return;
  }

  startTime = startInput.value;
  const [h, m] = startTime.split(':').map(Number);
  let times = [];

  if (currentMode === 'every_8h') {
    times = [0, 8, 16].map(offset => `${(h + offset) % 24}:${m.toString().padStart(2, '0')}`);
  } else if (currentMode === 'every_12h') {
    times = [0, 12].map(offset => `${(h + offset) % 24}:${m.toString().padStart(2, '0')}`);
  } else if (currentMode === 'every_24h') {
    times = [startTime];
  }

  preview.innerHTML = `
    <div class="preview-label">Next feed times:</div>
    <div class="preview-chips">
      ${times.map(t => `<span class="time-chip">${t}</span>`).join('')}
    </div>
  `;
}

function changeAmount(delta) {
  currentAmount = Math.max(0.5, Math.min(50, currentAmount + delta));
  document.getElementById('amount-num').textContent = currentAmount.toFixed(1);
}

function addTimeSlot() {
  customTimes.push('08:00');
  renderCustomTimes();
}

function removeTimeSlot(index) {
  customTimes.splice(index, 1);
  renderCustomTimes();
}

function renderCustomTimes() {
  const list = document.getElementById('time-list');
  if (!list) return;
  list.innerHTML = '';
  customTimes.forEach((t, i) => {
    const div = document.createElement('div');
    div.className = 'time-slot';
    div.innerHTML = `
      <span style="font-size:16px">🕐</span>
      <input type="time" value="${t}" onchange="customTimes[${i}] = this.value" />
      <button class="remove-time" onclick="removeTimeSlot(${i})">✕</button>
    `;
    list.appendChild(div);
  });
}

async function saveSchedule() {
  const payload = {
    mode: currentMode,
    quantity_grams: currentAmount,
    custom_times: currentMode === 'custom' ? JSON.stringify(customTimes) : null,
    start_time: startTime
  };
  try {
    const r = await fetch('/api/feeder/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (data.success) showToast('✅ Schedule saved successfully!');
  } catch (e) {
    showToast('❌ Error saving schedule.', true);
  }
}

async function feedNow() {
  try {
    const r = await fetch('/api/feeder/feed-now', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount: currentAmount })
    });
    const data = await r.json();
    if (data.success) {
      showToast(`🐠 ${data.message}`);
    }
  } catch (e) {
    showToast('❌ Failed to trigger feeding.', true);
  }
}

function showToast(msg, error = false) {
  const toast = document.getElementById('feeder-toast');
  toast.textContent = msg;
  toast.style.display = 'block';
  toast.style.background = error ? 'rgba(255,61,90,0.08)' : 'rgba(0,232,122,0.08)';
  toast.style.borderColor = error ? '#ff3d5a' : '#00e87a';
  toast.style.color = error ? '#ff3d5a' : '#00e87a';
  setTimeout(() => { toast.style.display = 'none'; }, 3500);
}
