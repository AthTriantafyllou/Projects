import { supabase } from "./supabase.js";

/* -------------------------
   HELPERS (Simplified)
------------------------- */

function getActivityIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

// Removed: getLocalDateYYYYMMDD() - No more client-side dates; server handles it.

/* -------------------------
   MAIN
------------------------- */

document.addEventListener("DOMContentLoaded", async () => {
  console.log("activity.js LOADED");

  // 1) Auth guard (unchanged)
  const { data: sessionData } = await supabase.auth.getSession();
  if (!sessionData.session) {
    window.location.href = "/streaks/pages/login.html";
    return;
  }

  const userId = sessionData.session.user.id;

  // 2) Activity ID (unchanged)
  const activityId = getActivityIdFromUrl();
  if (!activityId) {
    showError("Missing activity id.");
    return;
  }

  // 3) Load activity (unchanged)
  const { data: activity, error: activityError } = await supabase
    .from("activities")
    .select("id, name")
    .eq("id", activityId)
    .maybeSingle();

  if (activityError || !activity) {
    console.error(activityError);
    showError("Activity not found.");
    return;
  }

  document.getElementById("activity-title").textContent = activity.name;

  // Fetch streak (unchanged, but could be moved to server if needed)
  const { data: userActivity } = await supabase
    .from("user_activities")
    .select("streak_count")
    .eq("user_id", userId)
    .eq("activity_id", activityId)
    .single();

  document.getElementById("activity-streak").innerHTML = `
    <img src="/streaks/assets/icons/flame.webp" class="app-icon sm" alt="Streak" />
    ${userActivity?.streak_count ?? 0}
  `;

  // 4) Load tasks (unchanged)
  const tasksList = document.getElementById("tasks-list");
  tasksList.innerHTML = "";

  const { data: tasks, error: tasksError } = await supabase
    .from("tasks")
    .select("id, title")
    .eq("activity_id", activityId)
    .order("created_at", { ascending: true });

  if (tasksError) {
    console.error(tasksError);
    showError("Failed to load tasks.");
    return;
  }

  if (!tasks || tasks.length === 0) {
    tasksList.innerHTML = "<li>No tasks yet</li>";
    return;
  }

  // 5) Load today's task states (unchanged)
  const taskIds = tasks.map(t => t.id);

  const { data: states, error: statesError } = await supabase
    .from("user_task_daily")
    .select("task_id, completed")
    .eq("user_id", userId)
    .eq("date", new Date().toISOString().slice(0, 10))  // TEMP: Keep for now, but we'll remove this in Phase 2
    .in("task_id", taskIds);

  if (statesError) {
    console.error(statesError);
    showError("Failed to load task state.");
    return;
  }

  const stateMap = new Map(
    (states || []).map(r => [r.task_id, r.completed === true])
  );

  // Load today's activity state (simplified - just check if editable)
  const { data: todayState } = await supabase
    .from("activity_history")
    .select("completed, frozen")
    .eq("user_id", userId)
    .eq("activity_id", activityId)
    .eq("date", new Date().toISOString().slice(0, 10))  // TEMP: Same as above
    .maybeSingle();

  const editingDisabled = todayState?.completed === true || todayState?.frozen === true;

  // Render tasks (simplified - remove complex completion logic)
  tasks.forEach(task => {
    const li = document.createElement("li");
    li.className = "task-row-activity";

    const isCompleted = stateMap.get(task.id) === true;
    if (isCompleted) {
      li.classList.add("is-completed-orange");
    }

    const pill = document.createElement("button");
    pill.className = "task-pill";
    pill.textContent = task.title;
    pill.setAttribute("aria-pressed", isCompleted ? "true" : "false");

    if (editingDisabled) {
      pill.disabled = true;
    }

    // TAP = toggle completion (simplified - just update DB and call server to check completion)
    pill.addEventListener("click", async () => {
      if (editingDisabled) return;

      const newCompleted = !li.classList.contains("is-completed-orange");
      li.classList.toggle("is-completed-orange", newCompleted);
      pill.setAttribute("aria-pressed", newCompleted ? "true" : "false");

      // Update task state
      const { error } = await supabase
        .from("user_task_daily")
        .upsert(
          {
            user_id: userId,
            task_id: task.id,
            date: new Date().toISOString().slice(0, 10),  // TEMP: Will be removed
            completed: newCompleted
          },
          { onConflict: "user_id,task_id,date" }
        );

      if (error) {
        console.error(error);
        li.classList.toggle("is-completed-orange", !newCompleted);
        return;
      }

      // NEW: Call server to handle completion and streak logic
      await supabase.rpc("complete_activity", { user_id_input: userId, activity_id_input: activityId });
    });

    // DELETE (unchanged)
    const deleteBtn = document.createElement("button");
    deleteBtn.className = "task-delete-bubble";
    deleteBtn.textContent = "Delete";

    if (!editingDisabled) {
      deleteBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        openConfirm(`Delete task "${task.title}"?`, async () => {
          const { error } = await supabase
            .from("tasks")
            .delete()
            .eq("id", task.id);

          if (!error) li.remove();
        });
      });
    } else {
      deleteBtn.disabled = true;
    }

    // LONG PRESS (unchanged)
    let pressTimer;
    pill.addEventListener("pointerdown", () => {
      pressTimer = setTimeout(() => {
        li.classList.add("show-delete");
      }, 450);
    });

    ["pointerup", "pointerleave", "pointercancel"].forEach(evt =>
      pill.addEventListener(evt, () => clearTimeout(pressTimer))
    );

    document.addEventListener("click", e => {
      if (!li.contains(e.target)) {
        li.classList.remove("show-delete");
      }
    });

    li.appendChild(pill);
    li.appendChild(deleteBtn);
    tasksList.appendChild(li);
  });

  // FREEZE BUTTON (simplified - just call server)
  const freezeBtn = document.getElementById("freeze-btn");

  const { data: items } = await supabase
    .from("user_items")
    .select("freeze_count")
    .eq("user_id", userId)
    .single();

  const freezeCount = items?.freeze_count ?? 0;
  freezeBtn.innerHTML = `
    <img src="/streaks/assets/icons/freeze.webp" class="app-icon sm" alt="Freeze" />
    Freeze (${freezeCount})
  `;

  const freezeDisabled = freezeCount === 0 || editingDisabled;

  if (freezeDisabled) {
    freezeBtn.disabled = true;
  } else {
    freezeBtn.addEventListener("click", async () => {
      const { error } = await supabase.rpc("freeze_activity_today", { user_id_input: userId, activity_id_input: activityId });

      if (error) {
        console.error("Freeze failed:", error);
        return;
      }

      // Reload to reflect changes
      window.location.reload();
    });
  }

  // DELETE ACTIVITY (unchanged)
  const deleteBtn = document.getElementById("delete-activity-btn");
  deleteBtn.addEventListener("click", () => {
    openConfirm("Are you sure you want to delete this activity?", async () => {
      const { error } = await supabase
        .from("activities")
        .delete()
        .eq("id", activityId);

      if (error) {
        console.error(error);
        alert("Failed to delete activity.");
        return;
      }

      window.location.href = "/streaks/pages/home.html";
    });
  });

  // ADD TASK (unchanged)
  const addTaskBtn = document.getElementById("add-task-btn");
  if (addTaskBtn) {
    if (editingDisabled) {
      addTaskBtn.disabled = true;
      addTaskBtn.style.opacity = "0.5";
      addTaskBtn.style.cursor = "not-allowed";
    } else {
      addTaskBtn.addEventListener("click", () => {
        window.location.href = `/streaks/pages/add-task.html?id=${activityId}`;
      });
    }
  }

  // STATS BUTTON (unchanged)
  document.getElementById("stats-btn").addEventListener("click", () => {
    window.location.href = `/streaks/pages/activity-stats.html?id=${activityId}`;
  });

  // NEW: Call reset on load (to ensure streaks are up-to-date)
  await supabase.rpc("reset_broken_streaks", { user_id_input: userId });
});