import { supabase } from "./supabase.js";

function showError(message) {
  const el = document.getElementById("error");
  el.style.display = "block";
  el.textContent = message;
}

document.addEventListener("DOMContentLoaded", async () => {
  // Auth guard
  const { data: sessionData, error: sessionError } =
    await supabase.auth.getSession();

  if (sessionError) {
    console.error(sessionError);
    showError("Failed to read session.");
    return;
  }

  if (!sessionData.session) {
    window.location.href = "/streaks/pages/login.html";
    return;
  }

  const userId = sessionData.session.user.id;

  // Load items
  const { data, error } = await supabase
    .from("user_items")
    .select("freeze_count, coins")
    .eq("user_id", userId)
    .single();

  if (error) {
    console.error(error);
    showError("Failed to load items.");
    return;
  }

  document.getElementById("freeze-count").textContent =
    data.freeze_count ?? 0;

  document.getElementById("coin-count").textContent =
    data.coins ?? 0;

  let currentCoins = data.coins ?? 0;



  //buy freezes with coins
  document.querySelectorAll("button[data-freezes]").forEach(btn => {
  btn.addEventListener("click", () => {
    const freezes = Number(btn.dataset.freezes);
    const cost = Number(btn.dataset.cost);

    if (currentCoins < cost) {
      showToast("Not enough coins");
      return;
    }

    openConfirm(`Buy ${freezes} freeze(s) for ${cost} coins?`, async () => {
      const { error } = await supabase.rpc("buy_freezes", {
        user_id_input: userId,
        freeze_amount: freezes,
        coin_cost: cost
      });

      if (error) {
        console.error(error);
        showToast("Purchase failed.");
        return;
      }

      window.location.reload();
    });
  });
});


});
