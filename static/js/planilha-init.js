// Inicializa a grade Tabulator da pagina /acervo/planilha/.
// Os dados vem inline em <script id="dados-planilha" type="application/json">.
// O script externo de Tabulator esta em <head> com `defer`, entao o
// listener DOMContentLoaded ja roda apos o carregamento dele.

(function () {
  function escape(v) {
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function tituloCelula(cell) {
    var row = cell.getRow().getData();
    var titulo = escape(cell.getValue() || "");
    return '<a href="' + escape(row.url) + '" class="text-anco hover:underline">' + titulo + "</a>";
  }

  function linkExterno(cell) {
    var v = cell.getValue();
    if (!v) return "";
    return '<a href="' + escape(v) + '" target="_blank" rel="noopener" class="text-slate-600 hover:text-anco underline">acesso</a>';
  }

  function simNao(cell) {
    return cell.getValue() ? "Sim" : "—";
  }

  function init() {
    var node = document.getElementById("dados-planilha");
    if (!node || typeof Tabulator === "undefined") return;
    var dados;
    try {
      dados = JSON.parse(node.textContent);
    } catch (e) {
      console.error("planilha: JSON invalido", e);
      return;
    }
    new Tabulator("#planilha", {
      data: dados,
      layout: "fitDataStretch",
      height: "75vh",
      pagination: true,
      paginationSize: 100,
      paginationSizeSelector: [50, 100, 250, 500],
      placeholder: "Sem analises para exibir.",
      movableColumns: true,
      columns: [
        { title: "Ano", field: "ano", width: 80, headerFilter: "input", sorter: "number" },
        { title: "Titulo", field: "titulo", widthGrow: 4, minWidth: 320, headerFilter: "input", formatter: tituloCelula },
        { title: "Autores", field: "autores", widthGrow: 2, minWidth: 200, headerFilter: "input" },
        { title: "Periodico", field: "periodico", widthGrow: 2, minWidth: 200, headerFilter: "input" },
        { title: "Base", field: "base", width: 130, headerFilter: "input" },
        { title: "Grande área", field: "area", width: 170, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
        { title: "Epistemologia", field: "epistemologia", widthGrow: 2, minWidth: 180, headerFilter: "input" },
        { title: "Teoria", field: "teoria", widthGrow: 2, minWidth: 180, headerFilter: "input" },
        { title: "Resenha", field: "tem_resenha", width: 100, headerFilter: "tickCross", headerFilterParams: { tristate: true }, formatter: simNao, hozAlign: "center" },
        { title: "Acesso aberto", field: "acesso_aberto", width: 130, headerFilter: "tickCross", headerFilterParams: { tristate: true }, formatter: simNao, hozAlign: "center" },
        { title: "Status", field: "status", width: 130, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
        { title: "Analista", field: "analista", widthGrow: 1, minWidth: 160, headerFilter: "input" },
        { title: "Publicada em", field: "publicada_em", width: 130, headerFilter: "input", sorter: "date", sorterParams: { format: "yyyy-MM-dd" } },
        { title: "DOI", field: "doi", widthGrow: 1, minWidth: 180, headerFilter: "input" },
        { title: "Link", field: "link_artigo", width: 80, formatter: linkExterno, headerSort: false },
      ],
      initialSort: [{ column: "publicada_em", dir: "desc" }],
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
