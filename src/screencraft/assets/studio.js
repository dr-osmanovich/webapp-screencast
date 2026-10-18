/* screencraft runtime — real footage on a wallpaper stage with a spring camera and a replayed cursor.
   Everything is a pure function of time: camera and cursor samples are precomputed at 60 fps from the
   event log (window.TAKE) and read back by one proxy tween on the paused main timeline, so any seek
   order renders identical frames. Driven by window.SC (resolved plan from `screencraft compose`). */
(function () {
  const T = window.TAKE, SC = window.SC;
  const EV = T.events;
  const moves = EV.filter((e) => e.type === "move" || e.type === "down" || e.type === "up");
  const downs = EV.filter((e) => e.type === "down");
  const W = SC.canvas.width, H = SC.canvas.height;
  const ST = SC.stage;                       // {x, y, w, h} on the canvas; footage maps onto it
  const SS = ST.w / T.css_viewport.width;    // footage px -> stage px
  const FPS = 60;
  const V0 = SC.video_start, MS = SC.media_start;
  const toF = (tc) => MS + (tc - V0);        // comp time -> footage time
  const toC = (tf) => V0 + (tf - MS);

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const mix = (a, b, u) => a + (b - a) * u;
  const easeOut = gsap.parseEase("power2.out");

  function cursorAt(tf) {
    if (!moves.length) return { x: T.css_viewport.width / 2, y: T.css_viewport.height / 2 };
    if (tf <= moves[0].t) return { x: moves[0].x, y: moves[0].y };
    for (let i = 1; i < moves.length; i++) {
      if (tf <= moves[i].t) {
        const a = moves[i - 1], b = moves[i], u = (tf - a.t) / Math.max(1e-6, b.t - a.t);
        return { x: mix(a.x, b.x, u), y: mix(a.y, b.y, u) };
      }
    }
    const l = moves[moves.length - 1]; return { x: l.x, y: l.y };
  }
  function focusPoint(seg, tf) {
    const f = seg.focus;
    if (f === "cursor") return cursorAt(tf);
    if (f === "center" || f == null) return { x: T.css_viewport.width / 2, y: T.css_viewport.height / 2 };
    if (Array.isArray(f)) return { x: f[0], y: f[1] };
    return f;
  }
  const toWorld = (p) => ({ x: ST.x + p.x * SS, y: ST.y + p.y * SS });

  function mountCamera(tl) {
    const segs = (SC.camera && SC.camera.length ? SC.camera : [{ from: -1e9, zoom: 1, focus: "center" }])
      .slice().sort((a, b) => a.from - b.from);
    const segAt = (tf) => { let s = segs[0]; for (const g of segs) if (tf >= g.from) s = g; return s; };
    const t0c = V0 - 0.5, t1c = toC(SC.video_end) + 0.5;
    const n = Math.ceil((t1c - t0c) * FPS) + 2, SUB = 4, dt = 1 / (FPS * SUB);
    const OF = SC.look.focus_omega || 5.2, OZ = SC.look.zoom_omega || 4.2;   // critically damped springs
    const first = segAt(toF(t0c));
    let fx = toWorld(focusPoint(first, toF(t0c))), vx = 0, vy = 0, vz = 0, z = first.zoom;
    const cam = new Array(n);
    for (let i = 0; i < n; i++) {
      cam[i] = { x: fx.x, y: fx.y, z };
      for (let j = 0; j < SUB; j++) {
        const tf = toF(t0c + (i * SUB + j) * dt), s = segAt(tf), aim = toWorld(focusPoint(s, tf));
        vx += (OF * OF * (aim.x - fx.x) - 2 * OF * vx) * dt;
        vy += (OF * OF * (aim.y - fx.y) - 2 * OF * vy) * dt;
        fx = { x: fx.x + vx * dt, y: fx.y + vy * dt };
        vz += (OZ * OZ * (s.zoom - z) - 2 * OZ * vz) * dt;
        z += vz * dt;
      }
    }
    const camAt = (tc) => {
      const p = clamp((tc - t0c) * FPS, 0, n - 2), i = Math.floor(p), u = p - i, a = cam[i], b = cam[i + 1];
      return { x: mix(a.x, b.x, u), y: mix(a.y, b.y, u), z: mix(a.z, b.z, u) };
    };
    const world = document.getElementById("sc-world"), cur = document.getElementById("sc-cur");
    const curSvg = cur.querySelector("svg"), ring = cur.querySelector(".ring");
    const cursorEnd = SC.cursor_end == null ? Infinity : SC.cursor_end;
    const ringMax = SC.look.ring_radius || 54;
    function render(tc) {
      const c = camAt(tc), zz = Math.max(1, c.z), hw = W / (2 * zz), hh = H / (2 * zz);
      const cx = clamp(c.x, hw, W - hw), cy = clamp(c.y, hh, H - hh);   // keep the world covering the canvas
      world.style.transform = `translate(${(W / 2 - cx * zz).toFixed(2)}px, ${(H / 2 - cy * zz).toFixed(2)}px) scale(${zz.toFixed(4)})`;
      const tf = toF(tc), p = cursorAt(tf);
      const live = tf >= 0 && tf <= cursorEnd;
      const fade = live ? clamp(tf / 0.3, 0, 1) * clamp((cursorEnd - tf) / 0.3, 0, 1) : 0;
      cur.style.opacity = fade.toFixed(3);
      cur.style.transform = `translate(${(p.x - 6).toFixed(2)}px, ${(p.y - 4).toFixed(2)}px)`;
      let press = 0, ringU = -1;
      for (const d of downs) { const s = tf - d.t; if (s >= 0 && s < 0.5) { press = s < 0.08 ? s / 0.08 : Math.max(0, 1 - (s - 0.08) / 0.2); ringU = s / 0.5; } }
      curSvg.style.transform = press > 0 ? `scale(${(1 - 0.12 * press).toFixed(3)})` : "";
      if (ringU >= 0) {
        const r = 10 + (ringMax - 10) * easeOut(ringU);
        ring.style.width = ring.style.height = (r * 2).toFixed(1) + "px";
        ring.style.opacity = (0.85 * (1 - ringU)).toFixed(3);
      } else ring.style.opacity = "0";
    }
    const proxy = { t: t0c };
    tl.to(proxy, { t: t1c, duration: t1c - t0c, ease: "none", onUpdate: () => render(proxy.t) }, t0c);
    render(t0c);
  }

  function mountSubs(tl) {
    const box = document.getElementById("sc-subs");
    (SC.subtitles || []).forEach(([start, end, text], i) => {
      const el = document.createElement("div");
      el.className = "sc-sub"; el.id = "sc-sub-" + i; el.textContent = text; box.appendChild(el);
      tl.fromTo(el, { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.25, ease: "power2.out" }, start);
      tl.to(el, { opacity: 0, duration: 0.2, ease: "power1.in" }, Math.max(start + 0.3, end - 0.2));
    });
  }

  function mountCards(tl) {
    if (SC.intro) {
      const d = SC.intro.duration;
      tl.fromTo("#sc-intro .t1", { opacity: 0, y: 26 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 0.05);
      tl.fromTo("#sc-intro .t2", { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }, 0.3);
      tl.to("#sc-intro", { opacity: 0, duration: 0.4, ease: "power2.inOut" }, d - 0.4);
    }
    if (SC.outro) {
      const O = SC.outro.start;
      tl.fromTo("#sc-outro", { opacity: 0 }, { opacity: 1, duration: 0.45, ease: "power2.inOut" }, O);
      tl.fromTo("#sc-outro .mark", { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.6, ease: "back.out(1.4)" }, O + 0.15);
      tl.fromTo("#sc-outro .line", { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }, O + 0.5);
    }
  }

  function mountAnnotations(tl) {
    const fx = document.getElementById("sc-fx");
    (SC.callouts || []).forEach((c, i) => {
      const el = document.createElement("div");
      el.className = "sc-callout " + (c.side || "below"); el.id = "sc-callout-" + i; el.innerHTML = c.html;
      el.style.left = c.x + "px"; el.style.top = c.y + "px";
      if ((c.side || "below") === "left") el.style.transform = "translateY(-50%)";
      fx.appendChild(el);
      const tc = toC(c.at);
      tl.fromTo(el, { opacity: 0, x: c.side === "left" ? -14 : 0, y: c.side === "left" ? 0 : -10 },
                    { opacity: 1, x: 0, y: 0, duration: 0.4, ease: "power3.out" }, tc);
      if (c.until != null) tl.to(el, { opacity: 0, duration: 0.25 }, toC(c.until));
    });
    (SC.halos || []).forEach((h, i) => {
      const el = document.createElement("div"), pad = h.pad == null ? 10 : h.pad, b = h.box;
      el.className = "sc-halo"; el.id = "sc-halo-" + i;
      el.style.left = (b.x - pad) + "px"; el.style.top = (b.y - pad) + "px";
      el.style.width = (b.w + 2 * pad) + "px"; el.style.height = (b.h + 2 * pad) + "px";
      fx.appendChild(el);
      const tc = toC(h.at);
      tl.fromTo(el, { opacity: 0, scale: 0.6 }, { opacity: 0.9, scale: 1, duration: 0.35, ease: "power2.out" }, tc);
      tl.to(el, { scale: 1.25, opacity: 0, duration: 0.9, ease: "power2.out" }, tc + 0.35);
      tl.fromTo(el, { opacity: 0, scale: 0.9 }, { opacity: 0.9, scale: 1, duration: 0.3 }, tc + 1.3);
      tl.to(el, { scale: 1.25, opacity: 0, duration: 0.9, ease: "power2.out" }, tc + 1.6);
    });
  }

  window.Studio = {
    mount(tl) { mountCamera(tl); mountSubs(tl); mountCards(tl); mountAnnotations(tl); return tl; },
    cursorAt, toC, toF,
  };
})();
