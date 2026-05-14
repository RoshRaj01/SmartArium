// AquaMon — Feeder Page JS

let currentMode = 'every_8h';
let currentAmount = 5.0;
let customTimes = [];

function initFeeder(schedule) {
  currentMode = schedule.mode || 'every_8h';
  currentAmount = schedule.quantity_grams || 5.0;
  document.getElementById('amount-num').textContent = currentAmount.toFixed(1);

  if (schedule.custom_times) {
    try {
      customTimes = JSON.parse(schedule.custom_times);
    } catch {
      customTimes = [];
    }
  }
  renderCustomTimes();
}

function setMode(mode, btn) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const customSection = document.getElementById('custom-section');
  customSection.style.display = mode === 'custom' ? 'block' : 'none';
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
