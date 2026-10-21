// Named vulnerable demo baseline: the legacy importer may store a null note.
const note = JSON.parse(document.getElementById("case-note").textContent);
document.getElementById("note-preview").textContent = note.trim() || "No notes yet.";
