import { supabase } from "./supabase.js";

//notification
const VAPID_PUBLIC_KEY = "BPjT-QxTO6UgaCl8_q40FCKwUvNrRWjPGH6RR8unQp5OYp6YqxFA0aRI2ibdT5Miph5GksQd0xHtmEy7adUU25g";


function showError(message) {
  const el = document.getElementById("error");
  el.style.display = "block";
  el.textContent = message;
}


// NOTIFICAIONS //
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");

  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

async function getSWRegistration() {
  return await navigator.serviceWorker.ready;
}


document.addEventListener("DOMContentLoaded", async () => {
  // 1) Auth guard
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

  const user = sessionData.session.user;

  // 2) Show email
  document.getElementById("user-email").textContent = user.email;

  // 3) Logout
  document.getElementById("logout-btn").addEventListener("click", async () => {
    await supabase.auth.signOut();
    window.location.href = "/streaks/pages/login.html";
  });

  // 4) delete account

    document.getElementById("delete-account-btn").addEventListener("click", () => {

      openConfirm(
        "This will permanently delete your account and all data. This cannot be undone. Are you sure?",
        async () => {

          const { error } = await supabase.rpc("delete_my_account");

          if (error) {
            console.error("Delete account failed:", error);
            alert("Failed to delete account. Check console.");
            return;
          }

          // Log out locally (auth user already deleted)
          await supabase.auth.signOut();

          window.location.href = "/streaks/pages/login.html";
        }
      );

    });


  // 5) notifications

  const notifBtn = document.getElementById("notif-btn");

  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    notifBtn.textContent = "NOTIFICATIONS NOT SUPPORTED";
    notifBtn.disabled = true;
    return;
  }

  async function updateNotifButton() {
    const reg = await getSWRegistration();
    const sub = await reg.pushManager.getSubscription();

    notifBtn.textContent = sub
      ? "DISABLE NOTIFICATIONS"
      : "ENABLE NOTIFICATIONS";
  }

  await updateNotifButton();

  notifBtn.addEventListener("click", async () => {
    const reg = await getSWRegistration();
    const existingSub = await reg.pushManager.getSubscription();

    if (existingSub) {
      // 🔕 Disable
      await existingSub.unsubscribe();

      await supabase
        .from("push_subscriptions")
        .delete()
        .eq("endpoint", existingSub.endpoint);

      await updateNotifButton();
      return;
    }

    // 🔔 Enable
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      alert("Notifications permission denied.");
      return;
    }

    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
    });

    const { endpoint, keys } = subscription.toJSON();

    const { error } = await supabase
      .from("push_subscriptions")
      .upsert({
        user_id: user.id,
        endpoint,
        p256dh: keys.p256dh,
        auth: keys.auth,
        user_agent: navigator.userAgent
      });

    if (error) {
      console.error(error);
      alert("Failed to save notification settings.");
      return;
    }

    await updateNotifButton();
  });

  // Add this: Display current app version
  const currentVersion = localStorage.getItem('appVersion') || 'Unknown';
  document.getElementById("app-version").textContent = currentVersion;







});
