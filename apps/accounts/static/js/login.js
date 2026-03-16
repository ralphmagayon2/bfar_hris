// Password toggle
const pwInput   = document.getElementById("id_password");
const toggleBtn = document.getElementById("toggle-pw");
const pwEye     = document.getElementById("pw-eye");

if (toggleBtn && pwInput) {
    toggleBtn.addEventListener("click", () => {
    const isText = pwInput.type === "text";
    pwInput.type = isText ? "password" : "text";
    pwEye.className = isText ? "fas fa-eye" : "fas fa-eye-slash";
    });
}

// Loading state on submit
const form      = document.getElementById("login-form");
const loginBtn  = document.getElementById("btn-login");

if (form && loginBtn) {
    form.addEventListener("submit", () => {
    loginBtn.classList.add("loading");
    loginBtn.disabled = true;
    });
}