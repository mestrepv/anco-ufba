/**
 * Sincroniza o radio "modo" (busca-form) com o hidden "modo" (filtros-form).
 *
 * Os dois formulários são separados por necessidade: busca-form gerencia
 * query + toggle, filtros-form gerencia as facetas. Quando o usuário muda
 * o modo sem clicar "Buscar" e depois aplica filtros, o hidden do
 * filtros-form ficaria desatualizado sem esta sincronização.
 */
document.addEventListener("DOMContentLoaded", function () {
  const radios = document.querySelectorAll(
    "#busca-form input[type='radio'][name='modo']"
  );
  const hiddenModo = document.querySelector(
    "#filtros-form input[type='hidden'][name='modo']"
  );

  if (radios.length && hiddenModo) {
    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        hiddenModo.value = this.value;
      });
    });
  }

  initAnoPresets();
  initFiltrosFormCleanup();
});

/**
 * Atalhos do filtro de ano: clique preenche os inputs De/Até.
 * Não submete o formulário — usuário confirma com "Aplicar filtros".
 */
function initAnoPresets() {
  const minInput = document.getElementById("ano-min-input");
  const maxInput = document.getElementById("ano-max-input");
  if (!minInput || !maxInput) return;

  document.querySelectorAll(".ano-preset").forEach(function (btn) {
    btn.addEventListener("click", function () {
      minInput.value = btn.dataset.lo || "";
      maxInput.value = btn.dataset.hi || "";
    });
  });
}

/**
 * Antes de submeter os filtros, remove o `name` de inputs vazios para
 * que não apareçam como `?ano_min=&ano_max=` na URL.
 */
function initFiltrosFormCleanup() {
  const form = document.getElementById("filtros-form");
  if (!form) return;
  form.addEventListener("submit", function () {
    form.querySelectorAll("input[name]").forEach(function (el) {
      if (el.type === "number" && el.value === "") {
        el.disabled = true; // disabled fields são omitidos do submit
      }
    });
  });
}
