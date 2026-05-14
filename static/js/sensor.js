// AquaMon — Sensor Page JS

let chartInstance = null;
let allHistory = [];

const STATUS_COLORS = {
  green:  '#00e87a',
  yellow: '#f5c518',
  orange: '#ff8c42',
  red:    '#ff3d5a',
};

function getStatusColor(sensor, values) {
  // Use the last value's status for chart color
  return STATUS_COLORS;
}

function initSensorChart(history) {
  allHistory = history;
  renderChart(history);
}

function renderChart(history) {
  const ctx = document.getElementById('sensorChart').getContext('2d');
  if (chartInstance) chartInstance.destroy();

  const labels = history.map(h => {
    const d = new Date(h.timestamp);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  });
  const values = history.map(h => h.value);

  // Gradient fill
  const gradient = ctx.createLinearGradient(0, 0, 0, 240);
  gradient.addColorStop(0, 'rgba(0,200,255,0.3)');
  gradient.addColorStop(1, 'rgba(0,200,255,0)');

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: SENSOR_TYPE,
        data: values,
        borderColor: '#00c8ff',
        backgroundColor: gradient,
        borderWidth: 2,
        pointRadius: history.length > 30 ? 0 : 3,
        pointHoverRadius: 5,
        pointBackgroundColor: '#00c8ff',
        fill: true,
        tension: 0.4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0d1826',
          borderColor: '#1a3048',
          borderWidth: 1,
          titleColor: '#7aa8cc',
          bodyColor: '#e8f4ff',
          callbacks: {
            label: ctx => ` ${ctx.parsed.y}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(26,48,72,0.5)' },
          ticks: {
            color: '#3d6080',
            maxTicksLimit: 8,
            font: { family: 'Space Mono', size: 10 }
          }
        },
        y: {
          grid: { color: 'rgba(26,48,72,0.5)' },
          ticks: {
            color: '#3d6080',
            font: { family: 'Space Mono', size: 10 }
          }
        }
      }
    }
  });
}

function setRange(btn, points) {
  document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const slice = allHistory.slice(-points);
  renderChart(slice);
}

async function refreshSensorValue(sensor_type) {
  try {
    const r = await fetch(`/api/sensor/${sensor_type}/latest`);
    const data = await r.json();

    const valEl = document.getElementById('live-value');
    if (valEl) valEl.textContent = data.value;

    // Update hero status class
    const hero = document.querySelector('.sensor-hero');
    if (hero) {
      hero.className = `sensor-hero status-${data.status}`;
    }

    // Push to chart
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (chartInstance) {
      chartInstance.data.labels.push(now);
      chartInstance.data.datasets[0].data.push(data.value);
      if (chartInstance.data.labels.length > 100) {
        chartInstance.data.labels.shift();
        chartInstance.data.datasets[0].data.shift();
      }
      chartInstance.update('none');
    }
    allHistory.push({ value: data.value, timestamp: new Date().toISOString() });
  } catch (e) { console.error(e); }
}
