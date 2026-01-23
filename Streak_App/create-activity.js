import { supabase } from "./supabase.js";

const MAX_TASKS = 20;

function showError(message) {
  const el = document.getElementById("error");
  el.style.display = "block";
  el.textContent = message;
}

function clearError() {
  const el = document.getElementById("error");
  el.style.display = "none";
  el.textContent = "";
}

function createTaskInput(value = "") {
  const li = document.createElement("li");
  li.classList.add("task-row", "glass", "glass-dark-3");

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Task title";
  input.value = value;
  input.classList.add("task-input");

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.innerHTML = `
    <svg class="task-remove-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M18 6L6 18" />
      <path d="M6 6l12 12" />
    </svg>
  `;
  removeBtn.setAttribute("aria-label", "Remove task");

  removeBtn.classList.add("task-remove");

  removeBtn.addEventListener("click", () => {
    li.remove();
    updateSaveEnabled();
    updateAddTaskEnabled();
  });

  input.addEventListener("input", () => {
    updateSaveEnabled();
  });

  li.appendChild(input);
  li.appendChild(removeBtn);

  return li;
}

function getTaskValues() {
  const items = Array.from(document.querySelectorAll("#tasks-container li input"));
  return items.map(i => i.value.trim()).filter(Boolean);
}

function getTaskCount() {
  return document.querySelectorAll("#tasks-container li").length;
}

function updateAddTaskEnabled() {
  const addBtn = document.getElementById("add-task-btn");
  addBtn.disabled = getTaskCount() >= MAX_TASKS;
}

function updateSaveEnabled() {
  const title = document.getElementById("activity-title").value.trim();
  const tasks = getTaskValues();
  const saveBtn = document.getElementById("save-activity-btn");

  // Save enabled only if: title exists AND >=1 non-empty task
  saveBtn.disabled = !(title.length > 0 && tasks.length >= 1);
}

document.addEventListener("DOMContentLoaded", async () => {
  // 1) Auth guard
  const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
  if (sessionError) {
    console.error(sessionError);
    showError("Failed to read session.");
    return;
  }

  if (!sessionData.session) {
    window.location.href = "/streaks/pages/login.html";
    return;
  }

  clearError();

  // 2) Ensure at least ONE task input exists
  const tasksContainer = document.getElementById("tasks-container");
  tasksContainer.innerHTML = "";
  tasksContainer.appendChild(createTaskInput(""));

  // 3) Wire inputs
  document.getElementById("activity-title").addEventListener("input", () => {
    updateSaveEnabled();
  });

  document.getElementById("add-task-btn").addEventListener("click", () => {
    if (getTaskCount() >= MAX_TASKS) return;
    tasksContainer.appendChild(createTaskInput(""));
    updateAddTaskEnabled();
    updateSaveEnabled();
  });

  document.getElementById("cancel-btn").addEventListener("click", () => {
    window.location.href = "/streaks/pages/home.html";
  });

  // 4) Save (insert into DB)
    document.getElementById("save-activity-btn").addEventListener("click", async () => {
    clearError();

    const title = document.getElementById("activity-title").value.trim();
    const tasks = getTaskValues();

    if (!title) {
        showError("Please enter an activity title.");
        return;
    }

    if (tasks.length < 1) {
        showError("Please add at least one task.");
        return;
    }

    if (tasks.length > MAX_TASKS) {
        showError(`Maximum ${MAX_TASKS} tasks allowed.`);
        return;
    }

    // Disable button to prevent double submit
    const saveBtn = document.getElementById("save-activity-btn");
    saveBtn.disabled = true;

    try {
        // 1) Create activity
        const { data: activity, error: activityError } = await supabase
        .from("activities")
        .insert({
            name: title,
            created_by: sessionData.session.user.id
        })
        .select()
        .single();

        if (activityError) {
        console.error(activityError);
        showError("Failed to create activity.");
        saveBtn.disabled = false;
        return;
        }

        const activityId = activity.id;

        // 2) Link activity to user
        const { error: linkError } = await supabase
        .from("user_activities")
        .insert({
            user_id: sessionData.session.user.id,
            activity_id: activityId,
            streak_count: 0,
            last_resolved_date: null
        });

        if (linkError) {
        console.error(linkError);
        showError("Failed to link activity to user.");
        saveBtn.disabled = false;
        return;
        }

        // 3) Insert tasks
        const taskRows = tasks.map(taskTitle => ({
        activity_id: activityId,
        title: taskTitle
        }));

        const { error: tasksError } = await supabase
        .from("tasks")
        .insert(taskRows);

        if (tasksError) {
        console.error(tasksError);
        showError("Failed to create tasks.");
        saveBtn.disabled = false;
        return;
        }

        // 4) Redirect to Home
        window.location.href = "/streaks/pages/home.html";

    } catch (err) {
        console.error(err);
        showError("Unexpected error occurred.");
        saveBtn.disabled = false;
    }
    });


  // 5) Initial button states
  updateAddTaskEnabled();
  updateSaveEnabled();
});
