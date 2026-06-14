// =========================================
// AUTO CLOSE ALERTS
// =========================================

setTimeout(() => {

    let alerts = document.querySelectorAll(".alert");

    alerts.forEach((alert) => {

        alert.style.transition = "opacity 0.5s ease";

        alert.style.opacity = "0";

        setTimeout(() => {
            alert.remove();
        }, 500);

    });

}, 3000);


// =========================================
// CONFIRM DELETE
// =========================================

document.addEventListener("DOMContentLoaded", () => {

    let deleteButtons = document.querySelectorAll(".btn-danger");

    deleteButtons.forEach((button) => {

        button.addEventListener("click", (e) => {

            if (
                button.innerText.trim().toLowerCase() === "delete"
            ) {

                let confirmDelete = confirm(
                    "Are you sure you want to delete this appointment?"
                );

                if (!confirmDelete) {
                    e.preventDefault();
                }

            }

        });

    });

});


// =========================================
// LOADING BUTTON EFFECT
// =========================================

document.addEventListener("DOMContentLoaded", () => {

    let forms = document.querySelectorAll("form");

    forms.forEach((form) => {

        form.addEventListener("submit", () => {

            let submitBtn = form.querySelector(
                "button[type='submit'], input[type='submit']"
            );

            if (submitBtn) {

                submitBtn.disabled = true;

                submitBtn.innerHTML = "Processing...";

            }

        });

    });

});


// =========================================
// TABLE SEARCH FILTER
// =========================================

function searchTable() {

    let input = document.getElementById("tableSearch");

    if (!input) return;

    let filter = input.value.toLowerCase();

    let table = document.querySelector("table tbody");

    let rows = table.querySelectorAll("tr");

    rows.forEach((row) => {

        let text = row.innerText.toLowerCase();

        if (text.includes(filter)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }

    });

}


// =========================================
// DARK MODE TOGGLE
// =========================================

function toggleDarkMode() {

    document.body.classList.toggle("dark-mode");

    let darkMode = document.body.classList.contains(
        "dark-mode"
    );

    localStorage.setItem("darkMode", darkMode);

}


// =========================================
// LOAD DARK MODE
// =========================================

window.onload = () => {

    let darkMode = localStorage.getItem("darkMode");

    if (darkMode === "true") {
        document.body.classList.add("dark-mode");
    }

};


// =========================================
// ANIMATED COUNTER
// =========================================

function animateCounter(id, target) {

    let element = document.getElementById(id);

    if (!element) return;

    let count = 0;

    let speed = target / 50;

    let updateCounter = () => {

        count += speed;

        if (count < target) {

            element.innerText = Math.floor(count);

            requestAnimationFrame(updateCounter);

        } else {

            element.innerText = target;

        }

    };

    updateCounter();

}


// =========================================
// MOBILE MENU
// =========================================

function toggleMenu() {

    let menu = document.getElementById("mobileMenu");

    if (menu) {

        menu.classList.toggle("show");

    }

}


// =========================================
// TOOLTIP ACTIVATION
// =========================================

document.addEventListener("DOMContentLoaded", () => {

    let tooltipTriggerList = [].slice.call(
        document.querySelectorAll('[data-bs-toggle="tooltip"]')
    );

    tooltipTriggerList.map(function (tooltipTriggerEl) {

        return new bootstrap.Tooltip(tooltipTriggerEl);

    });

});


// =========================================
// DATE VALIDATION
// =========================================

document.addEventListener("DOMContentLoaded", () => {

    let dateInput = document.querySelector(
        "input[type='date']"
    );

    if (dateInput) {

        let today = new Date().toISOString().split("T")[0];

        dateInput.setAttribute("min", today);

    }

});


// =========================================
// SUCCESS SOUND
// =========================================

function playSuccessSound() {

    let audio = new Audio(
        "https://www.soundjay.com/buttons/sounds/button-3.mp3"
    );

    audio.play();

}