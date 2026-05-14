// Auto-dismiss flash messages after 4s
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 500); }, 4000);
  el.style.transition = 'opacity .5s';
});
