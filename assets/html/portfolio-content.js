/* Portfolio content for the Barca xG Lab: the "About this project" panel (EN + HE) and the
   Hebrew UI dictionary, both consumed by the shared brand kit
   (https://rshiri.github.io/assets/brand/brand.js, loaded just before this file).
   RS_I18N swaps exact text nodes; HE_BLOCKS gives whole explanatory paragraphs a Hebrew
   version (data-he-html) so mixed bold/plain sentences read as one natural sentence.
   Team names, player names and numbers are data and stay as they are. */
(function () {
  window.RS_ABOUT = {
    en: {
      title: "Barça xG Lab",
      intro: "A one-club analytics site for FC Barcelona: every match since 2022/23 with its expected-goals (xG) story, a player lab, and an interactive Match Centre for each game — built from WhoScored event data and an xG model trained for this portfolio.",
      sections: [
        { h: "What you are looking at",
          p: "Seven tabs over one dataset. <b>Overview</b> is the season record (results, form, record by competition, results timeline). <b>Matches</b> lists every fixture with its xG and a full head-to-head stat line. <b>Players</b> ranks the squad (goals, assists, rating, xG, key passes, take-ons). <b>xG Lab</b> asks whether Barcelona finish as well as their chances say they should. <b>Player Lab</b> is a one-player deep dive with action maps and a percentile radar, and can compare two players. <b>Shot Maps</b> opens the Match Centre for any game. The season switch in the header filters every tab; <b>All seasons</b> pools them." },
        { h: "Data and volumes",
          p: "The build currently holds <b>179 Barcelona matches across five seasons</b>: 2022/23, 2023/24 and 2024/25 (38 La Liga games each), 2025/26 (57 games: 38 La Liga, 12 Champions League, 5 Copa del Rey, 2 Supercopa) and the 2026/27 season in progress. 2025/26 comes from this repo's own WhoScored match-centre caches (the full event stream). Every other season is imported from Ram's <b>XLALIGA</b> La Liga dataset, which is derived from the same WhoScored feed; so those seasons are league-only and every played Barcelona fixture in XLALIGA appears here. The builder cross-checks each XLALIGA fixture and score against the site on every build." },
        { h: "Pipeline",
          p: "<code>build_dashboard.py</code> loads the WhoScored caches, tags each match with its season (July to June), folds in XLALIGA's seasons through <code>xlaliga_history.py</code> (a raw cache always wins over XLALIGA for the same fixture), aggregates team and player numbers, and writes <code>data.js</code>, <code>player_events.js</code> and one Match Centre file per game into <code>assets/html</code>. That folder is published as-is to GitHub Pages. The pages are static HTML, CSS and JavaScript: every chart is SVG drawn in the browser, with no images and no server." },
        { h: "The xG model",
          p: "Expected goals price each shot from 0 to 1 by how often such a shot is scored. The shared <code>xg_core</code> model is a <b>logistic regression</b> on 14 shot features: distance and log-distance, the angle the goal mouth opens up and its interaction with distance, header or other body part, big chance, free kick, corner, set piece, fast break and whether the shot was assisted. It was trained on <b>11,968 shots</b> (2025/26 La Liga plus the 2026 World Cup) without resampling, then calibrated on out-of-fold predictions so total xG equals total goals (out-of-fold ROC AUC 0.81). Penalties are a fixed value (about 0.78). An optional LightGBM blend exists in the artifact; this site uses the dependency-free logistic path. Seasons imported from XLALIGA carry XLALIGA's own per-shot xG." },
        { h: "xA and the Player Lab",
          p: "Expected assists (xA) come from a separate <b>pass-level model</b> in <code>xg_core</code>: for every pass it estimates the probability that the pass becomes an assist, trained on about 363,000 passes, so a player is credited for good passes even when the shot is missed. The Player Lab's radar shows <b>percentile ranks per 90 minutes</b> among squad players with 120+ minutes; its maps plot shots on a half pitch (sized by xG) and take-ons, tackles and passes on the full pitch." },
        { h: "Reading the Match Centre",
          p: "Each match page has the scoreboard and goal timeline, a stat comparison, an <b>xG momentum</b> chart (cumulative xG by minute, a step per shot), a clickable shot map and goal-mouth view, a pass explorer with filters (progressive, crosses, through balls, final third, 5-minute windows), dribbles, a pass network and average positions you can scrub through time, the line-ups with ratings, an all-goals map and animated goal replays you can export as PNG or video." },
        { h: "Limits",
          p: "XLALIGA keeps the on-ball attacking actions (shots, passes, dribbles, saves, goals, line-ups) but not the defensive event stream, so for the imported seasons the Player Lab's tackle map is empty (season tackle totals still come from XLALIGA's aggregates) and only La Liga is covered. xG is a model: it ignores defender positions and shot speed, so single games can disagree with other providers. Competition labels for 2025/26 are inferred from the feed, with a small manual override list checked against XLALIGA's 38 league fixtures." }
      ]
    },
    he: {
      title: "Barça xG Lab",
      intro: "אתר אנליטיקה שמוקדש כולו ל-FC ברצלונה: כל משחק מאז 2022/23 עם סיפור ה-xG (שערים צפויים) שלו, מעבדת שחקנים ו-Match Centre אינטראקטיבי לכל משחק. האתר בנוי על נתוני אירועים של WhoScored ועל מודל xG שאומן במיוחד לפורטפוליו הזה.",
      sections: [
        { h: "מה רואים כאן",
          p: "שבע לשוניות מעל מאגר נתונים אחד. <b>סקירה</b> מציגה את מאזן העונה: תוצאות, כושר, מאזן לפי מסגרת וציר תוצאות. <b>משחקים</b> מפרטת כל משחק עם ה-xG שלו ושורת סטטיסטיקה מלאה מול היריבה. <b>שחקנים</b> מדרגת את הסגל לפי שערים, בישולים, ציון, xG, מסירות מפתח ועקיפות. <b>מעבדת xG</b> בודקת אם ברצלונה מסיימת מצבים כמו שאיכות ההזדמנויות שלה מנבאת. <b>מעבדת השחקן</b> צוללת לשחקן אחד עם מפות פעולה ותרשים אחוזונים, ואפשר להשוות בה בין שני שחקנים. <b>מפות בעיטות</b> פותחת את ה-Match Centre של כל משחק. בורר העונה בכותרת מסנן את כל הלשוניות, ו<b>כל העונות</b> מאחד אותן." },
        { h: "הנתונים והיקפם",
          p: "הבנייה הנוכחית כוללת <b>179 משחקים של ברצלונה בחמש עונות</b>: 2022/23, 2023/24 ו-2024/25 (38 משחקי ליגה בכל אחת), 2025/26 (57 משחקים: 38 בליגה, 12 בליגת האלופות, 5 בגביע המלך ו-2 בסופרקופה) ועונת 2026/27 שנמצאת בעיצומה. עונת 2025/26 מגיעה מקובצי ה-match centre של WhoScored שנשמרו בריפו הזה (זרם האירועים המלא). כל שאר העונות מיובאות ממאגר הלה ליגה <b>XLALIGA</b> של רם, שנגזר מאותו פיד של WhoScored. לכן העונות האלה כוללות ליגה בלבד, וכל משחק של ברצלונה ששוחק ומופיע ב-XLALIGA מופיע גם כאן. בכל בנייה הבונה מצליב כל משחק ותוצאה מול XLALIGA." },
        { h: "ה-Pipeline",
          p: "הסקריפט <code>build_dashboard.py</code> טוען את קובצי WhoScored, משייך כל משחק לעונה שלו (מיולי עד יוני), מוסיף את העונות של XLALIGA דרך <code>xlaliga_history.py</code> (כשאותו משחק קיים בשני המקורות, הקובץ הגולמי גובר), מחשב נתוני קבוצה ושחקנים, וכותב לתיקייה <code>assets/html</code> את <code>data.js</code>, את <code>player_events.js</code> וקובץ Match Centre לכל משחק. התיקייה הזאת מתפרסמת כמו שהיא ב-GitHub Pages. הדפים הם HTML,‏ CSS ו-JavaScript סטטיים: כל תרשים הוא SVG שמצויר בדפדפן, בלי תמונות ובלי שרת." },
        { h: "מודל ה-xG",
          p: "xG (שערים צפויים) מתמחר כל בעיטה בין 0 ל-1 לפי התדירות שבה בעיטה כזאת נכנסת. מודל <code>xg_core</code> המשותף הוא <b>רגרסיה לוגיסטית</b> על 14 מאפייני בעיטה: מרחק ולוגריתם המרחק, הזווית שהשער פותח והשילוב שלה עם המרחק, נגיחה או חלק גוף אחר, מצב גדול, בעיטה חופשית, קרן, מצב נייח, מתפרצת והאם הבעיטה הגיעה ממסירה. הוא אומן על <b>11,968 בעיטות</b> (לה ליגה 2025/26 ומונדיאל 2026) בלי דגימה מחדש, ולאחר מכן כויל על תחזיות out-of-fold כך שסך ה-xG שווה לסך השערים (ROC AUC של 0.81 מחוץ לקבוצת האימון). לפנדל ערך קבוע (כ-0.78). בקובץ המודל יש גם שילוב אופציונלי עם LightGBM, אבל האתר משתמש במסלול הלוגיסטי שאינו דורש ספריות נוספות. העונות שיובאו מ-XLALIGA מגיעות עם ה-xG שחושב לכל בעיטה ב-XLALIGA עצמו." },
        { h: "xA ומעבדת השחקן",
          p: "xA (בישולים צפויים) מגיע ממודל נפרד <b>ברמת המסירה</b> ב-<code>xg_core</code>: לכל מסירה הוא מעריך את הסיכוי שתהפוך לבישול. המודל אומן על כ-363 אלף מסירות, כך ששחקן מקבל קרדיט על מסירה טובה גם כשהבעיטה שאחריה מוחמצת. תרשים הרדאר במעבדת השחקן מציג <b>אחוזונים לכל 90 דקות</b> מתוך שחקני הסגל ששיחקו 120 דקות ומעלה. המפות מציגות בעיטות על חצי מגרש (בגודל לפי xG), ועקיפות, תיקולים ומסירות על המגרש המלא." },
        { h: "איך לקרוא את ה-Match Centre",
          p: "בכל דף משחק יש לוח תוצאה וציר שערים, השוואת סטטיסטיקות, תרשים <b>מומנטום xG</b> (xG מצטבר לפי דקה, מדרגה לכל בעיטה), מפת בעיטות לחיצה ותצוגת מסגרת השער, סייר מסירות עם מסננים (מסירות מתקדמות, הגבהות, כדורי עומק, השליש האחרון, חלונות של 5 דקות), דריבלים, רשת מסירות ומיקומים ממוצעים שאפשר לגלול לאורך המשחק, הרכבים עם ציונים, מפה של כל השערים ושחזורי שערים מונפשים שאפשר לייצא כ-PNG או כווידאו." },
        { h: "מגבלות",
          p: "XLALIGA שומר את הפעולות ההתקפיות עם הכדור (בעיטות, מסירות, דריבלים, הצלות, שערים והרכבים) אבל לא את זרם האירועים ההגנתיים. לכן בעונות המיובאות מפת התיקולים במעבדת השחקן ריקה (סך התיקולים לעונה עדיין מגיע מהנתונים המצטברים של XLALIGA), והן מכסות את הליגה בלבד. xG הוא מודל: הוא לא מתחשב במיקום המגנים ובמהירות הבעיטה, ולכן במשחק בודד הוא עשוי להיות שונה מספקים אחרים. שיוך המשחקים למסגרות ב-2025/26 נגזר מהפיד, עם רשימה קטנה של תיקונים ידניים שנבדקה מול 38 משחקי הליגה ב-XLALIGA." }
      ]
    }
  };

  window.RS_I18N = {
    /* header + tabs */
    "Dashboard": "דשבורד",
    "Season overview · fixtures & results · player & xG lab": "סקירת עונה · משחקים ותוצאות · מעבדות xG ושחקנים",
    "Season": "עונה",
    "All seasons": "כל העונות",
    "Choose season": "בחירת עונה",
    "every season on record": "כל העונות שבמאגר",
    "Overview": "סקירה",
    "Matches": "משחקים",
    "Players": "שחקנים",
    "xG Lab": "מעבדת xG",
    "Player Lab": "מעבדת השחקן",
    "Shot Maps": "מפות בעיטות",
    "Data": "נתונים",
    /* overview */
    "Season Overview": "סקירת העונה",
    "Played": "משחקים",
    "Wins": "ניצחונות",
    "Draws": "תיקו",
    "Losses": "הפסדים",
    "Win Rate": "אחוז ניצחונות",
    "Points / Game": "נקודות למשחק",
    "Goals For": "שערי זכות",
    "Goals Against": "שערי חובה",
    "Goal Diff": "הפרש שערים",
    "Clean Sheets": "שערים נקיים",
    "Avg xG / Game": "ממוצע xG למשחק",
    "Total xG For": "סך xG בעד",
    "Total xG Against": "סך xG נגד",
    "Recent form": "כושר אחרון",
    "Record by competition": "מאזן לפי מסגרת",
    "Played, won, drawn, lost, goals and points in each competition this season.": "משחקים, ניצחונות, תיקו, הפסדים, שערים ונקודות בכל מסגרת העונה.",
    "Competition": "מסגרת",
    "Pts": "נק׳",
    "Results timeline": "ציר התוצאות",
    /* matches */
    "Fixtures & results": "משחקים ותוצאות",
    "Season totals": "סיכומי עונה",
    "All competitions": "כל המסגרות",
    "Champions League": "ליגת האלופות",
    "Copa del Rey": "גביע המלך",
    "Search opponent…": "חיפוש יריבה…",
    "Averages are per game played. Tap a column header to sort.": "הממוצעים הם למשחק. הקישו על כותרת עמודה כדי למיין.",
    "Metric": "מדד",
    "Total": "סה״כ",
    "Per game": "למשחק",
    "Goals for": "שערי זכות",
    "Goals against": "שערי חובה",
    "xG for": "xG בעד",
    "xG against": "xG נגד",
    "Shots on target": "בעיטות למסגרת",
    "Big chances": "מצבים גדולים",
    "Duels won": "מאבקים שנוצחו",
    "Saves": "הצלות",
    "Fouls": "עבירות",
    "Clean sheets": "שערים נקיים",
    "Open Match Centre →": "← פתיחת Match Centre",
    "Possession": "החזקת כדור",
    "Expected goals (xG)": "שערים צפויים (xG)",
    "Shots": "בעיטות",
    "Passes": "מסירות",
    "Pass accuracy": "דיוק מסירות",
    /* players */
    "Player Statistics": "סטטיסטיקת שחקנים",
    "Top Scorer": "מלך השערים",
    "Most Assists": "מלך הבישולים",
    "Goals + Assists": "שערים + בישולים",
    "Best Rating": "הציון הגבוה",
    "Highest xG": "ה-xG הגבוה",
    "Goals": "שערים",
    "Assists": "בישולים",
    "Rating": "ציון",
    "Creativity": "יצירתיות",
    "All positions": "כל העמדות",
    "Search a player…": "חיפוש שחקן…",
    "Player": "שחקן",
    "Pos": "עמדה",
    "Apps": "הופעות",
    "Leaderboards": "טבלאות מובילים",
    "Top eight players in each category so far.": "שמונת השחקנים המובילים בכל קטגוריה עד כה.",
    "Average rating": "ציון ממוצע",
    "Expected goals": "שערים צפויים",
    "Key passes": "מסירות מפתח",
    "Take-ons won": "עקיפות מוצלחות",
    /* xG lab */
    "xG Efficiency Lab": "מעבדת יעילות xG",
    "New here? What is xG?": "חדשים כאן? מה זה xG?",
    "Goals Scored": "שערים שהובקעו",
    "Goals Conceded": "שערים שספגה",
    "Finishing vs xG": "סיומת מול xG",
    "Games Over xG": "משחקים מעל ה-xG",
    "Did chances turn into goals?": "האם המצבים הפכו לשערים?",
    "exactly deserved": "בדיוק לפי המגיע",
    "xG created": "ה-xG שנוצר",
    "Goals scored": "שערים שהובקעו",
    "Win": "ניצחון",
    "Draw": "תיקו",
    "Loss": "הפסד",
    "Attack vs defence": "התקפה מול הגנה",
    "xG created and xG conceded, per game, home vs away.": "ה-xG שנוצר וה-xG שנספג, למשחק, בבית מול בחוץ.",
    "Home": "בית",
    "Away": "חוץ",
    "Most clinical finishers": "המסיימים הקטלניים ביותר",
    "Players scoring the most goals above their xG.": "השחקנים שכובשים הכי הרבה מעבר ל-xG שלהם.",
    "Wasteful in front of goal": "בזבזנים מול השער",
    "Players scoring the fewest goals relative to their xG.": "השחקנים שכובשים הכי מעט ביחס ל-xG שלהם.",
    "The same story as a distribution — games by chance quality": "אותו סיפור כהתפלגות: משחקים לפי איכות ההזדמנויות",
    "xG created in the game · below each bar: avg xG → avg goals actually scored": "ה-xG שנוצר במשחק · מתחת לכל עמודה: xG ממוצע ← שערים ממוצעים בפועל",
    /* player lab */
    "Compare": "השוואה",
    "— none —": "ללא",
    "Minutes": "דקות",
    "Key Passes": "מסירות מפתח",
    "Avg Rating": "ציון ממוצע",
    "Head-to-head": "ראש בראש",
    "Action maps": "מפות פעולה",
    "Take-ons": "עקיפות",
    "Tackles": "תיקולים",
    "Progressive passes": "מסירות מתקדמות",
    "Style fingerprint": "טביעת אצבע של סגנון",
    "Finishing": "סיומת",
    "Shooting": "בעיטה",
    "Dribbling": "דריבל",
    "Defending": "הגנה",
    "Aerials": "משחק אווירי",
    "What each spoke means": "מה מודד כל ציר",
    /* shot maps + data */
    "Match Centre — shot maps & passing": "Match Centre: מפות בעיטות ומסירות",
    "Competitions": "מסגרות",
    "Full WhoScored match feeds cached as JSON": "פידים מלאים של WhoScored שנשמרו כ-JSON",
    "Season-aggregated player stats & ratings": "סטטיסטיקות וציוני שחקנים מצטברים לעונה",
    "Every shot with model xG, for the Player Lab": "כל בעיטה עם xG מהמודל, עבור מעבדת השחקן",
    "How it updates": "איך זה מתעדכן",
    /* match centre */
    "· Match Centre": "· Match Centre",
    "Interactive shot & pass explorer": "סייר בעיטות ומסירות אינטראקטיבי",
    "← All matches": "→ כל המשחקים",
    "Expected goals (xG):": "שערים צפויים (xG):",
    "Match stats": "סטטיסטיקת המשחק",
    "xG momentum": "מומנטום xG",
    "Minute": "דקה",
    "Shot map": "מפת בעיטות",
    "Goals only": "שערים בלבד",
    "Shot paths": "מסלולי בעיטה",
    "Min xG": "סף xG",
    "Goal (team colour)": "שער (בצבע הקבוצה)",
    "On target": "למסגרת",
    "Off target": "מחוץ למסגרת",
    "Blocked": "נחסמה",
    "Shot path → goal": "מסלול הבעיטה → שער",
    "● size = xG": "● גודל = xG",
    "Click any shot to see who took it, when, and its xG.": "לחצו על בעיטה כדי לראות מי בעט, מתי, ומה ה-xG שלה.",
    "On-target shots": "בעיטות למסגרת",
    "Goal-mouth view · where on-target shots were aimed": "מבט על השער · לאן כוונו הבעיטות למסגרת",
    "Goal": "שער",
    "On target (saved)": "למסגרת (נהדפה)",
    "Team ring": "טבעת קבוצה",
    "Each dot is an on-target shot, placed where it was aimed in the goal. Click one for details.": "כל נקודה היא בעיטה למסגרת, במקום שאליו כוונה בשער. לחצו לפרטים.",
    "Pass explorer": "סייר מסירות",
    "All players": "כל השחקנים",
    "Type": "סוג",
    "All passes": "כל המסירות",
    "Completed": "הושלמו",
    "Incomplete": "לא הושלמו",
    "Progressive": "מתקדמות",
    "Crosses": "הגבהות",
    "Through balls": "כדורי עומק",
    "Final third": "השליש האחרון",
    "5-min window": "חלון של 5 דקות",
    "completed · progressive/key": "הושלמה · מתקדמת/מפתח",
    "completed · normal": "הושלמה · רגילה",
    "incomplete · forward/key": "לא הושלמה · קדימה/מפתח",
    "incomplete · normal": "לא הושלמה · רגילה",
    "dashed = incomplete · dot = start": "מקווקו = לא הושלמה · נקודה = התחלה",
    "Dribbles": "דריבלים",
    "Outcome": "תוצאה",
    "All dribbles": "כל הדריבלים",
    "Successful": "מוצלחים",
    "Unsuccessful": "לא מוצלחים",
    "successful": "מוצלח",
    "unsuccessful": "לא מוצלח",
    "● = where the take-on happened · → carry direction (next touch)": "● = מקום העקיפה · → כיוון ההובלה (הנגיעה הבאה)",
    "Pass network": "רשת מסירות",
    "Min. combined passes": "מינימום מסירות משותפות",
    "● node = player at average position · size = passes involved": "● צומת = שחקן במיקומו הממוצע · גודל = מספר המסירות",
    "line thickness = passes between the pair": "עובי הקו = מסירות בין שני השחקנים",
    "starting XI, until the first substitution": "ההרכב הפותח, עד החילוף הראשון",
    "Average position": "מיקום ממוצע",
    "Window": "חלון",
    "Full (0→now)": "מלא (0 עד עכשיו)",
    "● node = player's average position in the window · size = touches": "● צומת = המיקום הממוצע של השחקן בחלון · גודל = נגיעות",
    "players appear/disappear as they're subbed on and off": "שחקנים מופיעים ונעלמים לפי החילופים",
    "scrub or press ▶ to watch the shape change": "גררו או לחצו ▶ כדי לראות את המבנה משתנה",
    "Line-ups": "הרכבים",
    "Min · G/A · Rating": "דק׳ · ש/ב · ציון",
    "Substitutes used": "מחליפים שנכנסו",
    "⚽ goal": "⚽ שער",
    "assist": "בישול",
    "yellow": "צהוב",
    "rating coloured by value · min = minutes played": "הציון צבוע לפי ערכו · דק׳ = דקות משחק",
    "All goals map": "מפת כל השערים",
    "Own goal": "שער עצמי",
    "⤓ Download PNG": "⤓ הורדת PNG",
    "Players in move:": "שחקנים במהלך:",
    "Touch (shirt #)": "נגיעה (מספר חולצה)",
    "Move start": "תחילת המהלך",
    "Keeper save": "הצלת שוער",
    "Shot (xG)": "בעיטה (xG)",
    "Pass": "מסירה",
    "Cross": "הגבהה",
    "Carry / dribble": "הובלה / דריבל",
    "Shot": "בעיטה",
    "Goal replays": "שחזורי שערים",
    "▶ Play": "▶ הפעלה",
    "Speed": "מהירות",
    "⤓ Download video": "⤓ הורדת וידאו",
    "Press play": "לחצו על הפעלה",
    "Goal!": "גול!",
    "Build-up:": "בניית המהלך:",
    "Loading match…": "טוען משחק…"
  };

  /* Whole paragraphs: [start of the English text, Hebrew HTML]. Matched on the element's
     normalised text, then handed to brand.js as data-he-html. */
  var HE_BLOCKS = [
    ["Every FC Barcelona fixture in", function () {
      var os = document.getElementById("overviewSeason");
      return 'כל משחקי FC ברצלונה (<span id="overviewSeason">' + (os ? os.textContent : "") + "</span>) בכל המסגרות, עם נתוני ה-xG (שערים צפויים) שמאחורי התוצאות."; }],
    ["Chronological run of results.", "רצף התוצאות לפי הסדר. ירוק = ניצחון, כתום = תיקו, אדום = הפסד; עמודה גבוהה יותר = הפרש שערים גדול יותר."],
    ["Every fixture and result. Tap a match", "כל המשחקים והתוצאות. הקישו על משחק כדי לפתוח את שורת הסטטיסטיקה המלאה מול היריבה, או קפצו ל-Match Centre האינטראקטיבי. עברו ל״סיכומי עונה״ לנתונים מצטברים."],
    ["xG comes from our shot model;", 'ה-xG מגיע ממודל הבעיטות שלנו; כש-Understat פרסם xG למשחק, אנחנו משתמשים בו. ברצלונה מסומנת ב<b class="xg-cmp" style="color:#3ddc97">ירוק</b>.'],
    ["Aggregated across every played match from the WhoScored", "נתונים מצטברים מכל משחק ששוחק, מפידי השחקנים של WhoScored ומזרם האירועים: שערים, בישולים, ציונים, בעיטות, מסירות מפתח, כרטיסים ועוד. בחרו טבלת מובילים או מיינו לפי כל עמודה."],
    ["Min = minutes · Rt = average match rating", "Min = דקות · Rt = ציון ממוצע למשחק · ±xG = שערים פחות xG (איכות הסיומת). נספרים רק משחקים עם נתונים ברמת השחקן."],
    ["Does Barcelona score as much as", "האם ברצלונה כובשת כמו שאיכות ההזדמנויות שלה אומרת שהיא צריכה? התרשימים האלה משווים בין <b>שערים צפויים (xG)</b> למה שקרה בפועל."],
    ["Expected goals (xG) rates every shot", "<b>שערים צפויים (xG)</b> מדרגים כל בעיטה לפי הסיכוי שהיא תיכנס, מ-0 עד 1. בעיטה מקרוב מתוך רחבת החמש יכולה להיות 0.7 xG, ובעיטת ניסיון מ-30 מטר אולי 0.03 xG. סכום הבעיטות אומר כמה שערים היה כובש מסיים <i>ממוצע</i>."],
    ["So if Barcelona racks up", "כלומר, אם ברצלונה צוברת <b>2.5 xG אבל כובשת שער אחד</b>, היא יצרה מצבים טובים ובזבזה אותם. אם היא כובשת <b>3 מתוך 1.0 xG</b>, היא סיימה בצורה מבריקה, או שהיה לה מזל."],
    ["Where does the xG come from?", "<b>מאיפה מגיע ה-xG? בנינו את המודל בעצמנו.</b> כל בעיטה מקבלת ציון ממודל רגרסיה לוגיסטית שאומן על <b>11,830 בעיטות אמיתיות</b> (כל עונת לה ליגה 2025/26 ומונדיאל 2026) מול מה שקרה להן בפועל. המודל שוקל את <b>המרחק</b> של הבעיטה, את <b>הזווית שהשער פותח</b>, האם זו הייתה <b>נגיחה</b>, האם זה היה <b>מצב גדול</b>, ואת <b>סוג המצב</b> (משחק פתוח, בעיטה חופשית, קרן, מצב נייח, מתפרצת), עם כיול סיומת של הלה ליגה (פנדל מקבל ערך קבוע של 0.76). ברמת המשחק הוא תואם את המודל המקצועי של Understat ב-<b>r&nbsp;=&nbsp;0.975</b> במשחקי ברצלונה. אותו מודל רץ בדשבורדים שלנו של הלה ליגה, המונדיאל וברצלונה, כך שאפשר להשוות ביניהם."],
    ["Every dot is one match: xG created", "כל נקודה היא משחק אחד: ה-xG שנוצר (ציר אופקי) מול השערים שהובקעו בפועל (ציר אנכי). נקודות מעל הקו המקווקו = סיומת קטלנית; מתחתיו = בזבוז."],
    ["Every team-match (Barcelona's side", "כל הופעה של קבוצה במשחק (הצד של ברצלונה והצד של היריבה) ממוינת לקבוצה לפי כמות ה-xG שהיא ייצרה. העמודה היא <b>מספר המשחקים</b> שבהם נוצרה איכות הזדמנויות כזאת; מתחת לכל עמודה, <b>xG ממוצע ← שערים ממוצעים</b> שהובקעו בפועל במשחקים האלה. <b style=\"color:#43e8a0\">ירוק = ההזדמנויות הניבו יותר מהצפוי</b>, <b style=\"color:#ff5e7a\">אדום = פחות מהצפוי</b>, כחול ≈ בדיוק לפי הצפי."],
    ["Deep-dive one player:", "צלילה לשחקן אחד: כרטיס סטטיסטיקה עונתי, אותן מפות פעולה כמו ב-Match Centre וטביעת אצבע של אחוזונים מול הסגל. בחרו שחקן שני כדי להשוות זה לצד זה."],
    ["Side-by-side season totals", 'סיכומי עונה זה לצד זה: <b style="color:#3ddc97">ירוק</b> = השחקן הראשון, <b style="color:#4ea1ff">כחול</b> = השני.'],
    ["The Shots map is a half pitch", 'מפת <b>הבעיטות</b> היא חצי מגרש שהשער בראשו, והנקודות בגודל לפי xG: <b style="color:#43e8a0">ירוק = שער</b>, <b style="color:#ff5e7a">אדום מלא = למסגרת</b>, אדום חלול = מחוץ למסגרת או נחסמה. עקיפות, תיקולים ומסירות מוצגים על המגרש המלא (התקפה ←) עם חצים <b style="color:#43e8a0">ירוקים</b> = הצלחה ו<b style="color:#ff5e7a">אדומים</b> = כישלון. כל מפה מציגה את <b>הסיכומים עם פילוח ההצלחה או ההמרה</b>. <b>רחפו מעל כל סימן</b> כדי לראות דקה, xG ומשחק.'],
    ["Each spoke is the player's percentile rank", "כל ציר הוא <b>האחוזון</b> של השחקן מבין שחקני הסגל עם 120 דקות ומעלה, מחושב <b>לכל 90 דקות</b> (הציון הוא הממוצע הגולמי). רחוק יותר מהמרכז = גבוה יותר בסגל; 100 = הטוב ביותר. השוואה מוסיפה שכבה של שחקן שני. רחפו מעל נקודה לערך המדויק."],
    ["Finishing — goals per 90", "<b>סיומת</b>: שערים ל-90 דקות"],
    ["G+A — goals + assists per 90", "<b>G+A</b>: שערים + בישולים ל-90 דקות"],
    ["Shooting — shots per 90", "<b>בעיטה</b>: בעיטות ל-90 דקות"],
    ["Creativity — key passes per 90", "<b>יצירתיות</b>: <b>מסירות מפתח</b> ל-90 דקות, כלומר מסירות שהובילו ישירות לבעיטה (המסירה האחרונה לפני ניסיון של חבר לקבוצה), לפי WhoScored"],
    ["Dribbling — take-ons won per 90", "<b>דריבל</b>: עקיפות מוצלחות ל-90 דקות"],
    ["Defending — tackles + interceptions per 90", "<b>הגנה</b>: תיקולים + חטיפות ל-90 דקות"],
    ["Aerials — aerial duels won per 90", "<b>משחק אווירי</b>: מאבקי אוויר שנוצחו ל-90 דקות"],
    ["Rating — average WhoScored match rating", "<b>ציון</b>: ציון WhoScored ממוצע למשחק (אחוזון של הערך הגולמי)"],
    ["Full interactive dashboards for every match:", "דשבורד אינטראקטיבי מלא לכל משחק: מפות בעיטות של WhoScored ו-Understat, רשתות מסירות, מפות מסירות, עקיפות והשוואת הסטטיסטיקה המלאה. הקישו על משחק כדי לפתוח אותו."],
    ["The dashboard is built from cached WhoScored", "הדשבורד בנוי מפידי משחק של WhoScored שנשמרו מראש ומ-xG של Understat. כל מה שמוצג כאן נוצר ב-Pipeline של הפרויקט, שאוסף מחדש ובונה את האתר בערך שעה אחרי כל משחק."],
    ["A scheduled job runs about", "משימה מתוזמנת רצה בערך <b>שעה אחרי כל שריקת פתיחה של ברצלונה</b>: היא אוספת את המשחק שהסתיים, מחשבת מחדש את נתוני השחקנים וה-xG, בונה מחדש את הדשבורד ואת דפי המשחקים ומפרסמת ל-GitHub Pages."],
    ["Cumulative expected goals over the match", "<b>שערים צפויים</b> מצטברים לאורך המשחק: כל מדרגה היא בעיטה, בגודל לפי ה-xG שלה. הקו הגבוה יותר יצר את המצבים הטובים יותר; ⚽ מסמן שערים (הקישו כדי לראות את הכובש)."]
  ];

  function norm(s) { return String(s).replace(/\s+/g, " ").trim(); }
  // English text of an element even after brand.js swapped some of its text nodes.
  function origText(el) {
    var out = "", w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), n;
    while ((n = w.nextNode())) out += n.__rsOrig != null ? n.__rsOrig : n.nodeValue;
    return out;
  }
  var pending = false;
  function applyBlocks() {
    pending = false;
    var changed = false;
    document.querySelectorAll("p, li, .hint, .sub, .insight").forEach(function (el) {
      if (el.hasAttribute("data-he-html") || el.closest(".rs-bar, .rs-about")) return;
      var t = norm(origText(el));
      for (var i = 0; i < HE_BLOCKS.length; i++) {
        if (t.indexOf(HE_BLOCKS[i][0]) === 0) {
          var h = HE_BLOCKS[i][1];
          el.setAttribute("data-he-html", typeof h === "function" ? h(el) : h);
          changed = true;
          break;
        }
      }
    });
    if (changed && window.RSBrand && window.RSBrand.lang() === "he") window.RSBrand.refresh();
  }
  function schedule() { if (!pending) { pending = true; setTimeout(applyBlocks, 30); } }

  // The overview paragraph holds the live season name; keep it right in both languages.
  function syncSeasonSpan() {
    var os = document.getElementById("overviewSeason"), ss = document.getElementById("seasonSel");
    if (!os || !ss) return;
    var he = window.RSBrand && window.RSBrand.lang() === "he";
    os.textContent = ss.value === "all" ? (he ? "כל העונות שבמאגר" : "every season on record")
                                        : (ss.selectedOptions[0] ? ss.selectedOptions[0].textContent : ss.value);
  }

  function start() {
    applyBlocks();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    var ss = document.getElementById("seasonSel");
    if (ss) ss.addEventListener("change", function () { setTimeout(syncSeasonSpan, 0); });
  }
  window.addEventListener("sitelangchange", function () { setTimeout(syncSeasonSpan, 0); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
