/* PetGo — JavaScript progressivo */

// CSRF helper para requisições fetch
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

// Fecha alertas ao clicar
document.querySelectorAll('.alert').forEach(el => {
  el.style.cursor = 'pointer';
  el.addEventListener('click', () => el.remove());
});

// Confirmação antes de ações destrutivas
document.querySelectorAll('[data-confirm]').forEach(btn => {
  btn.addEventListener('click', e => {
    if (!confirm(btn.dataset.confirm)) e.preventDefault();
  });
});
