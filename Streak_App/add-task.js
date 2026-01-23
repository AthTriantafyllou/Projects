import { supabase } from "./supabase.js";

/* -------------------- */
/* Helpers              */
/* -------------------- */

function showError(msg) {
  const el = document.getElementById("error");
  el.style.display = "block";
  el.textContent = msg;
}

function getActivityId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

/* -------------------- */
/* Main                 */
/* -------------------- */

document.addEventListener("DOMContentLoaded", async () => {
  const activityId = getActivityId();
  if (!activityId) {
    showError("Missing activity id.");
    return;
  }

  // Auth guard
  const { data: sessionData } = await supabase.auth.getSession();
  if (!sessionData.session) {
    window.location.href = "/streaks/pages/login.html";
    return;
  }

  const userId = sessionData.session.user.id;

  /* -------------------- */
  /* Ownership check      */
  /* -------------------- */

  const { data: activity, error: activityError } = await supabase
    .from("activities")
    .select("id")
    .eq("id", activityId)
    .eq("created_by", userId)
    .single();

  if (activityError || !activity) {
    showError("You do not have permission to add tasks to this activity.");
    return;
  }

  /* -------------------- */
  /* Task count limit     */
  /* -------------------- */

  const { count, error: countError } = await supabase
    .from("tasks")
    .select("*", { count: "exact", head: true })
    .eq("activity_id", activityId);

  if (countError) {
    showError("Failed to check task limit.");
    return;
  }

  if (count >= 20) {
    showError("You cannot have more than 20 tasks in an activity.");
    return;
  }

  /* -------------------- */
  /* Save task            */
  /* -------------------- */

  document.getElementById("save-btn").addEventListener("click", async () => {
    const title = document.getElementById("task-title").value.trim();

    if (!title) {
      showError("Task title cannot be empty.");
      return;
    }

    const { error } = await supabase
      .from("tasks")
      .insert({
        activity_id: activityId,
        title
      });

    if (error) {
      console.error(error);
      showError("Failed to create task.");
      return;
    }

    // Success → back to activity
    window.location.href =
      `/streaks/pages/activity.html?id=${activityId}`;
  });

  /* -------------------- */
  /* Cancel               */
  /* -------------------- */

  document.getElementById("cancel-btn").addEventListener("click", () => {
    window.location.href =
      `/streaks/pages/activity.html?id=${activityId}`;
  });
});
