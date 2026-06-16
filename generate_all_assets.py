import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplsoccer import Pitch, VerticalPitch
import plotly.graph_objects as go
import plotly.offline as pyo
import json
import logging
import math
from concurrent.futures import ProcessPoolExecutor

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(_PROJECT_ROOT, "assets")
PNG_DIR = os.path.join(ASSETS_DIR, "png")
HTML_DIR = os.path.join(ASSETS_DIR, "html")
DATA_DIR = os.path.join(ASSETS_DIR, "data")

os.makedirs(PNG_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

SCALE_X = 1.2
SCALE_Y = 0.80

def _ws_to_sb_x(ws_x):
    if ws_x <= 50: return ws_x * (60.0 / 50.0)
    elif ws_x <= 89: return 60.0 + (ws_x - 50) * (48.0 / 39.0)
    else: return 108.0 + (ws_x - 89) * (12.0 / 11.0)

def _estimate_xg(x_sb, y_sb, is_penalty, is_big_chance, body_part):
    if is_penalty: return 0.76
    dx = 120.0 - x_sb
    dy = 40.0 - y_sb
    distance = max(np.sqrt(dx**2 + dy**2), 0.5)
    angle = np.arctan2(4.0, distance)
    xg = (angle / (np.pi / 2)) * (1 / (1 + distance / 30))
    if body_part == "Header": xg *= 0.4
    if is_big_chance:
        xg = max(0.35, xg * 3.5)
        xg = min(0.65, xg)
    if distance > 18: xg *= (18 / distance)**2
    return round(min(max(xg, 0.01), 0.95), 3)

def _player_name(match_data, player_id):
    for side in ("home", "away"):
        for p in match_data.get(side, {}).get("players", []):
            if p.get("playerId") == player_id:
                name = p.get("name", "")
                parts = name.split()
                if len(parts) >= 2: return parts[-1]
                return name
    return str(player_id)

def generate_passmaps(match_id, match_data, team_side, team_name, color_val):
    tid = match_data.get(team_side, {}).get("teamId")
    if not tid: return
    
    rows = []
    for ev in match_data.get("events", []):
        if ev.get("type", {}).get("displayName") != "Pass": continue
        if ev.get("teamId") != tid: continue
        outcome = ev.get("outcomeType", {}).get("displayName", "")
        end_x_raw, end_y_raw = ev.get("endX"), ev.get("endY")
        if end_x_raw is None or end_y_raw is None: continue

        is_prog = is_final_third = is_final_half = is_into_box = False
        x = ev.get("x", 0) * SCALE_X
        y = 80 - ev.get("y", 0) * SCALE_Y
        end_x = float(end_x_raw) * SCALE_X
        end_y = 80 - float(end_y_raw) * SCALE_Y

        # Progressive: significant forward gain depending on starting zone
        if x >= 48:
            if x < 60 and (end_x - x) >= 30: is_prog = True
            elif 60 <= x <= 90 and (end_x - x) >= 15: is_prog = True
            elif x > 90 and (end_x - x) >= 10: is_prog = True

        # Final third entry: pass crosses into the final third from outside it
        if x < 80 and end_x >= 80: is_final_third = True

        # Final half: pass ends in the opponent's half (x >= 60)
        if end_x >= 60: is_final_half = True

        # Into box: pass ends inside the penalty area (SB: x 102-120, y 18-62)
        if end_x >= 102 and 18 <= end_y <= 62: is_into_box = True

        rows.append({
            "x": x, "y": y,
            "end_x": end_x, "end_y": end_y,
            "pass_outcome": "Complete" if outcome == "Successful" else "Incomplete",
            "is_progressive": is_prog,
            "is_final_third": is_final_third,
            "is_final_half": is_final_half,
            "is_into_box": is_into_box,
        })

    df = pd.DataFrame(rows)
    if df.empty: return

    def draw_map(sub_df, title_prefix, out_name):
        pitch = Pitch(pitch_type="statsbomb", pitch_color="#2d572c", line_color="white")
        fig, ax = pitch.draw(figsize=(10, 6.5))
        fail = sub_df[sub_df["pass_outcome"] == "Incomplete"]
        succ = sub_df[sub_df["pass_outcome"] == "Complete"]

        if not fail.empty:
            pitch.lines(fail["x"], fail["y"], fail["end_x"], fail["end_y"],
                        lw=2.5, transparent=True, comet=True, ax=ax, color="#d62728", alpha=0.5)
        if not succ.empty:
            pitch.lines(succ["x"], succ["y"], succ["end_x"], succ["end_y"],
                        lw=2.5, transparent=True, comet=True, ax=ax, color="#2ca02c", alpha=0.6)

        n_succ = len(succ)
        n_tot = len(sub_df)
        ax.set_title(f"{team_name} - {title_prefix} ({n_succ}/{n_tot} Successful)",
                     fontsize=14, fontweight="bold", color="white", pad=10)
        fig.patch.set_facecolor('#0d0d1a')
        plt.tight_layout()
        plt.savefig(os.path.join(PNG_DIR, out_name), dpi=100, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)

    draw_map(df, "All Passes", f"{match_id}_{team_side}_total_passes.png")

    fh_df = df[df["is_final_half"]]
    draw_map(fh_df, "Final Half Passes", f"{match_id}_{team_side}_final_half.png")

    ft_df = df[df["is_final_third"]]
    draw_map(ft_df, "Final Third Entries", f"{match_id}_{team_side}_final_third.png")

    box_df = df[df["is_into_box"]]
    draw_map(box_df, "Passes Into the Box", f"{match_id}_{team_side}_into_box.png")

    prog_df = df[df["is_progressive"]]
    draw_map(prog_df, "Progressive Passes", f"{match_id}_{team_side}_progressive_passes.png")

def generate_passnetwork(match_id, match_data, team_side, team_name, color_val):
    tid = match_data.get(team_side, {}).get("teamId")
    if not tid: return
    
    team_block = match_data.get(team_side, {})
    jersey_map = {}
    for player in team_block.get("players", []):
        pid = player.get("playerId")
        jn = player.get("shirtNo")
        if pid is not None and jn is not None:
            jersey_map[pid] = int(jn)
            
    events_raw = match_data.get("events", [])
    
    # Process ALL events globally to trace exact chronology and opponents
    rows = []
    for ev in events_raw:
        pid = ev.get("playerId")
        if pid is None: continue
        rows.append({
            "id": ev.get("id"),
            "event_id": ev.get("eventId", 0),
            "team_id": ev.get("teamId"),
            "type": ev.get("type", {}).get("displayName", ""),
            "player_id": pid,
            "x": ev.get("x", 0) * SCALE_X,
            "y": 80 - ev.get("y", 0) * SCALE_Y,
            "minute": ev.get("minute", 0),
            "second": ev.get("second", 0),
            "outcome": ev.get("outcomeType", {}).get("displayName", ""),
        })
    df = pd.DataFrame(rows)
    if df.empty: return

    df["newsecond"] = 60 * df["minute"] + df["second"]
    df = df.sort_values(by=["newsecond", "event_id"]).reset_index(drop=True)
    
    # Calculate substitution limit for this specific team
    sub_df = df.loc[(df["team_id"] == tid) & (df["type"].isin(["SubstitutionOff", "SubstitutionOn"]))]
    first_sub = sub_df["newsecond"].min()
    if pd.isna(first_sub) or first_sub <= (60 * 45): first_sub = 60 * 45
    
    # Working dataset is pre-substitution
    df_pre_sub = df.loc[df["newsecond"] < first_sub].copy()
    
    # Identify Pass Recipients chronologically
    recipients = []
    for i in range(len(df_pre_sub)):
        row = df_pre_sub.iloc[i]
        rec = None
        if row["team_id"] == tid and row["type"] == "Pass" and row["outcome"] == "Successful":
            for j in range(i + 1, len(df_pre_sub)):
                next_ev = df_pre_sub.iloc[j]
                if next_ev["team_id"] != tid:
                    break # Opponent action breaks the sequence
                if next_ev["outcome"] == "Successful":
                    rec = next_ev["player_id"]
                    break
        recipients.append(rec)
        
    df_pre_sub["recipient"] = recipients
    completions = df_pre_sub.loc[(df_pre_sub["team_id"] == tid) & (df_pre_sub["type"] == "Pass") & (df_pre_sub["outcome"] == "Successful")].dropna(subset=["recipient"]).copy()
    if completions.empty: return
    
    # Node Positions: Average of ALL successful actions by the player (Passes made AND received etc)
    successful_actions = df_pre_sub.loc[(df_pre_sub["team_id"] == tid) & (df_pre_sub["outcome"] == "Successful")].copy()
    average_locs_and_count = successful_actions.groupby("player_id").agg({"x": ["mean"], "y": ["mean", "count"]})
    average_locs_and_count.columns = ["x", "y", "count"]
    
    completions["passer"] = completions["player_id"]
    
    passes_between = completions.groupby(["passer", "recipient"]).id.count().reset_index()
    passes_between.rename(columns={"id": "pass_count"}, inplace=True)
    
    passes_between = passes_between.merge(average_locs_and_count, left_on="passer", right_index=True)
    passes_between = passes_between.merge(average_locs_and_count, left_on="recipient", right_index=True, suffixes=["", "_end"])
    
    threshold = 3
    passes_between = passes_between.loc[passes_between["pass_count"] >= threshold]

    pitch = VerticalPitch(pitch_type="statsbomb", pitch_color="#ffffff", line_color="#c7c7c7")
    fig, ax = pitch.draw(figsize=(10, 10))
    fig.patch.set_facecolor('#ffffff')
    
    min_passes = passes_between["pass_count"].min() if not passes_between.empty else 1
    max_passes = passes_between["pass_count"].max() if not passes_between.empty else 1
    rng = max_passes - min_passes if max_passes != min_passes else 1
    
    MIN_LW = 1.5
    MAX_LW = 8.0
    
    def pass_line_template(ax, x, y, end_x, end_y, line_color, lw=4, alpha=0.85):
        ax.annotate(
            "",
            xy=(end_y, end_x),
            xytext=(y, x),
            zorder=1,
            arrowprops=dict(
                arrowstyle="-|>", linewidth=lw, color=line_color, alpha=alpha, connectionstyle="arc3,rad=0.15"
            ),
        )

    def pass_line_template_shrink(ax, x, y, end_x, end_y, line_color, dist_delta=4.0, lw=4, alpha=0.85):
        dist  = math.hypot(end_x - x, end_y - y)
        angle = math.atan2(end_y - y, end_x - x)
        upd_x = x + (dist - dist_delta) * math.cos(angle)
        upd_y = y + (dist - dist_delta) * math.sin(angle)
        pass_line_template(ax, x, y, upd_x, upd_y, line_color=line_color, lw=lw, alpha=alpha)

    for _, row in passes_between.iterrows():
        lw = MIN_LW + (row["pass_count"] - min_passes) / rng * (MAX_LW - MIN_LW) if rng > 0 else 2.5
        alpha_val = 0.4 + (row["pass_count"] - min_passes) / rng * 0.6 if rng > 0 else 0.7
        pass_line_template_shrink(
            ax, row["x"], row["y"], row["x_end"], row["y_end"],
            color_val, dist_delta=4.0, lw=lw, alpha=alpha_val
        )
        
    node_sizes = 200 + (average_locs_and_count["count"] * 25)
    pitch.scatter(average_locs_and_count.x, average_locs_and_count.y, s=node_sizes, color="white", edgecolors=color_val, linewidth=2.5, alpha=1, ax=ax, zorder=2)

    for player_id, row in average_locs_and_count.iterrows():
        try:
            jn = jersey_map.get(int(player_id), "")
        except:
            jn = ""
        if not jn:
            pname = _player_name(match_data, player_id)
            jn = "".join([n[0] for n in pname.split()[:2]]).upper()
        pitch.annotate(str(jn), xy=(row['x'], row['y']), c=color_val, va='center', ha='center', size=11, weight='bold', ax=ax, zorder=3)

    # Line-thickness legend
    from matplotlib.lines import Line2D
    if not passes_between.empty:
        q33 = int(np.percentile(passes_between["pass_count"], 33))
        q67 = int(np.percentile(passes_between["pass_count"], 67))
        lw_thin   = MIN_LW
        lw_mid    = MIN_LW + (MAX_LW - MIN_LW) * 0.5
        lw_thick  = MAX_LW
        lw_legend_handles = [
            Line2D([0], [0], color=color_val, lw=lw_thin,  alpha=0.85,
                   label=f"Low  (≤{q33} passes)"),
            Line2D([0], [0], color=color_val, lw=lw_mid,   alpha=0.85,
                   label=f"Med  ({q33+1}–{q67} passes)"),
            Line2D([0], [0], color=color_val, lw=lw_thick, alpha=0.85,
                   label=f"High (>{q67} passes)"),
        ]
        leg = ax.legend(
            handles=lw_legend_handles,
            title="Line thickness = Pass volume",
            loc="lower right",
            fontsize=8,
            title_fontsize=8.5,
            framealpha=0.75,
            facecolor="#eeeeee",
            edgecolor="#bbbbbb",
        )
        leg.get_title().set_color("#333333")

    ax.set_title(f"{team_name} - Passing Network (11 Starters, Min Pass: {threshold})", fontsize=18, fontweight="bold", color="#333333", pad=15)
    plt.tight_layout()
    plt.savefig(os.path.join(PNG_DIR, f"{match_id}_{team_side}_passnetwork.png"), dpi=100, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Projects.shotmap_whoscored import build_shot_df, draw_combined_shotmap, rescale_xg_to_total

def generate_shotmap(match_id, match_data, home_name, away_name):
    try:
        df_home = build_shot_df(match_data, home_name)
        df_away = build_shot_df(match_data, away_name)
        base_lbl = f"{home_name} vs {away_name} (Match ID: {match_id})"

        # WhoScored geometry xG map (no rescaling)
        out_ws = os.path.join(HTML_DIR, f"{match_id}_shotmap_ws.html")
        draw_combined_shotmap(df_home, home_name, df_away, away_name, out_ws,
                              match_label=base_lbl + " | WhoScored xG")

        # Understat-rescaled xG map (if data present)
        us_xg_home, us_xg_away = None, None
        if "understat" in match_data and match_data["understat"].get("xG"):
            us_xg_home = float(match_data["understat"]["xG"].get("h", 0))
            us_xg_away = float(match_data["understat"]["xG"].get("a", 0))

        df_home_us = rescale_xg_to_total(df_home, us_xg_home)
        df_away_us = rescale_xg_to_total(df_away, us_xg_away)
        out_us = os.path.join(HTML_DIR, f"{match_id}_shotmap_us.html")
        draw_combined_shotmap(df_home_us, home_name, df_away_us, away_name, out_us,
                              match_label=base_lbl + " | Understat xG",
                              xg_override_home=us_xg_home, xg_override_away=us_xg_away)
    except Exception as e:
        print(f"Error drawing shotmap for {match_id}: {e}")

def generate_dribblemap(match_id, match_data, team_side, team_name):
    tid = match_data.get(team_side, {}).get("teamId")
    if not tid: return

    rows = []
    for ev in match_data.get("events", []):
        if ev.get("type", {}).get("displayName") != "TakeOn": continue
        if ev.get("teamId") != tid: continue
        outcome = ev.get("outcomeType", {}).get("displayName", "")
        x = ev.get("x", 0) * SCALE_X
        y = 80 - ev.get("y", 0) * SCALE_Y
        rows.append({
            "x": x, "y": y,
            "outcome": "Successful" if outcome == "Successful" else "Unsuccessful",
            "player": _player_name(match_data, ev.get("playerId")),
            "minute": ev.get("minute", 0),
        })

    df = pd.DataFrame(rows)
    if df.empty: return

    # Static PNG (for embedding in page)
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#2d572c", line_color="white")
    fig_s, ax_s = pitch.draw(figsize=(10, 6.5))
    fail = df[df["outcome"] == "Unsuccessful"]
    succ = df[df["outcome"] == "Successful"]
    if not fail.empty:
        pitch.scatter(fail["x"], fail["y"], color="#d62728", edgecolors="black", marker="x", s=80, ax=ax_s, label="Unsuccessful", zorder=2)
    if not succ.empty:
        pitch.scatter(succ["x"], succ["y"], color="#2ca02c", edgecolors="black", marker="o", s=80, ax=ax_s, label="Successful", zorder=3)
    ax_s.legend(loc="lower left", framealpha=0.8, fontsize=10)
    ax_s.set_title(f"{team_name} - Take-Ons", fontsize=14, fontweight="bold", color="white", pad=10)
    fig_s.patch.set_facecolor('#0d0d1a')
    plt.tight_layout()
    plt.savefig(os.path.join(PNG_DIR, f"{match_id}_{team_side}_dribbles.png"), dpi=100, facecolor=fig_s.get_facecolor(), edgecolor='none')
    plt.close(fig_s)

    # Interactive Plotly HTML with player filter
    players = sorted(df["player"].unique())
    color_map = {"Successful": "#2ca02c", "Unsuccessful": "#d62728"}

    # Pitch outline shapes (StatsBomb full pitch)
    L, W = 120, 80
    pitch_shapes = [
        dict(type="rect", x0=0, y0=0, x1=L, y1=W, line=dict(color="white", width=2), fillcolor="rgba(0,0,0,0)"),
        dict(type="line", x0=60, y0=0, x1=60, y1=W, line=dict(color="white", width=1.5)),
        dict(type="circle", x0=51,y0=31,x1=69,y1=49, line=dict(color="white",width=1.5)),
        dict(type="rect", x0=0, y0=18, x1=18, y1=62, line=dict(color="white", width=1.5), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=0, y0=30, x1=6, y1=50, line=dict(color="white", width=1), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=102, y0=18, x1=L, y1=62, line=dict(color="white", width=1.5), fillcolor="rgba(0,0,0,0)"),
        dict(type="rect", x0=114, y0=30, x1=L, y1=50, line=dict(color="white", width=1), fillcolor="rgba(0,0,0,0)"),
    ]

    import json as _json
    shots_data = _json.dumps([
        {"x": r["x"], "y": r["y"], "player": r["player"],
         "outcome": r["outcome"], "minute": int(r["minute"])}
        for _, r in df.iterrows()
    ])

    # Unique token so home & away maps embedded on one page don't collide.
    tok = f"{match_id}_{team_side}_drib"

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
body{{margin:0;background:#0d0d1a;color:#e0e0e0;font-family:system-ui}}
.ctrl-{tok}{{display:flex;gap:12px;align-items:center;padding:10px 16px;background:#111128;flex-wrap:wrap}}
.ctrl-{tok} label{{font-size:11px;color:#8888bb;letter-spacing:1px;text-transform:uppercase}}
.ctrl-{tok} select{{background:#0d0d1a;color:#e0e0e0;border:1px solid #4444aa;border-radius:6px;padding:5px 10px;font-size:12px}}
#chart_{tok}{{width:100%;height:520px}}
</style></head><body>
<div class="ctrl-{tok}">
  <label>Player:</label>
  <select id="psel_{tok}" onchange="window.redraw_{tok}()">
    <option value="all">All Players</option>
    {"".join(f'<option value="{p}">{p}</option>' for p in players)}
  </select>
  <label style="margin-left:12px">Outcome:</label>
  <select id="osel_{tok}" onchange="window.redraw_{tok}()">
    <option value="all">All</option>
    <option value="Successful">Successful</option>
    <option value="Unsuccessful">Unsuccessful</option>
  </select>
  <span id="summary_{tok}" style="margin-left:auto;font-size:12px;color:#9999cc"></span>
</div>
<div id="chart_{tok}"></div>
<script>
(function(){{
  var data = {shots_data};
  var shapes = {_json.dumps(pitch_shapes)};

  window.redraw_{tok} = function() {{
    var p = document.getElementById("psel_{tok}").value;
    var o = document.getElementById("osel_{tok}").value;
    var filtered = data.filter(function(d){{
      return (p==="all" || d.player===p) && (o==="all" || d.outcome===o);
    }});
    var succ = filtered.filter(function(d){{return d.outcome==="Successful";}});
    var fail = filtered.filter(function(d){{return d.outcome==="Unsuccessful";}});
    document.getElementById("summary_{tok}").textContent =
      succ.length+" successful · "+fail.length+" unsuccessful";

    var traces = [
      {{
        x: succ.map(function(d){{return d.x;}}), y: succ.map(function(d){{return d.y;}}),
        mode:"markers", name:"Successful",
        marker:{{size:12, color:"#2ca02c", symbol:"circle", line:{{width:1.5, color:"white"}}}},
        hovertext: succ.map(function(d){{return "<b>"+d.player+"</b> ("+d.minute+"')<br>Successful Take-On";}}),
        hoverinfo:"text"
      }},
      {{
        x: fail.map(function(d){{return d.x;}}), y: fail.map(function(d){{return d.y;}}),
        mode:"markers", name:"Unsuccessful",
        marker:{{size:12, color:"#d62728", symbol:"x", line:{{width:2, color:"#ff6666"}}}},
        hovertext: fail.map(function(d){{return "<b>"+d.player+"</b> ("+d.minute+"')<br>Unsuccessful Take-On";}}),
        hoverinfo:"text"
      }}
    ];

    var layout = {{
      paper_bgcolor:"#0d0d1a", plot_bgcolor:"#2d572c",
      font:{{color:"white"}},
      shapes: shapes,
      xaxis:{{range:[-2,122], showgrid:false, zeroline:false, showticklabels:false, fixedrange:true}},
      yaxis:{{range:[-2,82], showgrid:false, zeroline:false, showticklabels:false, fixedrange:true}},
      showlegend:true,
      legend:{{x:0.5, y:-0.04, xanchor:"center", orientation:"h", font:{{color:"white",size:12}}, bgcolor:"rgba(0,0,0,0)"}},
      margin:{{l:10,r:10,t:14,b:10}},
    }};

    Plotly.newPlot("chart_{tok}", traces, layout, {{responsive:true, displayModeBar:false}});
  }};

  window.redraw_{tok}();
}})();
</script></body></html>"""

    out_path = os.path.join(HTML_DIR, f"{match_id}_{team_side}_dribbles.html")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Saved interactive dribbles: {os.path.basename(out_path)}")

def process_match(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            match_data = json.load(f)
        
        filename = os.path.basename(filepath)
        match_id = int(filename.split("_")[1]) if "_" in filename else match_data.get("matchId")
        
        home_name = match_data.get("home", {}).get("name", "Home")
        away_name = match_data.get("away", {}).get("name", "Away")
        
        generate_passmaps(match_id, match_data, "home", home_name, "#a50044")
        generate_passmaps(match_id, match_data, "away", away_name, "#004d98")
        
        generate_passnetwork(match_id, match_data, "home", home_name, "#a50044")
        generate_passnetwork(match_id, match_data, "away", away_name, "#004d98")
        
        generate_shotmap(match_id, match_data, home_name, away_name)
        
        generate_dribblemap(match_id, match_data, "home", home_name)
        generate_dribblemap(match_id, match_data, "away", away_name)
        
        return True
    except Exception as e:
        print(f"Error on {os.path.basename(filepath)}: {e}")
        return False

if __name__ == "__main__":
    import os as _os
    filter_ids = _os.environ.get("PIPELINE_MATCH_IDS", "").strip()
    all_files  = glob.glob(os.path.join(DATA_DIR, "match_*_cache.json"))

    if filter_ids:
        id_set = set(filter_ids.split(","))
        files  = [f for f in all_files
                  if os.path.basename(f).split("_")[1] in id_set]
        print(f"Generating assets for {len(files)} specific match(es)...")
    else:
        files = all_files
        print(f"Generating assets for {len(files)} matches...")

    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_match, files))
    print(f"Generation complete! Success: {sum(results)} / {len(results)}")
