(() => {
  function cookie(name) {
    return document.cookie.split("; ").find(item => item.startsWith(name + "="))?.split("=")[1] || "";
  }
  function report(message, stack) {
    const match = location.pathname.match(/\/cases\/(RF-[A-Z0-9-]+)\//);
    fetch("/telemetry/", {
      method: "POST", credentials: "same-origin",
      headers: {"Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(cookie("csrftoken"))},
      body: JSON.stringify({
        message: String(message).slice(0, 400), stack: String(stack || "").slice(0, 6000),
        route: location.pathname, case_reference: match?.[1] || "",
        correlation_id: crypto.randomUUID().replaceAll("-", ""),
      }),
    }).catch(() => {});
  }
  window.addEventListener("error", event => report(event.message, event.error?.stack || ""));
  window.addEventListener("unhandledrejection", event => report(event.reason?.message || event.reason, event.reason?.stack || ""));
})();
