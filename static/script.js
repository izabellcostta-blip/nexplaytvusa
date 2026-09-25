const btn = document.getElementById('langBtn');
let lang = 'pt';
function applyLanguage(){
  document.documentElement.lang = lang === 'pt' ? 'pt-BR' : 'en';
  document.querySelectorAll('[data-pt][data-en]').forEach(el=>{
    el.innerHTML = el.dataset[lang];
  });
  btn.textContent = lang === 'pt' ? '🇧🇷 PT' : '🇺🇸 EN';
}
btn.addEventListener('click', ()=>{ lang = lang === 'pt' ? 'en' : 'pt'; applyLanguage(); });
applyLanguage();
