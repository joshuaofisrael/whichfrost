(function () {
  var s = document.getElementById("contact-status");
  if (s && /[?&]sent=1/.test(location.search)) {
    s.hidden = false;
    s.className = "form-status ok";
    s.textContent = "Thanks, your message was sent. We will reply by email.";
  }
  var months = document.querySelectorAll("[data-month]");
  if (months.length) {
    var m = String(new Date().getMonth() + 1);
    for (var i = 0; i < months.length; i++) {
      if (months[i].getAttribute("data-month") === m) months[i].classList.add("is-now");
    }
    var label = document.getElementById("now-label");
    if (label) {
      var names = ["January","February","March","April","May","June","July","August","September","October","November","December"];
      label.textContent = "This month is " + names[m - 1] + ". That block is marked below.";
    }
  }
  var q = document.getElementById("city-q");
  var out = document.getElementById("city-results");
  if (!q || !out) return;
  var cities = [];
  fetch("/assets/cities.json")
    .then(function (r) { return r.json(); })
    .then(function (data) { cities = data; })
    .catch(function () { out.innerHTML = "<li>City search did not load. Use the state list below.</li>"; });
  function show() {
    var v = q.value.trim().toLowerCase();
    out.innerHTML = "";
    if (v.length < 2) return;
    var n = 0;
    for (var i = 0; i < cities.length; i++) {
      var c = cities[i];
      if ((c.n + " " + c.s + " " + c.a).toLowerCase().indexOf(v) === -1) continue;
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = c.u;
      a.textContent = c.n + ", " + c.s;
      li.appendChild(a);
      if (c.z) {
        var sp = document.createElement("span");
        sp.textContent = " · zone " + c.z;
        li.appendChild(sp);
      }
      out.appendChild(li);
      if (++n >= 12) break;
    }
    if (!n) {
      var li2 = document.createElement("li");
      li2.textContent = "No city on this site matches. It may be under 100,000 people, or it has no NOAA frost station within 50 miles.";
      out.appendChild(li2);
    }
  }
  q.addEventListener("input", show);
})();
