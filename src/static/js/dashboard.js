// @ts-nocheck
(function () {
  // Acessa as variáveis globais definidas no template
  var barLabels = window.chartLabels;
  var barCounts = window.chartCounts;

  var dataConfig = {
    labels: barLabels,
    datasets: [
      {
        label: "Quantidade de Mensagens",
        data: barCounts,
        backgroundColor: "rgba(54, 162, 235, 0.5)",
        borderColor: "rgba(54, 162, 235, 1)",
        borderWidth: 1,
      },
    ],
  };

  var barChartConfig = {
    type: "bar",
    data: dataConfig,
    options: {
      scales: {
        y: { beginAtZero: true },
      },
    },
  };

  var barCanvas = document.getElementById("messagesChart");
  if (barCanvas) {
    var barCtx = barCanvas.getContext("2d");
    new Chart(barCtx, barChartConfig);
  } else {
    console.error("Elemento messagesChart não encontrado.");
  }

  var lineLabels = window.lineLabels;
  var lineData = window.lineData;

  var lineDataConfig = {
    labels: lineLabels,
    datasets: [
      {
        label: "Mensagens por Dia",
        data: lineData,
        fill: false,
        borderColor: "rgba(255, 99, 132, 1)",
        tension: 0.1,
      },
    ],
  };

  var lineChartConfig = {
    type: "line",
    data: lineDataConfig,
    options: {
      scales: {
        y: { beginAtZero: true },
      },
    },
  };

  var lineCanvas = document.getElementById("lineChart");
  if (lineCanvas) {
    var lineCtx = lineCanvas.getContext("2d");
    new Chart(lineCtx, lineChartConfig);
  } else {
    console.error("Elemento lineChart não encontrado.");
  }
})();
