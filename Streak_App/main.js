


// Register Service Worker (PWA)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/streaks/sw.js");
  });
}




let confirmCallback = null;

function openConfirm(message, onConfirm) {
  document.getElementById("confirm-text").textContent = message;
  confirmCallback = onConfirm;
  document.getElementById("confirm-overlay").classList.remove("hidden");
}

function closeConfirm() {
  document.getElementById("confirm-overlay").classList.add("hidden");
  confirmCallback = null;
}





function showToast(message, duration = 2000) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");

  setTimeout(() => {
    toast.classList.add("hidden");
  }, duration);
}




/* for updateing the app without user refresh*/
async function checkForUpdates() {
  const currentVersion = localStorage.getItem('appVersion');
  try {
    const response = await fetch('/streaks/version.json', { cache: 'no-cache' }); // Updated path
    const data = await response.json();
    const latestVersion = data.version;

    if (currentVersion !== latestVersion) {
      localStorage.setItem('appVersion', latestVersion);
      console.log('App updated to version', latestVersion, '- Reloading...');
      window.location.reload(true);
    } else {
      console.log('App is up to date (version', currentVersion, ')');
    }
  } catch (error) {
    console.error('Failed to check for updates:', error);
  }
}

document.addEventListener('DOMContentLoaded', async () => {  // async for await support

  checkForUpdates();

  // Safely attach event handlers if elements exist
  const cancelBtn = document.getElementById("confirm-cancel");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", closeConfirm);
  }

  const yesBtn = document.getElementById("confirm-yes");
  if (yesBtn) {
    yesBtn.addEventListener("click", async () => {
      if (confirmCallback) await confirmCallback();
      closeConfirm();
    });
  }

  // Auth and streak reset logic (no change)
  const { data: sessionData } = await supabase.auth.getSession();
  if (sessionData.session) {
    const userId = sessionData.session.user.id;
    await supabase.rpc("reset_broken_streaks", { user_id_input: userId });
  }
});

