document.addEventListener("DOMContentLoaded", () => {
    const snowContainer = document.getElementById("snow");

    function createSnowflake() {
        const snowflake = document.createElement("div");
        snowflake.classList.add("snowflake");
        snowflake.innerHTML = "❄";

        snowflake.style.left = Math.random() * window.innerWidth + "px";
        snowflake.style.fontSize = (Math.random() * 6 + 3) + "px";
        snowflake.style.animationDuration = (Math.random() * 5 + 5) + "s";

        snowContainer.appendChild(snowflake);

        setTimeout(() => {
            snowflake.remove();
        }, 10000);
    }

    setInterval(createSnowflake, 200);
});