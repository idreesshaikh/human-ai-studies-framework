import { useEffect, useRef } from "react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

/*
 * The whole thing is decorative to a screen reader, never takes pointer events, renders
 * a single static frame under reduced motion, and stops its loop entirely when the tab
 * is hidden or the hero is scrolled away.
 */

/**
 * Radius per magnitude, relative to the field's short edge — the same 1–5 ramp the
 * grounding marks use, so a big object still reads as strong evidence rather than as a
 * nearer star.
 */
const R = [0, 0.9, 1.3, 1.9, 2.6, 3.4];

const COUNT = 180;
/** Threads join objects closer than this share of the short edge. */
const THREAD_REACH = 0.11;
/** Below this the centre column is left clear for the headline. */
const CLEAR_RADIUS = 0.34;

const TRANSIENT_EVERY = 4.5;
const TRANSIENT_LIFE = 2.6;
/** A signal travels one thread roughly this often, and takes this long to cross it. */
const SIGNAL_EVERY = 2.1;
const SIGNAL_LIFE = 1.3;
const GLYPH_DRAW = 3.2;
const GLYPH_HOLD = 4.5;
const GLYPH_FADE = 1.8;
const GLYPH_GAP = 2.2;
const GLYPH_CYCLE = GLYPH_DRAW + GLYPH_HOLD + GLYPH_FADE + GLYPH_GAP;

/**
 * Deterministic noise, so the field is the same plate on every render and never reflows
 * between mounts.
 */
function seeded(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Obj = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  m: number;
  phase: number;
  rate: number;
};

function buildField(): Obj[] {
  const rnd = seeded(0x25cb9e81);
  const out: Obj[] = [];
  while (out.length < COUNT) {
    const x = rnd();
    const y = rnd();
    // crowded under a headline is a plate you cannot read.
    const dx = (x - 0.5) * 2;
    const dy = (y - 0.5) * 2;
    const d = Math.sqrt(dx * dx + dy * dy);
    if (d < CLEAR_RADIUS && rnd() > d / CLEAR_RADIUS) continue;
    const roll = rnd();
    const m = roll > 0.97 ? 5 : roll > 0.9 ? 4 : roll > 0.72 ? 3 : roll > 0.42 ? 2 : 1;
    out.push({
      x,
      y,
      vx: (rnd() - 0.5) * 0.004,
      vy: (rnd() - 0.5) * 0.004,
      m,
      phase: rnd() * Math.PI * 2,
      rate: 0.25 + rnd() * 0.4,
    });
  }
  return out;
}

type Glyph = {
  /** The trace itself. */
  at: (t: number) => number;
  /** Optional marks struck under the trace once it has been drawn. */
  ticks?: number[];
  /** Scatter dots around the trace (phase folds, radial velocity). */
  scatter?: boolean;
  /** A second, counter-phased strand with rungs between (the helix). */
  paired?: boolean;
};

const GLYPHS: Glyph[] = [
  {
    at: (t) => {
      let v = Math.sin(t * 3.1) * 0.12;
      for (const line of [0.22, 0.38, 0.53, 0.71, 0.86]) {
        const d = (t - line) / 0.016;
        v -= Math.exp(-d * d) * 0.85;
      }
      return v;
    },
  },
  {
    at: (t) => {
      const d = (t - 0.5) / 0.13;
      return -Math.exp(-d * d * d * d) * 0.8;
    },
    ticks: [0.5],
  },
  {
    at: (t) => Math.sin(t * Math.PI * 2) * 0.75,
    scatter: true,
  },
  {
    at: (t) => Math.exp(-t * 3.2) * 1.6 - 0.8,
    ticks: [0.216],
  },
  {
    at: (t) => Math.sin(t * Math.PI * 2 - 0.6) * 0.7,
    scatter: true,
  },
  {
    at: (t) => Math.sin(t * Math.PI * 4) * 0.7,
    paired: true,
  },
];

export function ObservatoryField({ className }: { className?: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const readout = useRef<HTMLSpanElement>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const host = wrap.current;
    const cv = canvas.current;
    if (!host || !cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const field = buildField();

    /*
     * Colours live in the token layer, never here — the lint that forbids raw literals
     * in components is also what keeps this correct in both renditions, since
     * re-reading the same four names after a theme change is the whole of dark-mode
     * support for the canvas.
     */
    let ink = "";
    let thread = "";
    const readTokens = () => {
      const s = getComputedStyle(document.documentElement);
      ink = s.getPropertyValue("--mark").trim();
      thread = s.getPropertyValue("--thread").trim();
    };
    readTokens();
    const themeWatch = new MutationObserver(readTokens);
    themeWatch.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    let w = 0;
    let h = 0;
    let short = 0;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = host.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      short = Math.min(w, h);
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const sizeWatch = new ResizeObserver(resize);
    sizeWatch.observe(host);

    /*
     * A coarse pointer has no hover state to speak of, so the measuring engine simply
     * is not offered there rather than being offered and never reachable.
     */
    const fine = window.matchMedia("(pointer: fine)").matches;
    let px = -1;
    let py = -1;
    let sx = -1;
    let sy = -1;
    const onMove = (e: PointerEvent) => {
      const rect = host.getBoundingClientRect();
      px = e.clientX - rect.left;
      py = e.clientY - rect.top;
    };
    const onLeave = () => {
      px = -1;
      py = -1;
    };
    if (fine && !reduced) {
      host.addEventListener("pointermove", onMove);
      host.addEventListener("pointerleave", onLeave);
    }

    let tiltX = 0;
    let tiltY = 0;
    const pos = (o: Obj, t: number) => {
      const depth = o.m / 5;
      return {
        // Proper motion wraps, so the plate never empties at one edge.
        x: ((((o.x + o.vx * t) % 1) + 1) % 1) * w + tiltX * depth,
        y: ((((o.y + o.vy * t) % 1) + 1) % 1) * h + tiltY * depth,
      };
    };

    function drawGlyph(g: Glyph, cx: number, cy: number, span: number, amp: number, drawn: number, alpha: number) {
      if (!ctx || drawn <= 0) return;
      const steps = 120;
      const last = Math.max(1, Math.floor(steps * drawn));
      ctx.globalAlpha = alpha * 0.5;
      ctx.strokeStyle = thread;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i <= last; i++) {
        const t = i / steps;
        const x = cx + t * span;
        const y = cy - g.at(t) * amp;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      if (g.paired) {
        ctx.beginPath();
        for (let i = 0; i <= last; i++) {
          const t = i / steps;
          const x = cx + t * span;
          const y = cy + g.at(t) * amp;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.globalAlpha = alpha * 0.28;
        ctx.beginPath();
        for (let i = 0; i <= last; i += 8) {
          const t = i / steps;
          const x = cx + t * span;
          ctx.moveTo(x, cy - g.at(t) * amp);
          ctx.lineTo(x, cy + g.at(t) * amp);
        }
        ctx.stroke();
      }

      if (g.scatter) {
        ctx.globalAlpha = alpha * 0.4;
        ctx.fillStyle = thread;
        for (let i = 0; i <= last; i += 9) {
          const t = i / steps;
          const jitter = Math.sin(i * 12.9898) * 0.14;
          const x = cx + t * span;
          const y = cy - (g.at(t) + jitter) * amp;
          ctx.beginPath();
          ctx.arc(x, y, 1.1, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = alpha * 0.22;
          ctx.beginPath();
          ctx.moveTo(x, y - amp * 0.12);
          ctx.lineTo(x, y + amp * 0.12);
          ctx.stroke();
          ctx.globalAlpha = alpha * 0.4;
        }
      }

      if (g.ticks && drawn >= 1) {
        ctx.globalAlpha = alpha * 0.45;
        for (const t of g.ticks) {
          const x = cx + t * span;
          ctx.beginPath();
          ctx.moveTo(x, cy + amp * 0.55);
          ctx.lineTo(x, cy + amp * 0.95);
          ctx.stroke();
        }
      }
    }

    let raf = 0;
    let start = 0;
    let running = false;

    const frame = (now: number) => {
      if (!start) start = now;
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, w, h);

      if (px >= 0) {
        sx = sx < 0 ? px : sx + (px - sx) * 0.08;
        sy = sy < 0 ? py : sy + (py - sy) * 0.08;
        tiltX = (sx / w - 0.5) * short * 0.03;
        tiltY = (sy / h - 0.5) * short * 0.02;
      } else {
        tiltX += (0 - tiltX) * 0.05;
        tiltY += (0 - tiltY) * 0.05;
        sx = -1;
        sy = -1;
      }
      const lit = short * 0.16;

      const reach = short * THREAD_REACH;
      ctx.strokeStyle = thread;
      ctx.lineWidth = 0.6;
      for (let i = 0; i < field.length; i++) {
        const a = pos(field[i], t);
        for (let j = i + 1; j < field.length; j++) {
          const b = pos(field[j], t);
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 > reach * reach) continue;
          const near = 1 - Math.sqrt(d2) / reach;
          let gain = 1;
          if (sx >= 0) {
            const md = Math.hypot((a.x + b.x) / 2 - sx, (a.y + b.y) / 2 - sy);
            if (md < lit) gain = 1 + (1 - md / lit) * 2.6;
          }
          ctx.globalAlpha = Math.min(0.55, near * 0.16 * gain);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }

      ctx.fillStyle = ink;
      let nearest = -1;
      let nearestD = Infinity;
      let nx = 0;
      let ny = 0;
      for (let i = 0; i < field.length; i++) {
        const o = field[i];
        const p = pos(o, t);
        const twinkle = 0.72 + Math.sin(t * o.rate + o.phase) * 0.28;
        let r = (R[o.m] * short) / 900;
        let lift = 1;
        if (sx >= 0) {
          const d = Math.hypot(p.x - sx, p.y - sy);
          if (d < lit) {
            const k = 1 - d / lit;
            lift = 1 + k * 1.9;
            r *= 1 + k * 0.5;
          }
          if (d < nearestD) {
            nearestD = d;
            nearest = i;
            nx = p.x;
            ny = p.y;
          }
        }
        ctx.globalAlpha = Math.min(0.85, (o.m >= 4 ? 0.4 : 0.24) * twinkle * lift);
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      }

      const cycle = Math.floor(t / TRANSIENT_EVERY);
      const age = t - cycle * TRANSIENT_EVERY;
      if (age < TRANSIENT_LIFE) {
        const pick = field[(cycle * 37) % field.length];
        const p = pos(pick, t);
        const k = age / TRANSIENT_LIFE;
        const fade = 1 - k;
        ctx.globalAlpha = fade * 0.5;
        ctx.fillStyle = ink;
        ctx.beginPath();
        ctx.arc(p.x, p.y, (R[pick.m] * short) / 900 + 1, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = fade * 0.3;
        ctx.strokeStyle = thread;
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.arc(p.x, p.y, k * short * 0.07, 0, Math.PI * 2);
        ctx.stroke();
      }

      // A signal travels one thread at a time — the connections aren't just
      // static geometry, something is moving through the network.
      const sigCycle = Math.floor(t / SIGNAL_EVERY);
      const sigAge = t - sigCycle * SIGNAL_EVERY;
      if (sigAge < SIGNAL_LIFE) {
        const from = field[(sigCycle * 53) % field.length];
        const fp = pos(from, t);
        let toIdx = -1;
        let toD = Infinity;
        for (let j = 0; j < field.length; j++) {
          if (field[j] === from) continue;
          const q = pos(field[j], t);
          const d = Math.hypot(q.x - fp.x, q.y - fp.y);
          if (d < reach && d < toD) {
            toD = d;
            toIdx = j;
          }
        }
        if (toIdx >= 0) {
          const tp = pos(field[toIdx], t);
          const k = sigAge / SIGNAL_LIFE;
          const ease = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
          const sxp = fp.x + (tp.x - fp.x) * ease;
          const syp = fp.y + (tp.y - fp.y) * ease;
          const fade = Math.sin(k * Math.PI);
          ctx.globalAlpha = fade * 0.75;
          ctx.fillStyle = ink;
          ctx.beginPath();
          ctx.arc(sxp, syp, short * 0.0028 + 1, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      /* Glyphs place at fixed normalized coordinates (cx/cy as a fraction of
       * the field's own w/h), which only stays clear of the header's text
       * column on a roughly desktop aspect ratio — the star field's own
       * CLEAR_RADIUS is a circle from centre and works for a field of tiny
       * points, but a glyph's traced span is a wide horizontal mark, and on
       * a narrow/tall mobile viewport the text column runs nearly edge to
       * edge, not just near centre. w * 0.06 sits in open margin next to a
       * desktop-width column and directly under mobile's full-width prose.
       * Skipping glyphs below the field's own field width breakpoint is
       * simpler and more robust than teaching the canvas the header's exact
       * text rect for a purely decorative flourish. */
      const showGlyphs = w >= 640;
      for (const slot of showGlyphs ? [0, 1] : []) {
        const gt = t + slot * (GLYPH_CYCLE / 2);
        const turn = Math.floor(gt / GLYPH_CYCLE);
        const local = gt - turn * GLYPH_CYCLE;
        const g = GLYPHS[(turn * 2 + slot) % GLYPHS.length];
        let drawn = 0;
        let alpha = 0;
        if (local < GLYPH_DRAW) {
          drawn = local / GLYPH_DRAW;
          alpha = Math.min(1, local / 0.6);
        } else if (local < GLYPH_DRAW + GLYPH_HOLD) {
          drawn = 1;
          alpha = 1;
        } else if (local < GLYPH_DRAW + GLYPH_HOLD + GLYPH_FADE) {
          drawn = 1;
          alpha = 1 - (local - GLYPH_DRAW - GLYPH_HOLD) / GLYPH_FADE;
        }
        if (alpha <= 0) continue;
        const span = short * 0.2;
        const amp = short * 0.035;
        const cx = slot === 0 ? w * 0.06 : w * 0.72;
        const cy = slot === 0 ? h * (0.2 + ((turn % 3) * 0.22)) : h * (0.72 - ((turn % 3) * 0.2));
        drawGlyph(g, cx, cy, span, amp, drawn, alpha);
      }

      if (sx >= 0 && nearest >= 0 && nearestD < short * 0.06) {
        /*
         * Measuring one object and being shown what it cites is the literature graph
         * doing in miniature what the whole product does, which is why this is the
         * page's signature and not the crosshair that frames it.
         */
        const me = pos(field[nearest], t);
        ctx.strokeStyle = thread;
        ctx.lineWidth = 0.8;
        for (let j = 0; j < field.length; j++) {
          if (j === nearest) continue;
          const q = pos(field[j], t);
          const d = Math.hypot(q.x - me.x, q.y - me.y);
          if (d > reach) continue;
          ctx.globalAlpha = (1 - d / reach) * 0.6;
          ctx.beginPath();
          ctx.moveTo(me.x, me.y);
          ctx.lineTo(q.x, q.y);
          ctx.stroke();
          ctx.globalAlpha = (1 - d / reach) * 0.45;
          ctx.beginPath();
          ctx.arc(q.x, q.y, (R[field[j].m] * short) / 900 + 3.5, 0, Math.PI * 2);
          ctx.stroke();
        }

        const box = Math.max(10, (R[field[nearest].m] * short) / 900 + 9);
        ctx.globalAlpha = 0.5;
        ctx.strokeStyle = thread;
        ctx.lineWidth = 0.7;
        ctx.strokeRect(nx - box, ny - box, box * 2, box * 2);
        ctx.globalAlpha = 0.28;
        ctx.beginPath();
        ctx.moveTo(0, ny);
        ctx.lineTo(nx - box, ny);
        ctx.moveTo(nx + box, ny);
        ctx.lineTo(w, ny);
        ctx.moveTo(nx, 0);
        ctx.lineTo(nx, ny - box);
        ctx.moveTo(nx, ny + box);
        ctx.lineTo(nx, h);
        ctx.stroke();
        const el = readout.current;
        if (el) {
          el.style.opacity = "1";
          el.style.transform = `translate(${nx + box + 6}px, ${ny - box}px)`;
          // The magnitude, and what it means in the app's own words — the
          // same reading the grounding marks carry in the conversation.
          el.textContent = `mag ${field[nearest].m}`;
        }
      } else if (readout.current) {
        readout.current.style.opacity = "0";
      }

      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(frame);
    };

    const stop = () => {
      if (!running) return;
      running = false;
      cancelAnimationFrame(raf);
    };
    const go = () => {
      if (running || reduced) return;
      running = true;
      // Resume where the field left off rather than snapping back to frame
      // zero: a plate that jumps when you return to the tab reads as a fault.
      start = performance.now() - (start ? performance.now() - start : 0);
      raf = requestAnimationFrame(frame);
    };

    if (reduced) {
      // One settled frame, and no loop at all. The field is still a field;
      // it simply is not tracking.
      start = performance.now();
      frame(start);
      cancelAnimationFrame(raf);
    } else {
      const onVis = () => (document.hidden ? stop() : go());
      document.addEventListener("visibilitychange", onVis);
      const seen = new IntersectionObserver(
        ([e]) => (e.isIntersecting ? go() : stop()),
        { threshold: 0 },
      );
      seen.observe(host);
      return () => {
        stop();
        document.removeEventListener("visibilitychange", onVis);
        seen.disconnect();
        sizeWatch.disconnect();
        themeWatch.disconnect();
        host.removeEventListener("pointermove", onMove);
        host.removeEventListener("pointerleave", onLeave);
      };
    }

    return () => {
      stop();
      sizeWatch.disconnect();
      themeWatch.disconnect();
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
    };
  }, [reduced]);

  return (
    <div ref={wrap} className={className} aria-hidden>
      {/* The graticule is CSS, and it reuses the app's own tracked-field drift
        * rather than inventing a second one: one cell of travel over one full
        * cycle, so the rule never shows a seam. */}
      <div className="plate-graticule field-drift absolute inset-0" />
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" />
      {/* The magnitude readout is DOM, not canvas text, so it is set in the
        * app's own measurement voice instead of a font string invented here. */}
      <span
        ref={readout}
        className="type-quantity pointer-events-none absolute left-0 top-0 text-text-muted opacity-0 transition-opacity duration-fast"
      />
      {/* The vignette is what keeps "bold" from becoming "loud": density falls
        * away under the type, so the field is felt around the headline rather
        * than read through it. */}
      <div className="plate-vignette absolute inset-0" />
    </div>
  );
}
