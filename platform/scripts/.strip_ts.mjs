/* Strip narrative comments from TS/TSX, keeping what earns its place.
 *
 * Uses the TypeScript scanner for exact comment ranges, so a "//" inside a
 * string or a URL is never mistaken for a comment. Keep rules match the
 * Python pass: tool directives verbatim, JSDoc collapsed to one sentence,
 * and a plain comment only when it records a hazard.
 *
 * Usage: node strip_ts.mjs <file>...
 */
import { readFileSync, writeFileSync } from "node:fs";
import ts from "typescript";

const DIRECTIVE =
  /(eslint-|@ts-|prettier-ignore|tslint|webpackChunkName|@jsx|@license|@preserve|SPDX|Copyright|<reference|c8 |v8 ignore|istanbul)/i;

const HAZARD =
  /\b(must not|must be|must stay|never |otherwise |order matters|race condition|silently|do not |don't |cannot |can't |deliberately|on purpose|beware|would break|would fail|would silently|breaks the|is what made|which is why)\b/i;

const sentences = (text) =>
  text
    .split(/(?<!\be\.g)(?<!\bi\.e)(?<![A-Z])\.(?:\s|$)/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => `${s}.`);

const firstSentence = (text) => sentences(text)[0] ?? "";

const hazardSentence = (text) =>
  sentences(text).find((s) => HAZARD.test(s)) ?? firstSentence(text);

/** The prose inside a comment, with its markers and leading stars removed. */
function body(raw) {
  let t = raw;
  if (t.startsWith("/*")) t = t.slice(2).replace(/\*\/$/, "");
  return t
    .split("\n")
    .map((l) => l.replace(/^\s*\/\/+/, "").replace(/^\s*\*+/, "").trim())
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Break text into lines that fit, prefixed for a comment body. */
function wrapLines(text, indent, prefix, limit = 88) {
  const room = Math.max(24, limit - indent.length - prefix.length);
  const out = [];
  let cur = "";
  for (const w of text.split(/\s+/)) {
    if (cur && `${cur} ${w}`.length > room) {
      out.push(cur);
      cur = w;
    } else {
      cur = cur ? `${cur} ${w}` : w;
    }
  }
  if (cur) out.push(cur);
  return out;
}

/** Render a kept comment, wrapped, at the indent it sits on. */
function render(text, indent, style) {
  const lines = wrapLines(text, indent, style === "line" ? "// " : " * ");
  if (style === "line") return lines.map((l) => `// ${l}`).join(`\n${indent}`);
  if (lines.length === 1) return `/* ${lines[0]} */`;
  return [`/*`, ...lines.map((l) => ` * ${l}`), ` */`].join(`\n${indent}`);
}

function commentRanges(src, fileName) {
  const scanner = ts.createScanner(
    ts.ScriptTarget.Latest,
    /* skipTrivia */ false,
    fileName.endsWith("x") ? ts.LanguageVariant.JSX : ts.LanguageVariant.Standard,
    src,
  );
  const out = [];
  let token = scanner.scan();
  while (token !== ts.SyntaxKind.EndOfFileToken) {
    if (
      token === ts.SyntaxKind.SingleLineCommentTrivia ||
      token === ts.SyntaxKind.MultiLineCommentTrivia
    ) {
      out.push({
        pos: scanner.getTokenStart(),
        end: scanner.getTokenEnd(),
        line: token === ts.SyntaxKind.SingleLineCommentTrivia,
      });
    }
    token = scanner.scan();
  }
  return merge(out, src);
}

/* The scanner emits every "//" line as its own comment, so a paragraph
 * written across several of them arrives as N unrelated tokens. Left
 * ungrouped, a hazard on line 2 keeps line 2 alone and the sentence reads as
 * a fragment torn out of the middle. Consecutive own-line "//" comments are
 * therefore merged into one range before any keep/drop decision. */
function merge(ranges, src) {
  const ownLine = (pos) => {
    const start = src.lastIndexOf("\n", pos - 1) + 1;
    return src.slice(start, pos).trim() === "";
  };
  const lineOf = (pos) => src.slice(0, pos).split("\n").length;
  const out = [];
  for (const r of ranges) {
    const prev = out[out.length - 1];
    if (
      prev &&
      prev.line &&
      r.line &&
      ownLine(prev.pos) &&
      ownLine(r.pos) &&
      lineOf(r.pos) === lineOf(prev.pos) + (prev.lines ?? 1)
    ) {
      prev.end = r.end;
      prev.lines = (prev.lines ?? 1) + 1;
      continue;
    }
    out.push({ ...r, lines: 1 });
  }
  return out;
}

function strip(src, fileName) {
  const ranges = commentRanges(src, fileName);
  // Apply back-to-front so earlier offsets stay valid.
  let out = src;
  for (const { pos, end } of [...ranges].reverse()) {
    const raw = src.slice(pos, end);
    if (DIRECTIVE.test(raw)) continue;

    const text = body(raw);
    const isJsDoc = raw.startsWith("/**");
    const lineStartOf = out.lastIndexOf("\n", pos - 1) + 1;
    const indent = /^[ \t]*/.exec(out.slice(lineStartOf, pos))[0];
    let replacement = "";

    if (isJsDoc && text) {
      const s = firstSentence(text);
      const one = `/** ${s} */`;
      replacement =
        indent.length + one.length <= 88
          ? one
          : [`/**`, ...wrapLines(s, indent, " * ").map((l) => ` * ${l}`), ` */`].join(
              `\n${indent}`,
            );
    } else if (HAZARD.test(text)) {
      replacement = render(hazardSentence(text), indent, raw.startsWith("//") ? "line" : "block");
    }

    // A JSX comment is written {/* ... */}; dropping only the comment leaves
    // an empty expression container behind, so take the braces with it.
    let from = pos;
    let to = end;
    if (!replacement) {
      const before = out.slice(0, pos);
      const after = out.slice(end);
      const openBrace = /\{\s*$/.exec(before);
      const closeBrace = /^\s*\}/.exec(after);
      if (raw.startsWith("/*") && openBrace && closeBrace) {
        from = pos - openBrace[0].length;
        to = end + closeBrace[0].length;
      }
      // Take the rest of the line with it when nothing else is on it.
      const lineStart = out.lastIndexOf("\n", from - 1) + 1;
      const lineEndIdx = out.indexOf("\n", to);
      const lineEnd = lineEndIdx === -1 ? out.length : lineEndIdx;
      const head = out.slice(lineStart, from);
      const tail = out.slice(to, lineEnd);
      if (head.trim() === "" && tail.trim() === "") {
        from = lineStart;
        to = lineEnd + 1;
      } else if (head.trim() === "") {
        from = lineStart;
      } else if (tail.trim() === "") {
        // A trailing comment: drop it and the space before it.
        from = lineStart + head.replace(/\s+$/, "").length;
        to = lineEnd;
      }
    }
    out = out.slice(0, from) + replacement + out.slice(to);
  }
  return out.replace(/\n{3,}/g, "\n\n").replace(/\s+$/, "") + "\n";
}

let changed = 0;
for (const file of process.argv.slice(2)) {
  const src = readFileSync(file, "utf8");
  const next = strip(src, file);
  if (next === src) continue;
  // Refuse to write anything the parser can no longer read.
  const parsed = ts.createSourceFile(file, next, ts.ScriptTarget.Latest, true);
  if (parsed.parseDiagnostics?.length) {
    console.log(`SKIP (would break) ${file}: ${parsed.parseDiagnostics[0].messageText}`);
    continue;
  }
  writeFileSync(file, next);
  changed++;
}
console.log(`${changed} file(s) rewritten`);
