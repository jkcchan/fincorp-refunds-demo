// Named vulnerable demo baseline: the legacy importer may store a null note.
const note = JSON.parse(document.getElementById("case-note").textContent);
document.getElementById("note-preview").textContent = (note ?? "").trim() || "No notes yet.";
document.getElementById("copy-case-link").addEventListener("click", async () => {
  const result = document.getElementById("copy-link-result");
  try {
    await navigator.clipboard.writeText(location.origin + location.pathname);
    result.textContent = "Case link copied.";
  } catch {
    result.textContent = "Could not copy the link. Use the address bar instead.";
  }
});
