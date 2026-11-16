(function () {
  var KEY = "wf-ga4-consent";

  function readConsent() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function writeConsent(value) {
    try { localStorage.setItem(KEY, value); } catch (e) {}
  }

  function apply(value) {
    writeConsent(value);
    if (typeof gtag === "function") {
      gtag("consent", "update", {
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        analytics_storage: value === "granted" ? "granted" : "denied"
      });
    }
    if (value === "granted" && typeof window.wfLoadGA4 === "function") window.wfLoadGA4();
    var el = document.getElementById("consent-banner");
    if (el) el.remove();
  }

  function openBanner() {
    var old = document.getElementById("consent-banner");
    if (old) old.remove();
    var el = document.createElement("div");
    el.id = "consent-banner";
    el.className = "consent";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-labelledby", "consent-title");
    el.setAttribute("aria-describedby", "consent-text");
    el.innerHTML = '<p id="consent-title"><strong>Analytics choice</strong></p>'
      + '<p id="consent-text">Which Frost loads Google Analytics 4 only after you allow it. Cloudflare Web Analytics does not use cookies. <a href="/privacy/#cookies">Privacy</a></p>'
      + '<p class="btnrow"><button type="button" class="btn" id="consent-accept">Allow analytics</button> '
      + '<button type="button" class="btn alt" id="consent-deny">No thanks</button></p>';
    document.body.appendChild(el);
    document.getElementById("consent-accept").addEventListener("click", function () { apply("granted"); });
    document.getElementById("consent-deny").addEventListener("click", function () { apply("denied"); });
    document.getElementById("consent-accept").focus();
  }

  document.addEventListener("click", function (e) {
    var n = e.target;
    if (!n || n.id !== "cookie-settings") return;
    e.preventDefault();
    openBanner();
  });

  var saved = readConsent();
  if (saved === "granted" || saved === "denied") apply(saved);
  else openBanner();
})();
