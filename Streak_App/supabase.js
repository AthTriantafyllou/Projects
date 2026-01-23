import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm";

export const supabase = createClient(
  "https://qplinjzvztfkdwbrengn.supabase.co",
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFwbGluanp2enRma2R3YnJlbmduIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU5MDE1ODMsImV4cCI6MjA4MTQ3NzU4M30.qswdgIbIFIi4-tvhE8GwTfwp7sFDP12aDjkydLI8Ouc"
);


// Add to global scope for non-module scripts
window.supabase = supabase;