// Named vulnerable demo baseline: the legacy importer may store a null note.
const note = JSON.parse(document.getElementById("case-note").textContent);
document.getElementById("note-preview").textContent = (note ?? "").trim() || "No notes yet.";
document.getElementById("copy-case-link").addEventListener("click", async () => {
  const result = document.getElementById("copy-link-result");
  const url = location.origin + location.pathname;
  let copied = false;
  try {
    await navigator.clipboard.writeText(url);
    copied = true;
  } catch {
    const field = document.createElement("textarea");
    field.value = url;
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    try {
      copied = document.execCommand("copy");
    } catch {
      copied = false;
    } finally {
      field.remove();
    }
  }
  result.textContent = copied ? "Case link copied." : "Could not copy the link. Use the address bar instead.";
});
