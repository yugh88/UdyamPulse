// Sets the theme before first paint (external file so a strict CSP needs no inline script).
(function () {
  try {
    var t = localStorage.getItem("up_theme");
    if (t !== "light" && t !== "dark") t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.dataset.theme = t;
  } catch (e) {
    document.documentElement.dataset.theme = "light";
  }
})();
