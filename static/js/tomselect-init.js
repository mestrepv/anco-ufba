// Transforma os <select multiple> de epistemologia/teoria em um campo de
// busca com tags (Tom Select), no lugar da lista nativa (ctrl+clique).
document.addEventListener("DOMContentLoaded", function () {
  if (!window.TomSelect) return;
  ["id_epistemologia", "id_teoria"].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    new TomSelect(el, {
      plugins: ["remove_button"],
      maxOptions: null,
      placeholder: "Digite para buscar e selecionar…",
      hideSelected: true,
    });
  });
});
