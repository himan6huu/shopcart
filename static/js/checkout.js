// Format card number with spaces
const cardInput = document.getElementById('card_number');
if (cardInput) {
  cardInput.addEventListener('input', e => {
    let v = e.target.value.replace(/\D/g, '').slice(0, 16);
    e.target.value = v.replace(/(.{4})/g, '$1 ').trim();
  });
}
// Format expiry MM/YY
const expiryInput = document.getElementById('expiry');
if (expiryInput) {
  expiryInput.addEventListener('input', e => {
    let v = e.target.value.replace(/\D/g, '').slice(0, 4);
    if (v.length > 2) v = v.slice(0, 2) + '/' + v.slice(2);
    e.target.value = v;
  });
}
