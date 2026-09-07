const form = document.querySelector("#starter-form");
const input = document.querySelector("#starter-input");
const status = document.querySelector("#status");

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = input.value.trim();
  status.textContent = value ? `Saved: ${value}` : "Enter text before saving.";
});
