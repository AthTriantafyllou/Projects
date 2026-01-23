import { supabase } from "./supabase.js";

document.addEventListener("DOMContentLoaded", async () => {
  const {
    data: { session }
  } = await supabase.auth.getSession();

  if (session) {
    window.location.href = "/streaks/pages/home.html";
  } else {
    window.location.href = "/streaks/pages/login.html";
  }

  // Assuming this is in your login success handler or DOMContentLoaded
  const { data: sessionData } = await supabase.auth.getSession();
  if (sessionData.session) {
    const userId = sessionData.session.user.id;
    // NEW: Trigger streak reset on login to catch any missed days
    await supabase.rpc("reset_broken_streaks", { user_id_input: userId });
  }
  
});
