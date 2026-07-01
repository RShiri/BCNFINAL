/* FC Barcelona 2025/26 &mdash; single-page dashboard (WC2026-style, one team).
   Reads window.DATA (from data.js) and renders every tab. Vanilla JS. */
(function () {
  "use strict";
  var D = window.DATA || {};
  var M = D.matches || [];
  var P = D.players || [];
  var T = D.totals || {};
  var SHOTS = D.playerShots || {};

  var ACC = "#3ddc97", BLUE = "#4ea1ff", WARN = "#ffb454", BAD = "#ff6b81",
      MUTED = "#93a0bd", TEXT = "#e8edf7", GREY = "#7e8bb0";
  var RES_COL = { W: ACC, D: WARN, L: BAD };

  // ---- helpers ----
  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function n1(x) { return (Math.round(x * 10) / 10).toFixed(1); }
  function n2(x) { return (Math.round(x * 100) / 100).toFixed(2); }
  function sgn(x) { return (x > 0 ? "+" : "") + x; }
  function pillClass(c) { return { "La Liga": "liga", "UCL": "ucl", "Copa": "copa", "Supercopa": "supercopa" }[c] || "liga"; }
  function pillLabel(c) { return { UCL: "UCL", Copa: "Copa del Rey", Supercopa: "Supercopa" }[c] || c; }
  function compPill(c) { return '<span class="pill pill-' + pillClass(c) + '">' + esc(pillLabel(c)) + "</span>"; }
  function badge(r) { return '<span class="badge badge-' + r + '">' + r + "</span>"; }
  function statCard(v, k, cls) { return '<div class="stat"><div class="v ' + (cls || "") + '">' + v + '</div><div class="k">' + k + "</div></div>"; }

  // ---- tooltip ----
  var TIP = $("#tooltip");
  function showTip(html, x, y) {
    TIP.innerHTML = html;
    TIP.style.left = Math.min(x + 14, window.innerWidth - 240) + "px";
    TIP.style.top = (y + 14) + "px";
    TIP.style.opacity = "1";
  }
  function hideTip() { TIP.style.opacity = "0"; }

  // ---- tab switching ----
  var tabs = document.querySelectorAll("nav.tabs button");
  tabs.forEach(function (b) {
    b.addEventListener("click", function () {
      tabs.forEach(function (x) { x.classList.remove("active"); });
      b.classList.add("active");
      document.querySelectorAll(".view").forEach(function (v) { v.classList.remove("active"); });
      $("#view-" + b.dataset.view).classList.add("active");
      window.scrollTo(0, 0);
    });
  });

  /* ======================= OVERVIEW ======================= */
  function renderOverview() {
    var s = "";
    s += statCard(T.p, "Played");
    s += statCard(T.w, "Wins", "accent");
    s += statCard(T.d, "Draws", "warn");
    s += statCard(T.l, "Losses", "bad");
    s += statCard(T.win_pct + "%", "Win Rate");
    s += statCard(T.ppg, "Points / Game", "accent");
    s += statCard(T.gf, "Goals For");
    s += statCard(T.ga, "Goals Against");
    s += statCard(sgn(T.gd), "Goal Diff", T.gd >= 0 ? "accent" : "bad");
    s += statCard(T.cs, "Clean Sheets", "blue");
    s += statCard(T.avg_xg, "Avg xG / Game", "warn");
    s += statCard(n1(T.xgf), "Total xG For", "accent");
    s += statCard(n1(T.xga), "Total xG Against", "bad");
    $("#overviewStats").innerHTML = s;

    var form = M.slice(-10).reverse();
    $("#overviewForm").innerHTML = '<span class="form-label">Recent form</span>' +
      form.map(function (m) { return '<span class="form-chip fc-' + m.result + '" title="' +
        esc(m.opp_name) + ' ' + m.bcn_goals + '-' + m.opp_goals + '">' + m.result + "</span>"; }).join("");

    // competition standings-style table
    var rows = (D.byComp || []).map(function (c) {
      return '<tr><td class="team">' + compPill(c.comp) + "</td><td>" + c.p + "</td><td>" + c.w +
        "</td><td>" + c.d + "</td><td>" + c.l + "</td><td>" + c.gf + "</td><td>" + c.ga +
        '</td><td>' + sgn(c.gd) + '</td><td class="pts">' + c.pts + "</td></tr>";
    }).join("");
    $("#compGrid").innerHTML =
      '<div class="group-card" style="grid-column:1/-1"><table><thead><tr>' +
      '<th class="team">Competition</th><th>P</th><th>W</th><th>D</th><th>L</th>' +
      '<th>GF</th><th>GA</th><th>GD</th><th>Pts</th></tr></thead><tbody>' + rows + "</tbody></table></div>";

    // timeline
    var maxMargin = Math.max.apply(null, M.map(function (m) { return Math.abs(m.bcn_goals - m.opp_goals); }).concat([1]));
    $("#timeline").innerHTML = '<div style="display:flex;align-items:flex-end;gap:3px;height:120px;padding:10px 4px;overflow-x:auto">' +
      M.map(function (m) {
        var margin = m.bcn_goals - m.opp_goals;
        var h = 14 + Math.abs(margin) / maxMargin * 90;
        return '<div class="tl-bar" data-mid="' + m.mid + '" style="flex:0 0 auto;width:9px;height:' + h +
          "px;border-radius:3px;background:" + RES_COL[m.result] + ';opacity:.85;cursor:pointer" title="' +
          esc(m.date + "  " + m.home + " " + m.home_score + "-" + m.away_score + " " + m.away) + '"></div>';
      }).join("") + "</div>";
    $("#timeline").querySelectorAll(".tl-bar").forEach(function (b) {
      b.addEventListener("click", function () { location.href = "match.html?id=" + b.dataset.mid; });
    });
  }

  /* ======================= MATCHES ======================= */
  function statRow(hv, av, label) {
    var h = parseFloat(hv), a = parseFloat(av), t = (h + a) || 1;
    var hp = Math.round(100 * h / t), ap = 100 - hp;
    return '<div class="stat-cmp"><div class="sc-val' + (h >= a ? " win" : "") + '">' + hv + '</div>' +
      '<div><div class="sc-label">' + label + '</div><div class="sc-bar">' +
      '<div class="sc-fill h" style="width:' + hp + '%"></div><div class="sc-fill a" style="width:' + ap + '%"></div>' +
      '</div></div><div class="sc-val' + (a > h ? " win" : "") + '">' + av + "</div></div>";
  }
  function statPanel(m) {
    var xl = m.xg_source === "Understat" ? "xG" : "xG (est.)";
    return '<div class="stat-panel"><div class="sp-head"><span>' + esc(m.home) + "</span><span>" + esc(m.away) + "</span></div>" +
      statRow(n2(m.xg_h), n2(m.xg_a), xl) +
      statRow(m.h_poss + "%", m.a_poss + "%", "Possession") +
      statRow(m.h_sot, m.a_sot, "Shots on Target") +
      statRow(m.h_shots, m.a_shots, "Shots") +
      statRow(m.h_bcc, m.a_bcc, "Big Chances") +
      statRow(m.h_pacc_pct + "%", m.a_pacc_pct + "%", "Pass Accuracy") +
      statRow(m.h_duel, m.a_duel, "Duels Won") +
      statRow(m.h_saves, m.a_saves, "Saves") +
      statRow(m.h_fouls, m.a_fouls, "Fouls") +
      '<div style="text-align:right;padding:6px 2px 2px"><a class="open-match" href="match.html?id=' + m.mid +
      '">Open Match Centre &rarr;</a></div></div>';
  }
  function logoImg(u) { return u ? '<img class="tlogo" src="' + u + '" alt="" loading="lazy">' : ""; }
  function bcnName(m, side) {
    var isBcn = (side === "home") === m.bcn_is_home;
    var nm = side === "home" ? m.home : m.away;
    var lg = side === "home" ? m.home_logo : m.away_logo;
    var span = '<span class="nm" style="' + (isBcn ? "color:" + ACC + ";font-weight:700" : "") + '">' + esc(nm) + "</span>";
    return side === "home" ? (span + logoImg(lg)) : (logoImg(lg) + span);
  }
  var COMP_COL = { "La Liga": BLUE, "UCL": ACC, "Copa": "#c57aff", "Supercopa": WARN };
  function renderMatches() {
    var q = ($("#mSearch").value || "").toLowerCase();
    var comp = $("#mComp").value;
    var list = M.filter(function (m) {
      if (comp !== "all" && m.comp !== comp) return false;
      if (q && (m.home + " " + m.away).toLowerCase().indexOf(q) < 0) return false;
      return true;
    }).slice().reverse();
    var host = $("#matchList");
    host.innerHTML = list.map(function (m) {
      return '<div class="db-match" data-mid="' + m.mid + '" style="box-shadow:inset 3px 0 0 ' + (COMP_COL[m.comp] || BLUE) + '">' +
        '<div class="db-match-head"><div class="db-date">' + esc(m.date) +
        ' <span class="chev nav">&#8599;</span></div>' +
        '<div class="side home">' + bcnName(m, "home") + "</div>" +
        '<div class="score">' + m.home_score + " &ndash; " + m.away_score + "</div>" +
        '<div class="side away">' + bcnName(m, "away") + "</div>" +
        '<div class="open-links">' + compPill(m.comp) + badge(m.result) + '</div></div></div>';
    }).join("");
    host.querySelectorAll(".db-match").forEach(function (row) {
      row.style.cursor = "pointer";
      row.querySelector(".db-match-head").addEventListener("click", function () {
        location.href = "match.html?id=" + row.dataset.mid;
      });
    });
  }
  function renderTeamTotals() {
    var g = M.length || 1;
    function agg(f) { return M.reduce(function (s, m) { return s + (f(m) || 0); }, 0); }
    var rows = [
      ["Goals for", T.gf, T.gf / g],
      ["Goals against", T.ga, T.ga / g],
      ["xG for", n1(T.xgf), T.xgf / g],
      ["xG against", n1(T.xga), T.xga / g],
      ["Shots", agg(function (m) { return m.bcn_is_home ? m.h_shots : m.a_shots; }), agg(function (m) { return m.bcn_is_home ? m.h_shots : m.a_shots; }) / g],
      ["Shots on target", agg(function (m) { return m.bcn_is_home ? m.h_sot : m.a_sot; }), agg(function (m) { return m.bcn_is_home ? m.h_sot : m.a_sot; }) / g],
      ["Big chances", agg(function (m) { return m.bcn_is_home ? m.h_bcc : m.a_bcc; }), agg(function (m) { return m.bcn_is_home ? m.h_bcc : m.a_bcc; }) / g],
      ["Duels won", agg(function (m) { return m.bcn_is_home ? m.h_duel : m.a_duel; }), agg(function (m) { return m.bcn_is_home ? m.h_duel : m.a_duel; }) / g],
      ["Saves", agg(function (m) { return m.bcn_is_home ? m.h_saves : m.a_saves; }), agg(function (m) { return m.bcn_is_home ? m.h_saves : m.a_saves; }) / g],
      ["Fouls", agg(function (m) { return m.bcn_is_home ? m.h_fouls : m.a_fouls; }), agg(function (m) { return m.bcn_is_home ? m.h_fouls : m.a_fouls; }) / g],
      ["Clean sheets", T.cs, T.cs / g]
    ];
    $("#teamTable").innerHTML = "<table><thead><tr><th class='team'>Metric</th><th>Total</th><th>Per game</th></tr></thead><tbody>" +
      rows.map(function (r) { return "<tr><td class='team'>" + r[0] + "</td><td>" + r[1] + "</td><td>" + n1(r[2]) + "</td></tr>"; }).join("") +
      "</tbody></table>";
  }
  $("#mSearch").addEventListener("input", renderMatches);
  $("#mComp").addEventListener("change", renderMatches);
  $("#mModeList").addEventListener("click", function () {
    $("#mModeList").classList.add("active"); $("#mModeTeam").classList.remove("active");
    $("#mListView").style.display = ""; $("#mTeamView").style.display = "none";
  });
  $("#mModeTeam").addEventListener("click", function () {
    $("#mModeTeam").classList.add("active"); $("#mModeList").classList.remove("active");
    $("#mListView").style.display = "none"; $("#mTeamView").style.display = ""; renderTeamTotals();
  });

  /* ======================= PLAYERS ======================= */
  var PCOLS = [
    { k: "name", t: "Player", team: true }, { k: "pos", t: "Pos" }, { k: "apps", t: "Apps" },
    { k: "mins", t: "Min" }, { k: "goals", t: "G" }, { k: "assists", t: "A" }, { k: "ga", t: "G+A" },
    { k: "shots", t: "Sh" }, { k: "sot", t: "SoT" }, { k: "keyp", t: "KeyP" }, { k: "xg", t: "xG" },
    { k: "xgd", t: "xG&plusmn;" }, { k: "rating", t: "Rt" }
  ];
  var pSort = { k: "ga", dir: -1 };
  function renderPlayers() {
    // pos filter options
    var posSel = $("#playerPos");
    if (posSel.options.length <= 1) {
      var poss = {}; P.forEach(function (p) { if (p.pos) poss[p.pos] = 1; });
      Object.keys(poss).sort().forEach(function (ps) {
        var o = document.createElement("option"); o.value = ps; o.textContent = ps; posSel.appendChild(o);
      });
    }
    // leaders strip
    function leader(metric, label) {
      var top = P.slice().sort(function (a, b) { return b[metric] - a[metric]; })[0];
      return top ? statCard(esc(top.name.split(" ").slice(-1)[0]) + ' <span style="font-size:14px;color:' + MUTED + '">' + top[metric] + "</span>", label, "accent") : "";
    }
    $("#playerLeaders").innerHTML = leader("goals", "Top Scorer") + leader("assists", "Most Assists") +
      leader("ga", "Goals + Assists") + leader("rating", "Best Rating") + leader("xg", "Highest xG");

    var q = ($("#playerSearch").value || "").toLowerCase();
    var pos = $("#playerPos").value;
    var rows = P.filter(function (p) {
      if (pos && p.pos !== pos) return false;
      if (q && p.name.toLowerCase().indexOf(q) < 0) return false;
      return p.apps > 0;
    });
    rows.sort(function (a, b) {
      var va = a[pSort.k], vb = b[pSort.k];
      if (typeof va === "string") return pSort.dir * va.localeCompare(vb);
      return pSort.dir * (va - vb);
    });
    var head = "<tr>" + PCOLS.map(function (c) {
      var arr = pSort.k === c.k ? (pSort.dir < 0 ? " &#9660;" : " &#9650;") : "";
      return "<th class='" + (c.team ? "team" : "") + "' data-k='" + c.k + "'>" + c.t + "<span class='arr'>" + arr + "</span></th>";
    }).join("") + "</tr>";
    var body = rows.map(function (p, i) {
      return "<tr>" + PCOLS.map(function (c) {
        if (c.team) return "<td class='team'><span class='pos'>" + (i + 1) + "</span> " + esc(p.name) + "</td>";
        var v = p[c.k];
        if (c.k === "xgd") return "<td><span class='delta " + (v >= 0 ? "pos" : "neg") + "'>" + sgn(v) + "</span></td>";
        if (c.k === "rating") return "<td>" + (v ? v.toFixed(2) : "&ndash;") + "</td>";
        return "<td>" + v + "</td>";
      }).join("") + "</tr>";
    }).join("");
    $("#playersTable").innerHTML = "<table class='rank players'><thead>" + head + "</thead><tbody>" + body + "</tbody></table>";
    $("#playersTable").querySelectorAll("th[data-k]").forEach(function (th) {
      th.addEventListener("click", function () {
        var k = th.dataset.k;
        if (pSort.k === k) pSort.dir *= -1; else { pSort.k = k; pSort.dir = (k === "name" || k === "pos") ? 1 : -1; }
        renderPlayers();
      });
    });

    // leaderboards
    var boards = [
      ["goals", "Goals"], ["assists", "Assists"], ["rating", "Average rating"],
      ["xg", "Expected goals"], ["keyp", "Key passes"], ["drib", "Take-ons won"]
    ];
    $("#playerBoards").innerHTML = boards.map(function (b) {
      var top = P.filter(function (p) { return p.apps > (b[0] === "rating" ? 3 : 0); })
        .slice().sort(function (x, y) { return y[b[0]] - x[b[0]]; }).slice(0, 8);
      return '<div class="lboard card"><h3>' + b[1] + "</h3>" + top.map(function (p) {
        var val = b[0] === "rating" ? p.rating.toFixed(2) : (b[0] === "xg" ? n2(p.xg) : p[b[0]]);
        return '<div class="fin-row"><div class="nm"><span>' + esc(p.name) + '</span></div>' +
          '<div class="fin-stat"><span class="lb-val">' + val + "</span></div></div>";
      }).join("") + "</div>";
    }).join("");
  }
  $("#playerSearch").addEventListener("input", renderPlayers);
  $("#playerPos").addEventListener("change", renderPlayers);
  document.querySelectorAll("#playerPresets .seg-btn").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll("#playerPresets .seg-btn").forEach(function (x) { x.classList.remove("active"); });
      b.classList.add("active");
      pSort = { k: b.dataset.preset, dir: -1 }; renderPlayers();
    });
  });

  /* ======================= SHARED SCATTER ======================= */
  function scatter(host, pts, cfg) {
    var W = 540, H = 420, padL = 46, padT = 16, padB = 44, padR = 14;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var xmax = Math.max.apply(null, pts.map(function (p) { return p.x; }).concat([cfg.min || 1])) * 1.08;
    var ymax = Math.max.apply(null, pts.map(function (p) { return p.y; }).concat([cfg.min || 1])) * 1.08;
    var lim = Math.max(xmax, ymax);
    if (cfg.diagonal) { xmax = ymax = lim; }
    function sx(v) { return padL + v / xmax * plotW; }
    function sy(v) { return padT + plotH - v / ymax * plotH; }
    var svg = ['<svg viewBox="0 0 ' + W + " " + H + '" width="100%" class="scatter-svg">'];
    var ticks = 5, i;
    for (i = 0; i <= ticks; i++) {
      var tx = xmax * i / ticks, X = sx(tx);
      svg.push('<line x1="' + X.toFixed(1) + '" y1="' + padT + '" x2="' + X.toFixed(1) + '" y2="' + (padT + plotH) + '" stroke="#222b44" stroke-width="0.6"/>');
      svg.push('<text x="' + X.toFixed(1) + '" y="' + (padT + plotH + 16) + '" fill="' + MUTED + '" font-size="10" text-anchor="middle">' + n1(tx) + "</text>");
      var ty = ymax * i / ticks, Y = sy(ty);
      svg.push('<line x1="' + padL + '" y1="' + Y.toFixed(1) + '" x2="' + (padL + plotW) + '" y2="' + Y.toFixed(1) + '" stroke="#222b44" stroke-width="0.6"/>');
      svg.push('<text x="' + (padL - 8) + '" y="' + (Y + 3).toFixed(1) + '" fill="' + MUTED + '" font-size="10" text-anchor="end">' + n1(ty) + "</text>");
    }
    if (cfg.diagonal) {
      svg.push('<line x1="' + sx(0) + '" y1="' + sy(0) + '" x2="' + sx(lim) + '" y2="' + sy(lim) + '" stroke="' + MUTED + '" stroke-width="1.2" stroke-dasharray="5 4"/>');
      svg.push('<text x="' + (sx(lim) - 4).toFixed(1) + '" y="' + (sy(lim) - 6).toFixed(1) + '" fill="' + MUTED + '" font-size="10" text-anchor="end">exactly deserved</text>');
    }
    pts.forEach(function (p, idx) {
      svg.push('<circle cx="' + sx(p.x).toFixed(1) + '" cy="' + sy(p.y).toFixed(1) + '" r="' + (p.r || 5) +
        '" fill="' + p.color + '" fill-opacity="0.82" stroke="#0b0f1a" stroke-width="0.7" data-i="' + idx + '"/>');
    });
    svg.push('<text x="' + (padL + plotW / 2) + '" y="' + (H - 6) + '" fill="' + TEXT + '" font-size="12.5" text-anchor="middle">' + cfg.xLabel + "</text>");
    svg.push('<text transform="translate(14,' + (padT + plotH / 2) + ') rotate(-90)" fill="' + TEXT + '" font-size="12.5" text-anchor="middle">' + cfg.yLabel + "</text>");
    svg.push("</svg>");
    host.innerHTML = svg.join("");
    var circles = host.querySelectorAll("circle[data-i]");
    circles.forEach(function (c) {
      c.addEventListener("mousemove", function (e) { showTip(pts[+c.dataset.i].tip, e.clientX, e.clientY); });
      c.addEventListener("mouseleave", hideTip);
    });
  }

  /* ======================= XG LAB ======================= */
  function renderXg() {
    var over = M.filter(function (m) { return m.bcn_goals > m.bcn_xg; }).length;
    $("#xgStats").innerHTML =
      statCard(T.gf, "Goals Scored", "accent") +
      statCard(n1(T.xgf), "Total xG For", "warn") +
      statCard(T.ga, "Goals Conceded", "bad") +
      statCard(n1(T.xga), "Total xG Against", "warn") +
      statCard(sgn(n1(T.gf - T.xgf)), "Finishing vs xG", (T.gf - T.xgf) >= 0 ? "accent" : "bad") +
      statCard(over + "/" + M.length, "Games Over xG", "blue");

    // small deterministic jitter separates matches that share the same goal count
    var seen = {};
    var pts = M.filter(function (m) { return m.bcn_xg > 0 || m.bcn_goals > 0; }).map(function (m) {
      var key = m.bcn_goals + "|" + Math.round(m.bcn_xg * 2);
      var k = (seen[key] = (seen[key] || 0) + 1);
      var jit = ((k % 2 ? 1 : -1) * Math.floor(k / 2)) * 0.11;
      return {
        x: m.bcn_xg, y: Math.max(0, m.bcn_goals + jit), color: RES_COL[m.result], r: 6,
        tip: "<div class='t-team'>" + esc(m.opp_name) + "</div><div class='t-line'>" + m.date +
          "</div><div class='t-line'>Goals <b style='color:" + ACC + "'>" + m.bcn_goals +
          "</b> &middot; xG <b style='color:" + WARN + "'>" + n2(m.bcn_xg) + "</b></div>"
      };
    });
    scatter($("#xgScatter"), pts, { diagonal: true, min: 1, xLabel: "xG created", yLabel: "Goals scored" });
    $("#xgScatterLegend").innerHTML =
      '<span class="cl-item"><i class="cl-sw" style="background:' + ACC + '"></i>Win</span>' +
      '<span class="cl-item"><i class="cl-sw" style="background:' + WARN + '"></i>Draw</span>' +
      '<span class="cl-item"><i class="cl-sw" style="background:' + BAD + '"></i>Loss</span>';

    // home / away xG bars
    function split(homeGame) {
      var ms = M.filter(function (m) { return m.bcn_is_home === homeGame; });
      var g = ms.length || 1;
      return { xgf: ms.reduce(function (s, m) { return s + m.bcn_xg; }, 0) / g, xga: ms.reduce(function (s, m) { return s + m.opp_xg; }, 0) / g };
    }
    var hh = split(true), aa = split(false);
    var mx = Math.max(hh.xgf, hh.xga, aa.xgf, aa.xga, 1);
    function haRow(lab, v, col) {
      return '<div class="ha-row"><span class="ha-lab">' + lab + '</span><div class="ha-track">' +
        '<div class="ha-fill" style="width:' + (v / mx * 100) + "%;background:" + col + '"></div></div><b>' + n2(v) + "</b></div>";
    }
    $("#homeAway").innerHTML =
      '<div style="font-size:12px;color:' + MUTED + ';margin:2px 0 4px">Home</div>' +
      haRow("xG for", hh.xgf, ACC) + haRow("xG against", hh.xga, BAD) +
      '<div style="font-size:12px;color:' + MUTED + ';margin:10px 0 4px">Away</div>' +
      haRow("xG for", aa.xgf, ACC) + haRow("xG against", aa.xga, BAD);
    $("#xgInsight").innerHTML = "Barcelona average <b>" + n2(hh.xgf) + " xG</b> at home vs <b>" + n2(aa.xgf) +
      "</b> away, conceding <b>" + n2(hh.xga) + "</b> / <b>" + n2(aa.xga) + "</b>.";

    // finishing lists
    function finList(host, arr) {
      host.innerHTML = arr.map(function (p) {
        return '<div class="fin-row"><div class="nm"><span>' + esc(p.name) + '</span></div>' +
          '<div class="fin-stat"><span class="sub">' + p.goals + "G &middot; " + n2(p.xg) + ' xG</span>' +
          '<span class="delta ' + (p.xgd >= 0 ? "pos" : "neg") + '">' + sgn(p.xgd) + "</span></div></div>";
      }).join("");
    }
    var shooters = P.filter(function (p) { return p.xg >= 0.5 || p.goals >= 1; });
    finList($("#finClinical"), shooters.slice().sort(function (a, b) { return b.xgd - a.xgd; }).slice(0, 8));
    finList($("#finWasteful"), shooters.slice().sort(function (a, b) { return a.xgd - b.xgd; }).slice(0, 8));
  }

  /* ======================= PLAYER LAB ======================= */
  var RADAR_METRICS = [
    { k: "goals", t: "Finishing", per90: true },
    { k: "ga", t: "G+A", per90: true },
    { k: "shots", t: "Shooting", per90: true },
    { k: "keyp", t: "Creativity", per90: true },
    { k: "drib", t: "Dribbling", per90: true },
    { k: "def", t: "Defending", per90: true },
    { k: "aerials", t: "Aerials", per90: true },
    { k: "rating", t: "Rating", per90: false }
  ];
  function per90(p, k) {
    if (k === "def") return p.mins ? (p.tackles + p.intc) / p.mins * 90 : 0;
    if (!p.mins) return 0;
    return p[k] / p.mins * 90;
  }
  function pctRank(pool, val, getter) {
    var vals = pool.map(getter);
    var below = vals.filter(function (v) { return v <= val; }).length;
    return Math.round(100 * below / vals.length);
  }
  function radar(host, players, pool) {
    var W = 360, H = 340, cx = W / 2, cy = H / 2 + 6, R = 118, N = RADAR_METRICS.length;
    var svg = ['<svg viewBox="0 0 ' + W + " " + H + '" width="100%" class="scatter-svg">'];
    var g, i;
    for (g = 1; g <= 4; g++) {
      var pts = [];
      for (i = 0; i < N; i++) {
        var a = -Math.PI / 2 + i / N * 2 * Math.PI, rr = R * g / 4;
        pts.push((cx + rr * Math.cos(a)).toFixed(1) + "," + (cy + rr * Math.sin(a)).toFixed(1));
      }
      svg.push('<polygon points="' + pts.join(" ") + '" fill="none" stroke="#26304d" stroke-width="0.8"/>');
    }
    for (i = 0; i < N; i++) {
      var a2 = -Math.PI / 2 + i / N * 2 * Math.PI;
      var lx = cx + (R + 16) * Math.cos(a2), ly = cy + (R + 16) * Math.sin(a2);
      var anc = Math.abs(Math.cos(a2)) < 0.3 ? "middle" : (Math.cos(a2) > 0 ? "start" : "end");
      svg.push('<line x1="' + cx + '" y1="' + cy + '" x2="' + (cx + R * Math.cos(a2)).toFixed(1) + '" y2="' + (cy + R * Math.sin(a2)).toFixed(1) + '" stroke="#26304d" stroke-width="0.8"/>');
      svg.push('<text x="' + lx.toFixed(1) + '" y="' + (ly + 3).toFixed(1) + '" fill="' + MUTED + '" font-size="10.5" text-anchor="' + anc + '">' + RADAR_METRICS[i].t + "</text>");
    }
    var cols = [ACC, BLUE];
    players.forEach(function (p, pi) {
      var pts = [];
      for (i = 0; i < N; i++) {
        var mtc = RADAR_METRICS[i];
        var val = mtc.per90 ? per90(p, mtc.k) : p[mtc.k];
        var pct = pctRank(pool, val, function (q) { return mtc.per90 ? per90(q, mtc.k) : q[mtc.k]; }) / 100;
        var a3 = -Math.PI / 2 + i / N * 2 * Math.PI, rr2 = R * Math.max(0.04, pct);
        pts.push((cx + rr2 * Math.cos(a3)).toFixed(1) + "," + (cy + rr2 * Math.sin(a3)).toFixed(1));
      }
      svg.push('<polygon points="' + pts.join(" ") + '" fill="' + cols[pi] + '" fill-opacity="0.18" stroke="' + cols[pi] + '" stroke-width="2"/>');
    });
    svg.push("</svg>");
    host.innerHTML = svg.join("");
    $("#plRadarLegend").innerHTML = players.map(function (p, pi) {
      return '<span class="cl-item"><i class="cl-sw" style="background:' + cols[pi] + '"></i>' + esc(p.name) + "</span>";
    }).join("");
  }
  function pitchShotMap(host, shots, title) {
    var W = 560, H = 360, pad = 8;
    var pw = W - pad * 2, ph = H - pad * 2;
    // horizontal pitch, attacking right. build_shot_df x:0-120, y:0-80
    function px(x) { return pad + Math.max(0, Math.min(120, x)) / 120 * pw; }
    function py(y) { return pad + Math.max(0, Math.min(80, y)) / 80 * ph; }
    var s = ['<svg viewBox="0 0 ' + W + " " + H + '" width="100%" class="scatter-svg">'];
    s.push('<rect x="' + pad + '" y="' + pad + '" width="' + pw + '" height="' + ph + '" fill="#101a2e" stroke="#26304d"/>');
    s.push('<line x1="' + px(60) + '" y1="' + pad + '" x2="' + px(60) + '" y2="' + (pad + ph) + '" stroke="#26304d"/>');
    s.push('<circle cx="' + px(60) + '" cy="' + py(40) + '" r="' + (9.15 / 120 * pw) + '" fill="none" stroke="#26304d"/>');
    // right box + left box
    s.push('<rect x="' + px(102) + '" y="' + py(18) + '" width="' + (px(120) - px(102)) + '" height="' + (py(62) - py(18)) + '" fill="none" stroke="#26304d"/>');
    s.push('<rect x="' + px(0) + '" y="' + py(18) + '" width="' + (px(18) - px(0)) + '" height="' + (py(62) - py(18)) + '" fill="none" stroke="#26304d"/>');
    shots.forEach(function (sh, i) {
      var col = sh.goal ? "#ff3d8b" : (sh.ot ? BLUE : "#7e8bb0");
      var r = 3 + Math.sqrt(sh.xg) * 12;
      s.push('<circle cx="' + px(sh.x).toFixed(1) + '" cy="' + py(sh.y).toFixed(1) + '" r="' + r.toFixed(1) +
        '" fill="' + col + '" fill-opacity="0.7" stroke="#0b0f1a" stroke-width="0.8" data-i="' + i + '"/>');
    });
    s.push("</svg>");
    host.innerHTML = s.join("");
    host.querySelectorAll("circle[data-i]").forEach(function (c) {
      var sh = shots[+c.dataset.i];
      c.addEventListener("mousemove", function (e) {
        showTip("<div class='t-team'>" + (sh.goal ? "Goal" : sh.ot ? "On target" : "Off target") + "</div>" +
          "<div class='t-line'>vs " + esc(sh.opp) + " &middot; " + sh.min + "'</div><div class='t-line'>xG " + n2(sh.xg) +
          " &middot; " + esc(sh.sit || "") + "</div>", e.clientX, e.clientY);
      });
      c.addEventListener("mouseleave", hideTip);
    });
  }
  function playerByName(nm) { return P.filter(function (p) { return p.name === nm; })[0]; }
  function plShots(nm) {
    var arr = (SHOTS[nm] || []).slice();
    var f = $("#plShotFilter").value;
    if (f === "goal") arr = arr.filter(function (s) { return s.goal; });
    else if (f === "ot") arr = arr.filter(function (s) { return s.ot; });
    else if (f === "big") arr = arr.filter(function (s) { return s.big; });
    return arr;
  }
  function renderPlayerLab() {
    var main = $("#plMain").value, cmp = $("#plCompare").value;
    var p = playerByName(main); if (!p) return;
    var s = "";
    s += statCard(p.apps, "Apps");
    s += statCard(p.mins, "Minutes");
    s += statCard(p.goals, "Goals", "accent");
    s += statCard(p.assists, "Assists", "blue");
    s += statCard(n2(p.xg), "xG", "warn");
    s += statCard(sgn(p.xgd), "xG&plusmn;", p.xgd >= 0 ? "accent" : "bad");
    s += statCard(p.shots, "Shots");
    s += statCard(p.keyp, "Key Passes");
    s += statCard(p.rating ? p.rating.toFixed(2) : "&ndash;", "Avg Rating", "accent");
    $("#plStats").innerHTML = s;

    var shots = plShots(main);
    $("#plMapTitle").innerHTML = esc(main) + " &mdash; " + shots.length + " shots";
    pitchShotMap($("#plMap"), shots);

    var pool = P.filter(function (q) { return q.mins >= 120; });
    var pc = cmp ? playerByName(cmp) : null;
    var players = [p]; if (pc) players.push(pc);
    radar($("#plRadar"), players, pool.length ? pool : P);

    // side-by-side head-to-head comparison
    var cmpCard = $("#plCompareCard");
    if (pc) {
      $("#plCompareTitle").innerHTML = esc(main) + " vs " + esc(cmp);
      var metrics = [["shots", "Shots"], ["drib", "Take-ons won"], ["tackles", "Tackles"],
                     ["passes", "Passes"], ["prog", "Progressive passes"]];
      $("#plCompareBody").innerHTML = metrics.map(function (mt) {
        var a = p[mt[0]] || 0, b = pc[mt[0]] || 0, t = (a + b) || 1, ap = Math.round(100 * a / t);
        return '<div class="stat-cmp"><div class="sc-val' + (a >= b ? " win" : "") + '">' + a + '</div>' +
          '<div><div class="sc-label">' + mt[1] + '</div><div class="sc-bar">' +
          '<div class="sc-fill h" style="width:' + ap + '%"></div>' +
          '<div class="sc-fill a" style="width:' + (100 - ap) + '%"></div></div></div>' +
          '<div class="sc-val' + (b > a ? " win" : "") + '">' + b + "</div></div>";
      }).join("");
      cmpCard.style.display = "";
    } else {
      cmpCard.style.display = "none";
    }
  }
  function initPlayerLab() {
    var opts = P.filter(function (p) { return p.apps > 0; })
      .slice().sort(function (a, b) { return b.ga - a.ga; });
    var mainSel = $("#plMain"), cmpSel = $("#plCompare");
    opts.forEach(function (p) {
      var o = document.createElement("option"); o.value = p.name; o.textContent = p.name; mainSel.appendChild(o);
      var o2 = document.createElement("option"); o2.value = p.name; o2.textContent = p.name; cmpSel.appendChild(o2);
    });
    // default to top scorer with shots
    var withShots = opts.filter(function (p) { return (SHOTS[p.name] || []).length; });
    if (withShots[0]) mainSel.value = withShots[0].name;
    [mainSel, cmpSel, $("#plShotFilter")].forEach(function (e) { e.addEventListener("change", renderPlayerLab); });
  }

  /* ======================= SHOT MAPS GRID ======================= */
  function renderShotGrid() {
    var q = ($("#sSearch").value || "").toLowerCase();
    var comp = $("#sComp").value;
    var list = M.filter(function (m) {
      if (comp !== "all" && m.comp !== comp) return false;
      if (q && (m.home + " " + m.away).toLowerCase().indexOf(q) < 0) return false;
      return true;
    }).slice().reverse();
    $("#shotGrid").innerHTML = list.map(function (m) {
      return '<a class="group-card" href="match.html?id=' + m.mid + '" style="display:block;text-decoration:none;color:inherit;box-shadow:inset 3px 0 0 ' + RES_COL[m.result] + '">' +
        '<div style="padding:14px 16px">' +
        '<div style="display:flex;justify-content:space-between;font-size:11px;color:' + MUTED + ';margin-bottom:8px">' +
        '<span>' + esc(m.date) + "</span>" + compPill(m.comp) + "</div>" +
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px">' +
        bcnName(m, "home") + '<b style="font-size:19px">' + m.home_score + " &ndash; " + m.away_score + "</b>" + bcnName(m, "away") + "</div>" +
        '<div style="margin-top:8px;font-size:11px;color:' + MUTED + '">xG ' + n2(m.xg_h) + " &ndash; " + n2(m.xg_a) +
        ' &middot; <span style="color:' + ACC + '">Open Match Centre &rarr;</span></div></div></a>';
    }).join("");
  }
  $("#sSearch").addEventListener("input", renderShotGrid);
  $("#sComp").addEventListener("change", renderShotGrid);

  /* ======================= DATA ======================= */
  function renderData() {
    var cards = [
      ["Matches", M.length + " games", "Full WhoScored match feeds cached as JSON"],
      ["Players", P.length + " players", "Season-aggregated player stats & ratings"],
      ["Shots", Object.keys(SHOTS).reduce(function (s, k) { return s + SHOTS[k].length; }, 0) + " shots", "Every shot with model xG, for the Player Lab"],
      ["Competitions", (D.byComp || []).length + " comps", "La Liga &middot; Champions League &middot; Copa del Rey &middot; Supercopa"]
    ];
    $("#dataGrid").innerHTML = cards.map(function (c) {
      return '<div class="data-card"><div class="dc-name">' + c[0] + '</div><div class="dc-meta">' + c[2] +
        '</div><div class="dc-dl">' + c[1] + "</div></div>";
    }).join("");
  }

  /* ======================= INIT ======================= */
  renderOverview();
  renderMatches();
  renderPlayers();
  renderXg();
  initPlayerLab();
  renderPlayerLab();
  renderShotGrid();
  renderData();
  $("#footerNote").innerHTML = "FC Barcelona 2025/26 &middot; " + M.length + " matches &middot; WhoScored + Understat data &middot; updated " + esc(D.updated || "");
})();
