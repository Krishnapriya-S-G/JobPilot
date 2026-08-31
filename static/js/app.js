// =========================
// JOBPILOT GLOBAL JAVASCRIPT
// =========================

console.log("JobPilot application loaded.");


// =========================
// AUTO HIDE ALERTS
// =========================

setTimeout(() => {

    const alerts =
        document.querySelectorAll(".alert");

    alerts.forEach(alert => {

        alert.style.transition =
            "opacity 0.5s";

        alert.style.opacity = "0";

        setTimeout(() => {

            alert.remove();

        }, 500);

    });

}, 5000);