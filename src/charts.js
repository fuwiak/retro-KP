import Chart from "chart.js/auto";

export function renderBarChart(ctx, tags, color) {
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: tags.map(t=>t.tag),
      datasets:[{label:'TOP TAGS', data:tags.map(t=>t.count), backgroundColor:color}]
    },
    options:{scales:{x:{ticks:{color:color}},y:{ticks:{color:color}}}}
  });
}
