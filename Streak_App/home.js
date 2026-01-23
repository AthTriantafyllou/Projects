import { supabase } from "./supabase.js";

document.addEventListener("DOMContentLoaded", async () => {
  // 1. Check session
  const {
    data: { session }
  } = await supabase.auth.getSession();

  if (!session) {
    window.location.href = "/streaks/pages/login.html";
    return;
  }

  const userId = session.user.id;

  function getLocalDateYYYYMMDD() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  }

  // Reset broken streaks (runs once on app open)
  await supabase.rpc("reset_broken_streaks", {
    user_id_input: userId,
    today_input: getLocalDateYYYYMMDD()
  });



  //----------------
  // to color the bubbles correctly
  //----------------

  const today = getLocalDateYYYYMMDD();

  // Fetch today's activity history
  const { data: todayHistory, error: historyError } = await supabase
    .from("activity_history")
    .select("activity_id, completed, frozen")
    .eq("user_id", userId)
    .eq("date", today);

  if (historyError) {
    console.error(historyError);
  }

  const todayStateMap = new Map();

  (todayHistory || []).forEach(row => {
    todayStateMap.set(row.activity_id, {
      completed: row.completed,
      frozen: row.frozen
    });
  });
  // ------------ that WAS so that the colors match the completion of the activity




  const { data: items } = await supabase
    .from("user_items")
    .select("freeze_count, coins")
    .eq("user_id", userId)
    .single();

  const itemsBar = document.getElementById("items-bar");



  itemsBar.innerHTML = `
    <div class="items-bar-inner">
      <span class="item-count">
        <img src="/streaks/assets/icons/freeze.webp" class="app-icon sm" alt="Freezes">
        ${items?.freeze_count ?? 0}
      </span>

      <span class="item-count">
        <img src="/streaks/assets/icons/coins.webp" class="app-icon sm" alt="Coins">
        ${items?.coins ?? 0}
      </span>
    </div>
  `;




  // 2. Fetch user activities + activity data
  const { data, error } = await supabase
  .from("user_activities")
  .select(`
    id,
    streak_count,
    activity:activities (
      id,
      name,
      created_at
    )
  `)
    .eq("user_id", userId)
    .order("created_at", { foreignTable: "activities", ascending: true });

  if (error) {
    console.error(error);
    alert("Failed to load activities");
    return;
  }

  // 3. Render
  const list = document.getElementById("activities-list");
  list.innerHTML = "";

  if (data.length === 0) {
    list.innerHTML = "<li>No activities yet</li>";
  } else {
    data.forEach(item => {
      const li = document.createElement("li");
      li.classList.add("activity-card", "glass", "glass-dark");

      // DEFAULT state --- so that the colors match with the completion of the activity
      li.classList.add("state-default");

      const todayState = todayStateMap.get(item.activity.id);

      // Priority: frozen > completed > default
      if (todayState?.frozen === true) {
        li.classList.remove("glass-dark", "state-default");
        li.classList.add("glass-blue", "state-frozen");
      } else if (todayState?.completed === true) {
        li.classList.remove("glass-dark", "state-default");
        li.classList.add("glass-orange", "state-completed");
      }
      // ------ that was so that the colors match with the completion of the activity


      // icon logic (default uses flame for now)
      const iconSrc =
        todayState?.frozen === true
          ? "/streaks/assets/icons/freeze.webp"
          : "/streaks/assets/icons/flame.webp"; // completed OR default (for now)

      const iconAlt = todayState?.frozen === true ? "Frozen" : "Streak";

      li.innerHTML = `
        <div class="activity-name">${item.activity.name}</div>
        <div class="activity-streak">
          <img src="${iconSrc}" class="app-icon sm" alt="${iconAlt}">
          ${item.streak_count}
        </div>
      `;


      li.addEventListener("click", () => {
        window.location.href =
          `/streaks/pages/activity.html?id=${item.activity.id}`;
      });

      list.appendChild(li);
    });
  }

  // 4.add activity button
  document
  .getElementById("add-activity-btn")
  .addEventListener("click", () => {
    window.location.href = "/streaks/pages/create-activity.html";
  });



});
