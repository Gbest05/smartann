/**
 * Smart Energy Management System - Chart.js Theme & Visualizations
 * Palette: Green (#16A34A), Deep Green (#15803D), Amber (#F59E0B), Red (#DC2626), Dark (#1F2937)
 * Strictly NO BLUE colors used.
 */

const ENERGY_COLORS = {
    primary: '#16A34A',
    primaryLight: 'rgba(22, 163, 74, 0.15)',
    secondary: '#15803D',
    amber: '#F59E0B',
    amberLight: 'rgba(245, 158, 11, 0.15)',
    red: '#DC2626',
    redLight: 'rgba(220, 38, 38, 0.15)',
    dark: '#1F2937',
    grid: '#E2E8F0',
    text: '#4B5563'
};

/**
 * Initialize 14-day Consumption Trend Line Chart
 */
function initConsumptionTrendChart(canvasId, labels, dataPoints) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Electricity Consumption (kWh)',
                data: dataPoints,
                borderColor: ENERGY_COLORS.primary,
                backgroundColor: ENERGY_COLORS.primaryLight,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: ENERGY_COLORS.primaryDark || ENERGY_COLORS.primary,
                pointBorderColor: '#FFFFFF',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: { color: ENERGY_COLORS.text, font: { family: 'Segoe UI', size: 12, weight: '500' } }
                },
                tooltip: {
                    backgroundColor: ENERGY_COLORS.dark,
                    titleFont: { family: 'Segoe UI', size: 13, weight: '600' },
                    bodyFont: { family: 'Segoe UI', size: 12 },
                    padding: 10,
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            return ` ${context.dataset.label}: ${context.parsed.y.toFixed(2)} kWh`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: ENERGY_COLORS.grid, drawBorder: false },
                    ticks: { color: ENERGY_COLORS.text, font: { size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: ENERGY_COLORS.grid, drawBorder: false },
                    ticks: {
                        color: ENERGY_COLORS.text,
                        font: { size: 11 },
                        callback: function(value) { return value + ' kWh'; }
                    }
                }
            }
        }
    });
}

/**
 * Initialize Peak vs Off-Peak Stacked Bar Chart
 */
function initPeakOffPeakChart(canvasId, labels, peakData, offPeakData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Peak Hours (kWh)',
                    data: peakData,
                    backgroundColor: ENERGY_COLORS.amber,
                    borderRadius: 4
                },
                {
                    label: 'Off-Peak Hours (kWh)',
                    data: offPeakData,
                    backgroundColor: ENERGY_COLORS.primary,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: ENERGY_COLORS.text, font: { size: 12 } }
                },
                tooltip: {
                    backgroundColor: ENERGY_COLORS.dark,
                    padding: 10,
                    cornerRadius: 8
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { color: ENERGY_COLORS.text, font: { size: 11 } }
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    grid: { color: ENERGY_COLORS.grid },
                    ticks: {
                        color: ENERGY_COLORS.text,
                        callback: function(v) { return v + ' kWh'; }
                    }
                }
            }
        }
    });
}

/**
 * Initialize Predicted vs Actual Comparison Chart
 */
function initPredVsActualChart(canvasId, labels, actualData, predData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Actual Consumption (kWh)',
                    data: actualData,
                    borderColor: ENERGY_COLORS.primary,
                    backgroundColor: 'transparent',
                    borderWidth: 2.5,
                    pointRadius: 4
                },
                {
                    label: 'ANN Predicted (kWh)',
                    data: predData,
                    borderColor: ENERGY_COLORS.amber,
                    backgroundColor: 'transparent',
                    borderWidth: 2.5,
                    borderDash: [5, 5],
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: ENERGY_COLORS.text, font: { size: 12 } }
                },
                tooltip: {
                    backgroundColor: ENERGY_COLORS.dark,
                    padding: 10,
                    cornerRadius: 8
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: ENERGY_COLORS.text } },
                y: {
                    beginAtZero: true,
                    grid: { color: ENERGY_COLORS.grid },
                    ticks: {
                        color: ENERGY_COLORS.text,
                        callback: function(v) { return v + ' kWh'; }
                    }
                }
            }
        }
    });
}
