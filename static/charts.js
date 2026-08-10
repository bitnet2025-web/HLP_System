// ELECTRICITY
new Chart(document.getElementById("electricityChart"), {
    type: "line",
    data: {
        labels: labels,
        datasets: [{
            label: "Electricity (kWh)",
            data: electricity,
            borderWidth: 2
        }]
    }
});

// WATER
new Chart(document.getElementById("waterChart"), {
    type: "bar",
    data: {
        labels: labels,
        datasets: [
            { label: "NCC Water", data: ncc },
            { label: "Borehole Water", data: borehole }
        ]
    }
});

// FUEL
new Chart(document.getElementById("fuelChart"), {
    type: "line",
    data: {
        labels: labels,
        datasets: [
            { label: "Diesel (Ltrs)", data: diesel },
            { label: "LPG (%)", data: lpg }
        ]
    }
});
