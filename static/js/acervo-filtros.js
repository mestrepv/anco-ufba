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

  if (!radios.length || !hiddenModo) return;

  radios.forEach(function (radio) {
    radio.addEventListener("change", function () {
      hiddenModo.value = this.value;
    });
  });
});
