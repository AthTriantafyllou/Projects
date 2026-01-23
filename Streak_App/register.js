import { supabase } from "./supabase.js";

const form = document.getElementById("register-form");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: {
    emailRedirectTo: "https://thanfyllou.eu/streaks/pages/login.html"
  }
  });

  if (error) {
    alert(error.message);
  } else {
    alert("Check your email to confirm your account.");
    window.location.href = "/streaks/pages/login.html";
  }
});
