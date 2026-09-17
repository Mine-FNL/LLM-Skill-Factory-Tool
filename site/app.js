/* skillmd-lint playground — JS mirror of Mine-FNL/skillmd-lint rules.py
 *
 * Same constants, same rule logic, same output formats (human / JSON /
 * GitHub Actions annotations) as the Python reference implementation.
 * No dependencies, no build step. Lint runs entirely in the browser.
 *
 * Source of truth: https://github.com/Mine-FNL/skillmd-lint/blob/main/skillmd_lint/rules.py
 */
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // 1. Constants — copied verbatim from skillmd_lint/rules.py
  // ------------------------------------------------------------------

  var RESERVED_SLUGS = [
    "",
    ".",
    "..",
    "~",
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    "anthropic", "claude", "openai", "gpt", "grok"
  ];
  var RESERVED_SET = new Set(RESERVED_SLUGS);

  var MAX_NAME_LEN = 64;
  var MAX_DESC_LEN = 1024;
  var MIN_BODY_LINES = 20;
  var RECOMMENDED_BODY_LINES = 200;

  var NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

  var POSITIVE_TRIGGER_PHRASES = [
    "use when",
    "use this",
    "use this skill",
    "when ",
    "whenever",
    "for ",
    "trigger",
    "applies when",
    "if the user",
    "whenever you need"
  ];
  var NEGATIVE_TRIGGER_PHRASES = [
    "do not use",
    "don't use",
    "not for",
    "do not apply",
    "not appropriate",
    "not applicable",
    "skip when"
  ];

  // ------------------------------------------------------------------
  // 2. Tiny frontmatter YAML parser
  //
  // Handles the subset of YAML that SKILL.md actually uses:
  //   - `key: scalar` plain or quoted strings
  //   - `key: |`  block scalar (literal newlines, trailing newline stripped)
  //   - `key: >`  folded scalar (newlines preserved for our case)
  //   - `key: null` / `key: ~` / empty -> null / ""
  //
  // Anything we can't parse returns {} (mirrors `_split_frontmatter`).
  // ------------------------------------------------------------------

  function unquoteScalar(s) {
    s = s.trim();
    // YAML null forms: empty value, "null", "~"  ->  Python's None.
    if (s === "" || s === "~" || s === "null" || s === "Null" || s === "NULL") return null;
    if (s === "true" || s === "True" || s === "TRUE") return true;
    if (s === "false" || s === "False" || s === "FALSE") return false;
    if (s.length >= 2 &&
        ((s[0] === '"' && s[s.length - 1] === '"') ||
         (s[0] === "'" && s[s.length - 1] === "'"))) {
      return s.slice(1, -1);
    }
    return s;
  }

  function splitFrontmatter(text) {
    // Mirrors `def _split_frontmatter(text)` from rules.py, including the
    // splitlines() semantics (no trailing empty element).
    var stripped = text.replace(/^\uFEFF/, "");
    if (!stripped.startsWith("---")) return [{}, text];

    var lines = pySplitlines(stripped);
    var end = -1;
    for (var i = 1; i < lines.length; i++) {
      if (lines[i].trim() === "---") { end = i; break; }
    }
    if (end === -1) return [{}, text];

    var fmBlock = lines.slice(1, end).join("\n");
    var bodyLines = lines.slice(end + 1);
    while (bodyLines.length && bodyLines[0] === "") bodyLines.shift();
    var body = bodyLines.join("\n");

    var data;
    try { data = parseSimpleYaml(fmBlock); }
    catch (e) { return [{}, body]; }
    if (!data || typeof data !== "object" || Array.isArray(data)) return [{}, body];
    return [data, body];
  }

  // Python's str.splitlines() — does not produce a trailing empty element
  // when the string ends with a newline. The default JS String.split() does,
  // which would inflate line counts and mis-align body-length findings.
  function pySplitlines(s) {
    if (s === "") return [];
    var out = [];
    var start = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c === 10) {            // \n
        out.push(s.substring(start, i));
        start = i + 1;
      } else if (c === 13) {     // \r
        out.push(s.substring(start, i));
        if (s.charCodeAt(i + 1) === 10) { start = i + 2; i++; }
        else { start = i + 1; }
      }
    }
    if (start < s.length) out.push(s.substring(start));
    return out;
  }

  function parseSimpleYaml(block) {
    var lines = block.split(/\r?\n/);
    var result = {};
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];
      if (line.trim() === "" || line.trim().startsWith("#")) { i++; continue; }
      var m = line.match(/^([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
      if (!m) { i++; continue; }
      var key = m[1];
      var rest = m[2];
      if (rest === "|" || rest === ">") {
        // Block scalar: collect indented (or empty) lines until indent drops.
        var parts = [];
        i++;
        var sawContent = false;
        var minIndent = null;
        while (i < lines.length) {
          var bl = lines[i];
          if (bl === "" || /^\s/.test(bl)) {
            parts.push(bl);
            if (bl !== "") {
              var lead = bl.match(/^(\s*)/)[1].length;
              if (minIndent === null || lead < minIndent) minIndent = lead;
              sawContent = true;
            }
            i++;
          } else { break; }
        }
        if (!sawContent) { result[key] = ""; continue; }
        var stripped = parts.map(function (p) {
          if (p === "") return "";
          return p.slice(minIndent);
        });
        var joined = stripped.join("\n");
        // Strip trailing blank lines, like Python's default strip-chomping.
        joined = joined.replace(/\n+$/, "");
        result[key] = joined;
      } else {
        result[key] = unquoteScalar(rest);
        i++;
      }
    }
    return result;
  }

  // ------------------------------------------------------------------
  // 3. Rules — same logic, same messages, same severity as rules.py
  // ------------------------------------------------------------------

  function hasXmlTags(s) {
    return /<[a-zA-Z][^>]*>/.test(s);
  }

  function finding(code, severity, message) {
    return { code: code, severity: severity, message: message, path: "<text>" };
  }

  // E002 — frontmatter missing or invalid
  function ruleFrontmatter(_p, fm) {
    if (!fm || Object.keys(fm).length === 0) {
      return [finding(
        "E002", "error",
        "frontmatter is missing or invalid; SKILL.md must start with " +
        "a YAML frontmatter block delimited by `---` markers"
      )];
    }
    return [];
  }

  // E003 — name missing or empty
  function ruleNamePresent(_p, fm) {
    var name = fm.name;
    if (!name || typeof name !== "string" || !name.trim()) {
      return [finding("E003", "error", "`name` is missing or empty")];
    }
    return [];
  }

  // E004 — name format (lowercase kebab-case)
  function ruleNameFormat(_p, fm) {
    var name = fm.name == null ? "" : fm.name;
    if (typeof name !== "string" || !name) return [];
    if (!NAME_RE.test(name)) {
      return [finding(
        "E004", "error",
        "name '" + name + "' must be lowercase kebab-case " +
        "(letters, digits, single hyphens; no leading/trailing/double " +
        "hyphens; no underscores or uppercase letters)"
      )];
    }
    return [];
  }

  // E005 — name collides with a reserved slug
  // Python: `name = fm.get("name", "")`. A missing key becomes "", which
  // IS in RESERVED_SLUGS and fires E005. An explicit null stays null
  // (not a string) and skips. We mirror that distinction.
  function ruleNameReserved(_p, fm) {
    var has = Object.prototype.hasOwnProperty.call(fm, "name");
    var name = has ? fm.name : "";
    if (typeof name !== "string") return [];
    if (RESERVED_SET.has(name)) {
      return [finding(
        "E005", "error",
        "name '" + name + "' collides with a reserved word (Windows device " +
        "names, the open SKILL.md reserved list, or filesystem specials)"
      )];
    }
    return [];
  }

  // E006 — name length
  function ruleNameLength(_p, fm) {
    var name = fm.name == null ? "" : fm.name;
    if (typeof name !== "string" || !name) return [];
    if (name.length > MAX_NAME_LEN) {
      return [finding(
        "E006", "error",
        "name is " + name.length + " chars; spec limit is " + MAX_NAME_LEN
      )];
    }
    return [];
  }

  // E007 — description missing or empty
  function ruleDescriptionPresent(_p, fm) {
    var desc = fm.description;
    if (!desc || typeof desc !== "string" || !desc.trim()) {
      return [finding("E007", "error", "`description` is missing or empty")];
    }
    return [];
  }

  // E008 — description length
  function ruleDescriptionLength(_p, fm) {
    var desc = fm.description == null ? "" : fm.description;
    if (typeof desc !== "string" || !desc) return [];
    if (desc.length > MAX_DESC_LEN) {
      return [finding(
        "E008", "error",
        "description is " + desc.length + " chars; spec limit is " + MAX_DESC_LEN
      )];
    }
    return [];
  }

  // E009 — description contains XML tags
  function ruleDescriptionXml(_p, fm) {
    var desc = fm.description == null ? "" : fm.description;
    if (typeof desc === "string" && hasXmlTags(desc)) {
      return [finding(
        "E009", "error",
        "description contains XML tags; spec forbids them"
      )];
    }
    return [];
  }

  // W001 — description has no positive trigger phrase
  function ruleDescriptionPositiveTrigger(_p, fm) {
    var desc = (fm.description == null ? "" : fm.description).toString().toLowerCase();
    if (!desc) return [];
    var hit = POSITIVE_TRIGGER_PHRASES.some(function (phr) { return desc.indexOf(phr) !== -1; });
    if (!hit) {
      return [finding(
        "W001", "warning",
        "description has no positive trigger phrase (e.g. 'use when', " +
        "'whenever', 'for ...'). The agent uses these to decide whether " +
        "to load the skill."
      )];
    }
    return [];
  }

  // W002 — description has no negative trigger phrase
  function ruleDescriptionNegativeTrigger(_p, fm) {
    var desc = (fm.description == null ? "" : fm.description).toString().toLowerCase();
    if (!desc) return [];
    var hit = NEGATIVE_TRIGGER_PHRASES.some(function (phr) { return desc.indexOf(phr) !== -1; });
    if (!hit) {
      return [finding(
        "W002", "warning",
        "description has no negative trigger ('do not use when\u2026', " +
        "'not for\u2026'). Negative triggers reduce over-firing."
      )];
    }
    return [];
  }

  // W003 / W004 — body line count (Python uses body.splitlines())
  function ruleBodyLength(_p, _fm, body) {
    var n = pySplitlines(body).length;
    if (n < MIN_BODY_LINES) {
      return [finding(
        "W003", "warning",
        "body has " + n + " lines; spec recommends at least " + MIN_BODY_LINES
      )];
    }
    if (n > RECOMMENDED_BODY_LINES) {
      return [finding(
        "W004", "warning",
        "body has " + n + " lines; >" + RECOMMENDED_BODY_LINES + " suggests " +
        "progressive disclosure (move detail into references/)"
      )];
    }
    return [];
  }

  // W005 — no '## When to use' (or equivalent) section
  function ruleWhenToUseSection(_p, _fm, body) {
    var low = body.toLowerCase();
    var markers = ["## when to use", "## usage", "## when", "## how to use"];
    var hit = markers.some(function (m) { return low.indexOf(m) !== -1; });
    if (!hit) {
      return [finding(
        "W005", "warning",
        "no '## When to use' (or equivalent) section in the body \u2014 " +
        "readers can't quickly find the activation conditions"
      )];
    }
    return [];
  }

  // W006 — body has no concrete examples
  function ruleHasExamples(_p, _fm, body) {
    var low = body.toLowerCase();
    var markers = ["example", "e.g.", "for example", "for instance"];
    var hit = markers.some(function (m) { return low.indexOf(m) !== -1; });
    if (!hit) {
      return [finding(
        "W006", "warning",
        "body has no concrete examples; skills with examples are " +
        "significantly more reliable in practice"
      )];
    }
    return [];
  }

  // E001 — file not found (file-mode only, never fires from text input)
  // W007 — no SKILL.md found in folder (folder-mode only, never fires from text)
  // Both are documented in the UI but never emitted here.

  var RULES = [
    ruleFrontmatter,
    ruleNamePresent,
    ruleNameFormat,
    ruleNameReserved,
    ruleNameLength,
    ruleDescriptionPresent,
    ruleDescriptionLength,
    ruleDescriptionXml,
    ruleDescriptionPositiveTrigger,
    ruleDescriptionNegativeTrigger,
    ruleBodyLength,
    ruleWhenToUseSection,
    ruleHasExamples
  ];

  // ------------------------------------------------------------------
  // 4. lint_text() — mirrors lint_text() / LintResult in rules.py
  // ------------------------------------------------------------------

  function lintText(text, path) {
    var parts = splitFrontmatter(text);
    var fm = parts[0], body = parts[1];
    var p = path || "<text>";

    var result = {
      path: p,
      looks_like_skill: !!(fm && Object.keys(fm).length > 0),
      passed: false,
      errors: [],
      warnings: [],
      findings: []
    };

    for (var i = 0; i < RULES.length; i++) {
      var findings = RULES[i](p, fm, body);
      for (var j = 0; j < findings.length; j++) {
        var f = Object.assign({}, findings[j], { path: p });
        result.findings.push(f);
        if (f.severity === "error") result.errors.push(f);
        else if (f.severity === "warning") result.warnings.push(f);
      }
    }

    result.passed = result.errors.length === 0 && result.looks_like_skill;
    return result;
  }

  // ------------------------------------------------------------------
  // 5. Output formats — human, JSON, GitHub Actions
  //    Match the Python CLI output byte-for-byte (modulo ANSI).
  // ------------------------------------------------------------------

  function formatHuman(results) {
    // Mirrors cli._format_human: `{glyph:<11}: msg  [CODE]`, summary line
    // is `✓ all N file(s) passed` (clean) or `✗/⚠ N error(s), N warning(s)`.
    var out = [];
    var totalErr = 0;
    var totalWarn = 0;
    for (var i = 0; i < results.length; i++) {
      var r = results[i];
      if (r.findings.length === 0 && r.looks_like_skill) {
        out.push("  \u2713 " + r.path + ": ok");
        continue;
      }
      out.push(r.path);
      for (var k = 0; k < r.findings.length; k++) {
        var f = r.findings[k];
        var glyph = f.severity === "error" ? "\u2717 error" : "\u26A0 warning";
        while (glyph.length < 11) glyph += " ";
        out.push("  " + glyph + ": " + f.message + "  [" + f.code + "]");
        if (f.severity === "error") totalErr++;
        else if (f.severity === "warning") totalWarn++;
      }
    }
    out.push("");
    if (totalErr === 0 && totalWarn === 0) {
      out.push("\u2713 all " + results.length + " file(s) passed");
    } else {
      var mark = totalErr > 0 ? "\u2717" : "\u26A0";
      out.push(mark + " " + totalErr + " error(s), " + totalWarn + " warning(s)");
    }
    return out.join("\n");
  }

  function formatJSON(results) {
    var compact = results.map(function (r) {
      return {
        path: r.path,
        looks_like_skill: r.looks_like_skill,
        passed: r.passed,
        errors: r.errors.map(function (f) {
          return { code: f.code, severity: f.severity, message: f.message, path: f.path };
        }),
        warnings: r.warnings.map(function (f) {
          return { code: f.code, severity: f.severity, message: f.message, path: f.path };
        })
      };
    });
    return JSON.stringify(compact, null, 2);
  }

  function formatGithub(results) {
    // https://docs.github.com/actions/using-workflows/workflow-commands-for-github-actions
    var lines = [];
    for (var i = 0; i < results.length; i++) {
      var r = results[i];
      var findings = r.findings;
      for (var k = 0; k < findings.length; k++) {
        var f = findings[k];
        var sev = f.severity; // 'error' | 'warning'
        lines.push("::" + sev + " file=" + r.path + ",line=1::" +
                   f.code + ": " + f.message);
      }
    }
    return lines.join("\n");
  }

  // ------------------------------------------------------------------
  // 6. Sample content
  // ------------------------------------------------------------------

  var VALID_EXAMPLE = [
    "---",
    "name: quant-research-analyst",
    "description: |",
    "  Use when designing, reviewing, or critiquing quantitative trading or",
    "  investment research \u2014 alpha signals, backtests, factor models, and",
    "  statistical validation. Trigger on requests like \"backtest this",
    "  strategy\", \"is this signal real?\", or questions about Sharpe ratios,",
    "  overfitting, look-ahead bias, or factor exposures. Do not use when",
    "  the work is about discretionary stock-picking or pure macro views \u2014",
    "  those need a different specialist.",
    "---",
    "",
    "# Quant Research Analyst",
    "",
    "Act as a skeptical quantitative researcher. Your default stance is that",
    "an apparent edge is a bug or a bias until proven otherwise.",
    "",
    "## Core principles",
    "- Assume overfitting first. The burden of proof is on the signal, not on the doubter.",
    "- Separate in-sample design from out-of-sample validation; never tune on the test set.",
    "- Returns are not edges until they survive costs, capacity, and a multiple-testing adjustment.",
    "",
    "## When to use this skill",
    "- Reviewing a backtest before anyone trades on it.",
    "- Stress-testing a proposed alpha signal.",
    "- Auditing factor exposures and Sharpe ratio claims.",
    "",
    "## Validation checklist (run before believing any backtest)",
    "- [ ] Point-in-time data \u2014 no look-ahead.",
    "- [ ] Realistic costs: commissions, slippage, borrow, and market impact.",
    "- [ ] Out-of-sample or walk-forward results.",
    "- [ ] Multiple-testing penalty: deflate Sharpe accordingly.",
    "- [ ] Stability across regimes and sub-periods.",
    "- [ ] Capacity: does the edge survive at the AUM you intend to run?",
    "",
    "## Example \u2014 good vs poor",
    "- Poor: \"Backtest shows 40% annual return, Sharpe 2.8 in-sample.\" \u2192 reject pending OOS and cost analysis.",
    "- Good: \"Net-of-cost Sharpe 0.9 out-of-sample across two regimes, low factor loadings, stable across sub-periods, capacity ~$200M.\" \u2192 candidate for paper trading.",
    ""
  ].join("\n");

  var INVALID_EXAMPLE = [
    "---",
    "name: BadName!",
    "description: This description has no trigger phrases of any kind. It also contains <b>XML</b> tags which the spec forbids.",
    "---",
    "",
    "Short body."
  ].join("\n");

  // ------------------------------------------------------------------
  // 7. UI wiring
  // ------------------------------------------------------------------

  function el(id) { return document.getElementById(id); }

  var editor, output, summary, status, editorMeta;
  var activeTab = "human";

  function debounce(fn, ms) {
    var t = null;
    return function () {
      var args = arguments;
      if (t) clearTimeout(t);
      t = setTimeout(function () { fn.apply(null, args); }, ms);
    };
  }

  function escapeHTML(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }

  function renderHumanColored(text, result) {
    // Returns HTML where findings are highlighted by severity.
    var findings = result.findings;
    var html = "";
    var lines = text.split("\n");
    if (findings.length === 0) {
      html = "<span class=\"ln-ok\">" + escapeHTML(text) + "</span>";
    } else {
      // Simple line-by-line coloring: each finding occupies the first
      // body line for visual hint. The Python output has a single per-line
      // entry, so we mirror that by aligning all findings to line 1 of the
      // rendered output.
      var summary = "";
      var sevClass = result.errors.length > 0 ? "ln-err" : "ln-warn";
      var lines2 = [];
      for (var k = 0; k < findings.length; k++) {
        var f = findings[k];
        var cls = f.severity === "error" ? "ln-err" : "ln-warn";
        var sev = f.severity === "error" ? "\u2717 error" : "\u26A0 warning";
        while (sev.length < 11) sev += " ";
        lines2.push(
          "<span class=\"" + cls + "\">  " + escapeHTML(sev) + ": " +
          escapeHTML(f.message) + "  [" +
          "<span class=\"ln-code\">" + escapeHTML(f.code) + "</span>" +
          "]</span>"
        );
      }
      html = "<span class=\"ln-path\">" + escapeHTML(result.path) + "</span>\n" +
             lines2.join("\n") + "\n\n" +
             "<span class=\"" + sevClass + "\">" +
             escapeHTML(
               (result.errors.length > 0 ? "\u2717 " : "\u2713 ") +
               result.errors.length + " error(s), " +
               result.warnings.length + " warning(s)"
             ) +
             "</span>";
    }
    output.innerHTML = html;
  }

  function render() {
    var text = editor.value;
    var result = lintText(text);
    var arr = [result];

    // Summary line
    var passed = result.passed;
    var eN = result.errors.length, wN = result.warnings.length;
    var html = "";
    if (eN > 0) {
      html += "<span class=\"pill pill-err\">\u2717 " + eN + " error" + (eN === 1 ? "" : "s") + "</span>";
    } else if (passed) {
      html += "<span class=\"pill pill-ok\">\u2713 passed</span>";
    } else {
      html += "<span class=\"pill pill-ok\">\u2713 lint clean</span>";
    }
    if (wN > 0) {
      html += "<span class=\"pill pill-warn\">\u26A0 " + wN + " warning" + (wN === 1 ? "" : "s") + "</span>";
    }
    if (!result.looks_like_skill) {
      html += "<span class=\"pill\" style=\"color:var(--text-faint)\">not a SKILL.md</span>";
    }
    summary.innerHTML = html;

    // Output pane
    if (activeTab === "human") {
      renderHumanColored(text, result);
      output.className = "results-output";
    } else if (activeTab === "json") {
      output.textContent = formatJSON(arr);
      output.className = "results-output";
    } else if (activeTab === "github") {
      output.textContent = formatGithub(arr);
      output.className = "results-output";
    }

    // Status / editor meta
    editorMeta.textContent =
      text.split("\n").length + " line" + (text.split("\n").length === 1 ? "" : "s") +
      " \u00B7 " + text.length + " char" + (text.length === 1 ? "" : "s");

    if (!result.looks_like_skill && text.trim() !== "") {
      status.textContent = "Not a SKILL.md (missing `---` frontmatter).";
      status.className = "toolbar-status is-warn";
    } else if (eN > 0) {
      status.textContent = eN + " error" + (eN === 1 ? "" : "s") +
                           ", " + wN + " warning" + (wN === 1 ? "" : "s");
      status.className = "toolbar-status is-err";
    } else if (wN > 0) {
      status.textContent = "Passed with " + wN + " warning" + (wN === 1 ? "" : "s") + ".";
      status.className = "toolbar-status is-warn";
    } else if (text.trim() === "") {
      status.textContent = "";
      status.className = "toolbar-status";
    } else {
      status.textContent = "Passed.";
      status.className = "toolbar-status is-ok";
    }

    // Sync URL (only on first render or when user explicitly loads).
    if (window._skillmdSyncURL !== false) {
      try {
        var url = new URL(window.location.href);
        url.searchParams.delete("skill");
        if (text.length > 0 && text.length < 2000) {
          url.searchParams.set("skill", text);
        }
        window.history.replaceState(null, "", url.toString());
      } catch (e) { /* noop */ }
    }
  }

  function setTab(name) {
    activeTab = name;
    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
      var t = tabs[i];
      var isActive = t.dataset.tab === name;
      t.classList.toggle("is-active", isActive);
      t.setAttribute("aria-selected", isActive ? "true" : "false");
    }
    render();
  }

  function loadSample(text) {
    window._skillmdSyncURL = false;
    editor.value = text;
    window._skillmdSyncURL = true;
    render();
    editor.focus();
    // Move caret to start for easy editing.
    try { editor.setSelectionRange(0, 0); } catch (e) { /* noop */ }
  }

  function copyShareLink() {
    var text = editor.value;
    var url = new URL(window.location.href);
    url.searchParams.set("skill", text);
    var s = url.toString();
    var ok = function () {
      status.textContent = text.length > 1800
        ? "Link copied (URL is large; some clients may truncate)."
        : "Share link copied to clipboard.";
      status.className = "toolbar-status is-ok";
    };
    var fail = function () {
      status.textContent = "Couldn't access clipboard. URL is in the bar.";
      status.className = "toolbar-status is-warn";
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(s).then(ok, fail);
    } else {
      // Fallback: temporary textarea + execCommand.
      try {
        var ta = document.createElement("textarea");
        ta.value = s;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        ok();
      } catch (e) { fail(); }
    }
  }

  function loadFromURL() {
    try {
      var url = new URL(window.location.href);
      var s = url.searchParams.get("skill");
      if (s != null) {
        editor.value = s;
        status.textContent = "Loaded from ?skill= URL.";
        status.className = "toolbar-status is-ok";
        return true;
      }
    } catch (e) { /* noop */ }
    return false;
  }

  function init() {
    editor = el("editor");
    output = el("output");
    summary = el("summary");
    status = el("status");
    editorMeta = el("editor-meta");

    var loaded = loadFromURL();
    if (!loaded) editor.value = "";

    document.getElementById("btn-valid").addEventListener("click", function () {
      loadSample(VALID_EXAMPLE);
    });
    document.getElementById("btn-invalid").addEventListener("click", function () {
      loadSample(INVALID_EXAMPLE);
    });
    document.getElementById("btn-clear").addEventListener("click", function () {
      window._skillmdSyncURL = false;
      editor.value = "";
      window._skillmdSyncURL = true;
      render();
      editor.focus();
    });
    document.getElementById("btn-share").addEventListener("click", copyShareLink);

    var tabs = document.querySelectorAll(".tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function () { setTab(this.dataset.tab); });
    }

    var debouncedRender = debounce(render, 150);
    editor.addEventListener("input", function () {
      // Always sync URL when user types, just throttled.
      debouncedRender();
    });

    render();

    // Expose a small testing hook so QA scripts can verify rule parity.
    window._skillmd = {
      lintText: lintText,
      splitFrontmatter: splitFrontmatter,
      formatHuman: formatHuman,
      formatJSON: formatJSON,
      formatGithub: formatGithub,
      constants: {
        MAX_NAME_LEN: MAX_NAME_LEN,
        MAX_DESC_LEN: MAX_DESC_LEN,
        MIN_BODY_LINES: MIN_BODY_LINES,
        RECOMMENDED_BODY_LINES: RECOMMENDED_BODY_LINES,
        RESERVED_SLUGS: RESERVED_SLUGS.slice()
      }
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();