/**
 * PREDICT-X // FUTURISTIC TELEMETRY & INTERACTIVE SCRIPT
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Live Telemetry Clock
  function updateTelemetryClock() {
    const clockElements = document.querySelectorAll('.cyber-clock');
    const now = new Date();
    const utcString = now.toUTCString().replace('GMT', 'UTC');
    const timeFormatted = now.toISOString().substring(11, 19) + ' UTC';

    clockElements.forEach(el => {
      el.textContent = timeFormatted;
    });
  }

  setInterval(updateTelemetryClock, 1000);
  updateTelemetryClock();

  // 2. Telemetry Live Micro-Oscillation (adds realistic HUD sensor life)
  const oscElements = document.querySelectorAll('[data-telemetry-osc]');
  if (oscElements.length > 0) {
    setInterval(() => {
      oscElements.forEach(el => {
        const base = parseFloat(el.getAttribute('data-base') || el.textContent);
        const variance = parseFloat(el.getAttribute('data-variance') || 0.4);
        const unit = el.getAttribute('data-unit') || '';
        const randomDelta = (Math.random() * variance * 2 - variance);
        const newValue = (base + randomDelta).toFixed(1);
        el.textContent = newValue + unit;
      });
    }, 2500);
  }

  // 3. Alert close handler
  const closeButtons = document.querySelectorAll('.cyber-alert-close');
  closeButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.cyber-alert');
      if (alert) {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        alert.style.transition = 'all 0.3s ease';
        setTimeout(() => alert.remove(), 300);
      }
    });
  });

  // 4. Auto-dismiss flash messages after 6 seconds
  const autoAlerts = document.querySelectorAll('.cyber-alert');
  if (autoAlerts.length > 0) {
    setTimeout(() => {
      autoAlerts.forEach(alert => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        alert.style.transition = 'all 0.3s ease';
        setTimeout(() => alert.remove(), 300);
      });
    }, 6000);
  }
});
