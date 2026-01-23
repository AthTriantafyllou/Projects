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

function formatDateLocal(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function daysBetween(a, b) {
  const ms = 1000 * 60 * 60 * 24;
  return Math.floor((b - a) / ms) + 1;
}

function monthName(date) {
  return date.toLocaleString("en-US", {
    month: "long",
    year: "numeric"
  });
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
  /* Activity info        */
  /* -------------------- */

  const { data: activity } = await supabase
    .from("activities")
    .select("name, created_at")
    .eq("id", activityId)
    .single();

  document.getElementById("activity-name").textContent =
    `Stats — ${activity.name}`;

  /* -------------------- */
  /* History              */
  /* -------------------- */

  const { data: history } = await supabase
    .from("activity_history")
    .select("date, completed, frozen")
    .eq("user_id", userId)
    .eq("activity_id", activityId);

  /* -------------------- */
  /* Numeric stats        */
  /* -------------------- */

  const createdAt = new Date(activity.created_at);
  createdAt.setHours(0, 0, 0, 0);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const totalDays = daysBetween(createdAt, today);
  const completedDays = history.filter(h => h.completed).length;
  const frozenDays = history.filter(h => h.frozen).length;
  const failedDays = Math.max(totalDays - completedDays - frozenDays, 0);

  document.getElementById("numeric-stats").innerHTML = `
    <p>Total days since created: ${totalDays}</p>
    <p>Completed days: ${completedDays}</p>
    <p>Frozen days: ${frozenDays}</p>
    <p>Failed days: ${failedDays}</p>
  `;

  /* -------------------- */
  /* Calendar setup       */
  /* -------------------- */

  // Map date → state
  const historyMap = new Map();
  history.forEach(h => {
    if (h.completed) historyMap.set(h.date, "completed");
    else if (h.frozen) historyMap.set(h.date, "frozen");
  });

  // Build valid months list
  const months = [];
  const startMonth = new Date(createdAt.getFullYear(), createdAt.getMonth(), 1);
  const endMonth = new Date(today.getFullYear(), today.getMonth(), 1);

  let cursor = new Date(startMonth);
  while (cursor <= endMonth) {
    months.push(new Date(cursor));
    cursor.setMonth(cursor.getMonth() + 1);
  }

  let currentMonthIndex = months.length - 1; // start at current month

  const calendarEl = document.getElementById("calendar");

  function renderMonth(monthDate) {
    calendarEl.innerHTML = "";

    const monthLabel = document.getElementById("month-label");
    if (monthLabel) {
      monthLabel.textContent = monthDate.toLocaleString("en-US", { month: "long" }).toUpperCase();
    }


    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();

    const monthContainer = document.createElement("div");
    monthContainer.className = "calendar-month";

    const title = document.createElement("h3");
    title.textContent = monthName(monthDate);
    monthContainer.appendChild(title);

    // Weekdays
    const header = document.createElement("div");
    header.className = "calendar-weekdays";
    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach(d => {
      const el = document.createElement("div");
      el.textContent = d;
      header.appendChild(el);
    });
    monthContainer.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "calendar-grid";

    const firstOfMonth = new Date(year, month, 1);
    let offset = firstOfMonth.getDay() - 1;
    if (offset < 0) offset = 6;

    for (let i = 0; i < offset; i++) {
      grid.appendChild(document.createElement("div"));
    }

    const lastDay = new Date(year, month + 1, 0).getDate();

    for (let d = 1; d <= lastDay; d++) {
      const day = new Date(year, month, d);
      day.setHours(0, 0, 0, 0);

      const dayEl = document.createElement("div");
      dayEl.className = "calendar-day";
      dayEl.textContent = d;

      const dateStr = formatDateLocal(day);

      // State logic
      if (day >= createdAt && day <= today) {
        if (historyMap.has(dateStr)) {
          dayEl.classList.add(
            historyMap.get(dateStr) === "completed"
              ? "day-completed"
              : "day-frozen"
          );
        } else if (dateStr !== formatDateLocal(today)) {
          dayEl.classList.add("day-failed");
        }
      }

      if (dateStr === formatDateLocal(today)) {
        dayEl.classList.add("day-today-outline");
      }

      grid.appendChild(dayEl);
    }

    monthContainer.appendChild(grid);
    calendarEl.appendChild(monthContainer);

    // Button states
    document.getElementById("prev-month").disabled = currentMonthIndex === 0;
    document.getElementById("next-month").disabled =
      currentMonthIndex === months.length - 1;
  }

  // Initial render
  renderMonth(months[currentMonthIndex]);

  /* -------------------- */
  /* Month navigation     */
  /* -------------------- */

  document.getElementById("prev-month").addEventListener("click", () => {
    if (currentMonthIndex > 0) {
      currentMonthIndex--;
      renderMonth(months[currentMonthIndex]);
    }
  });

  document.getElementById("next-month").addEventListener("click", () => {
    if (currentMonthIndex < months.length - 1) {
      currentMonthIndex++;
      renderMonth(months[currentMonthIndex]);
    }
  });

  /* -------------------- */
  /* Back button          */
  /* -------------------- */

  document.getElementById("back-btn").addEventListener("click", () => {
    window.location.href = `/streaks/pages/activity.html?id=${activityId}`;
  });
});
