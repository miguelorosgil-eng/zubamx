import { Audio, staticFile } from "remotion";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";

export const ZubaAdSchema = z.object({
  hook: z.enum(["pain", "mecanismo", "riesgo"]),
});
type Props = z.infer<typeof ZubaAdSchema>;

// ── Design System — Apple tokens + ZUBA brand ─────────────────────────────────
const C = {
  black:       "#000000",
  white:       "#FFFFFF",
  offWhite:    "#F5F5F7",  // Apple
  textPrimary: "#1D1D1F",  // Apple
  textSecond:  "#6E6E73",  // Apple secondary
  orange:      "#FF6B35",  // ZUBA
  orangeDeep:  "#E8521F",
  green:       "#25D366",
};
const R = 980; // Apple pill radius
const font = '"SF Pro Display","SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif';

// ── Caption timing per hook (frames, 30fps) ───────────────────────────────────
const CAPTIONS: Record<string, { text: string; from: number; to: number }[]> = {
  pain: [
    { text: "¿Tu restaurante está en Uber Eats, Rappi o DiDi Food…",  from: 4,   to: 105 },
    { text: "y casi no te llegan pedidos?",                            from: 100, to: 175 },
    { text: "El problema no es tu comida.",                            from: 170, to: 240 },
    { text: "Es cómo te ve el algoritmo.",                             from: 235, to: 315 },
    { text: "ZUBA optimiza los 5 factores clave.",                     from: 310, to: 400 },
    { text: "Si no creces… no cobramos.",                              from: 395, to: 510 },
  ],
  mecanismo: [
    { text: "El algoritmo de Uber Eats, Rappi y DiDi Food…",          from: 4,   to: 110 },
    { text: "decide quién vende, y quién no.",                         from: 105, to: 185 },
    { text: "Premia 5 cosas exactas.",                                 from: 180, to: 255 },
    { text: "Si fallas en una, quedas abajo.",                         from: 250, to: 335 },
    { text: "ZUBA los optimiza todos por ti.",                         from: 330, to: 415 },
    { text: "Si no creces… no cobramos.",                              from: 410, to: 510 },
  ],
  riesgo: [
    { text: "¿Cuánto llevas perdiendo en Uber Eats, Rappi y DiDi?",   from: 4,   to: 115 },
    { text: "sin ver resultados reales?",                              from: 110, to: 185 },
    { text: "El problema siempre es el mismo:",                        from: 180, to: 255 },
    { text: "operación mal configurada.",                              from: 250, to: 330 },
    { text: "ZUBA lo arregla todo.",                                   from: 325, to: 405 },
    { text: "Si no creces… no pagas.",                                 from: 400, to: 510 },
  ],
};

// ── Animation helpers ─────────────────────────────────────────────────────────
const inOut = (frame: number, inF: number, outF: number, d = 20) => {
  const i = interpolate(frame, [inF, inF + d], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const o = interpolate(frame, [outF, outF + d], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 1, 1),
  });
  return Math.min(i, o);
};

const reveal = (frame: number, startAt: number, fps: number) => {
  const p = spring({ fps, frame: frame - startAt, config: { damping: 32, stiffness: 72 }, durationInFrames: 55 });
  return {
    opacity:   interpolate(p, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 1], [28, 0])}px) scale(${interpolate(p, [0, 1], [0.97, 1])})`,
  };
};

const sceneOp = (frame: number, inF: number, outF: number) =>
  inOut(frame, inF, outF, 22);

// ── Caption bar ───────────────────────────────────────────────────────────────
const Caption: React.FC<{ hook: string; frame: number }> = ({ hook, frame }) => {
  const all = CAPTIONS[hook] ?? [];
  const active = all.find(c => frame >= c.from && frame <= c.to + 10);
  if (!active) return null;
  const op = inOut(frame, active.from, active.to, 18);
  return (
    <div style={{
      position: "absolute", bottom: 200, left: 0, right: 0,
      display: "flex", justifyContent: "center",
      pointerEvents: "none", opacity: op,
    }}>
      <div style={{
        background: "rgba(0,0,0,0.78)",
        backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)",
        borderRadius: R, padding: "13px 36px", maxWidth: 820,
      }}>
        <span style={{
          fontFamily: font, fontWeight: 500, fontSize: 30,
          color: C.white, letterSpacing: 0.1, lineHeight: 1.35,
        }}>{active.text}</span>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 1 — HOOK  (0–150f)
// Apple: one giant question. Pure black. Nothing else.
// ─────────────────────────────────────────────────────────────────────────────
const HOOK_LINES: Record<string, [string, string, string]> = {
  pain:      ["¿Por qué tu",   "restaurante",  "no vende?"],
  mecanismo: ["El algoritmo",  "decide",       "quién gana."],
  riesgo:    ["¿Cuánto llevas", "perdiendo",   "en apps?"],
};

const SceneHook: React.FC<{ hook: string; frame: number; fps: number }> = ({ hook, frame, fps }) => {
  const [l1, l2, l3] = HOOK_LINES[hook];
  return (
    <AbsoluteFill style={{ background: C.black }}>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "0 56px",
        gap: 4,
      }}>
        {/* Platform pill */}
        <div style={{
          ...reveal(frame, 0, fps),
          marginBottom: 36,
          background: "rgba(255,107,53,0.12)",
          border: "1px solid rgba(255,107,53,0.3)",
          borderRadius: R, padding: "10px 28px",
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: C.orange }} />
          <span style={{ fontFamily: font, fontWeight: 600, fontSize: 24, color: C.orange, letterSpacing: 0.4, textTransform: "uppercase" }}>
            Uber Eats · Rappi · DiDi Food
          </span>
        </div>

        {/* Giant hook — each line is one word / phrase */}
        <div style={{ textAlign: "center", lineHeight: 1.0 }}>
          <div style={{ ...reveal(frame, 10, fps), fontFamily: font, fontWeight: 800, fontSize: 118, color: C.white, letterSpacing: -4 }}>
            {l1}
          </div>
          <div style={{ ...reveal(frame, 22, fps), fontFamily: font, fontWeight: 900, fontSize: 134, letterSpacing: -5,
            background: `linear-gradient(135deg, ${C.orange} 10%, ${C.orangeDeep} 90%)`,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            {l2}
          </div>
          <div style={{ ...reveal(frame, 34, fps), fontFamily: font, fontWeight: 800, fontSize: 118, color: C.white, letterSpacing: -4 }}>
            {l3}
          </div>
        </div>

        {/* Thin orange rule */}
        <div style={{
          ...reveal(frame, 52, fps),
          marginTop: 32,
          height: 3, borderRadius: 2, width: 88,
          background: C.orange,
        }} />
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 2 — ALGORITMO  (150–330f)
// Apple: giant "5" as hero number, then list builds below it.
// ─────────────────────────────────────────────────────────────────────────────
const FACTORS = ["Rating y reseñas", "Fotografía", "Menú estratégico", "Horarios y disponibilidad", "Pauta interna"];

const SceneAlgo: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 150;

  // "5" shrinks up as the list appears
  const listProgress = interpolate(f, [50, 100], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const bigFiveSize  = interpolate(listProgress, [0, 1], [320, 120], { easing: Easing.bezier(0.4, 0, 0.2, 1) });
  const bigFiveY     = interpolate(listProgress, [0, 1], [0, -200]);

  return (
    <AbsoluteFill style={{ background: C.black }}>
      {/* Faint orange halo behind the 5 */}
      <div style={{
        position: "absolute", top: "28%", left: "50%",
        transform: "translate(-50%,-50%)",
        width: 700, height: 700, borderRadius: "50%",
        background: `radial-gradient(circle, ${C.orange}22 0%, transparent 65%)`,
        opacity: interpolate(listProgress, [0, 1], [1, 0]),
        pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "0 64px",
      }}>
        {/* Hero "5" */}
        <div style={{
          ...reveal(f, 0, fps),
          transform: `${reveal(f, 0, fps).transform} translateY(${bigFiveY}px)`,
          fontFamily: font, fontWeight: 900, fontSize: bigFiveSize,
          letterSpacing: -8, lineHeight: 1,
          background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDeep})`,
          WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          marginBottom: 8,
        }}>5</div>

        {/* "factores que el algoritmo premia" — appears as 5 fades */}
        <div style={{
          opacity: interpolate(listProgress, [0.2, 0.7], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          transform: `translateY(${interpolate(listProgress, [0.2, 0.7], [20, 0])}px)`,
          fontFamily: font, fontWeight: 300, fontSize: 34,
          color: C.textSecond, textAlign: "center", marginBottom: 44, letterSpacing: -0.3,
        }}>
          factores que el algoritmo premia
        </div>

        {/* List — Apple table style: dividers only, no cards */}
        <div style={{
          opacity: listProgress,
          width: "100%",
          display: "flex", flexDirection: "column",
        }}>
          {FACTORS.map((f2, i) => {
            const itemOp = interpolate(
              spring({ fps, frame: f - (65 + i * 14), config: { damping: 28, stiffness: 85 }, durationInFrames: 40 }),
              [0, 0.3], [0, 1], { extrapolateRight: "clamp" }
            );
            return (
              <div key={f2} style={{
                opacity: itemOp,
                transform: `translateX(${interpolate(itemOp, [0, 1], [-24, 0])}px)`,
                display: "flex", alignItems: "center",
                borderTop: `1px solid rgba(255,255,255,0.09)`,
                padding: "22px 0",
              }}>
                <span style={{
                  fontFamily: font, fontWeight: 700, fontSize: 26,
                  color: C.orange, minWidth: 36, letterSpacing: 0.5,
                }}>0{i + 1}</span>
                <span style={{
                  fontFamily: font, fontWeight: 500, fontSize: 38,
                  color: C.offWhite, letterSpacing: -0.5,
                }}>{f2}</span>
                <div style={{
                  marginLeft: "auto", fontSize: 22,
                  color: "rgba(255,80,40,0.5)",
                }}>✕</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 3 — SOLUCIÓN  (330–480f)
// Apple: white bg, brand mark top-left, giant statement, clean steps.
// ─────────────────────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Diagnóstico" },
  { n: "02", title: "Fotografía" },
  { n: "03", title: "Menú estratégico" },
  { n: "04", title: "Activación" },
  { n: "05", title: "Pauta interna" },
];

const SceneSolution: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 330;
  return (
    <AbsoluteFill style={{ background: C.white }}>
      {/* Very faint warm tint top-right — Apple product page style */}
      <div style={{
        position: "absolute", top: -200, right: -200, width: 800, height: 800,
        borderRadius: "50%",
        background: `radial-gradient(circle, rgba(255,107,53,0.08) 0%, transparent 65%)`,
        pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        padding: "130px 68px 220px",
        justifyContent: "center",
        gap: 0,
      }}>
        {/* ZUBA logotype */}
        <div style={{ ...reveal(f, 0, fps), display: "flex", alignItems: "center", gap: 18, marginBottom: 40 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 18,
            background: `linear-gradient(145deg, ${C.orange}, ${C.orangeDeep})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 8px 24px rgba(255,107,53,0.35)`,
          }}>
            <span style={{ fontFamily: font, fontWeight: 900, fontSize: 32, color: C.white }}>Z</span>
          </div>
          <div>
            <div style={{ fontFamily: font, fontWeight: 900, fontSize: 42, color: C.textPrimary, letterSpacing: -1.5, lineHeight: 1 }}>ZUBA</div>
            <div style={{ fontFamily: font, fontWeight: 400, fontSize: 20, color: C.textSecond, letterSpacing: 0 }}>Consultoría de operación</div>
          </div>
        </div>

        {/* Giant statement — Apple product hero style */}
        <div style={{ marginBottom: 48 }}>
          <div style={{
            ...reveal(f, 14, fps),
            fontFamily: font, fontWeight: 800, fontSize: 88,
            color: C.textPrimary, lineHeight: 1.0, letterSpacing: -4,
          }}>
            No es marketing.
          </div>
          <div style={{
            ...reveal(f, 26, fps),
            fontFamily: font, fontWeight: 900, fontSize: 88,
            lineHeight: 1.0, letterSpacing: -4,
            background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDeep})`,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>
            Es operación.
          </div>
        </div>

        {/* 5 steps — Apple table/list style, hairline dividers */}
        <div style={{ borderBottom: "1px solid rgba(0,0,0,0.08)" }}>
          {STEPS.map((s, i) => {
            const op = spring({ fps, frame: f - (44 + i * 13), config: { damping: 28, stiffness: 80 }, durationInFrames: 40 });
            const itemOp = interpolate(op, [0, 0.3], [0, 1], { extrapolateRight: "clamp" });
            return (
              <div key={s.n} style={{
                opacity: itemOp,
                transform: `translateX(${interpolate(itemOp, [0, 1], [-20, 0])}px)`,
                display: "flex", alignItems: "center", gap: 22,
                borderTop: "1px solid rgba(0,0,0,0.08)",
                padding: "18px 0",
              }}>
                <span style={{ fontFamily: font, fontWeight: 800, fontSize: 24, color: C.orange, minWidth: 32 }}>{s.n}</span>
                <span style={{ fontFamily: font, fontWeight: 500, fontSize: 34, color: C.textPrimary, letterSpacing: -0.3, flex: 1 }}>
                  {s.title}
                </span>
                {i === 0 && (
                  <div style={{
                    background: C.orange, borderRadius: R, padding: "6px 20px",
                    fontFamily: font, fontWeight: 700, fontSize: 20, color: C.white,
                  }}>Inicio</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 4 — CTA  (480–600f)
// Apple: pure black, giant guarantee, one big pill CTA.
// ─────────────────────────────────────────────────────────────────────────────
const SceneCTA: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 480;
  const breathe = 1 + 0.012 * Math.sin(f * 0.1);

  return (
    <AbsoluteFill style={{ background: C.black }}>
      {/* Center halo */}
      <div style={{
        position: "absolute", top: "38%", left: "50%",
        transform: "translate(-50%,-50%)",
        width: 900, height: 700, borderRadius: "50%",
        background: `radial-gradient(ellipse, rgba(255,107,53,0.16) 0%, transparent 60%)`,
        pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "140px 60px 250px",
        gap: 0,
      }}>
        {/* Giant guarantee */}
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{
            ...reveal(f, 0, fps),
            fontFamily: font, fontWeight: 900, fontSize: 116,
            color: C.white, lineHeight: 0.95, letterSpacing: -5,
          }}>Si no creces,</div>
          <div style={{
            ...reveal(f, 14, fps),
            fontFamily: font, fontWeight: 900, fontSize: 116,
            lineHeight: 0.95, letterSpacing: -5,
            background: `linear-gradient(135deg, ${C.orange} 0%, ${C.orangeDeep} 100%)`,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>no cobramos.</div>
        </div>

        {/* Sub */}
        <div style={{
          ...reveal(f, 28, fps),
          fontFamily: font, fontWeight: 300, fontSize: 32,
          color: "rgba(255,255,255,0.48)", textAlign: "center",
          lineHeight: 1.55, maxWidth: 720, marginBottom: 64,
          letterSpacing: 0,
        }}>
          Operación técnica completa en{" "}
          <span style={{ color: C.offWhite, fontWeight: 500 }}>Uber Eats, Rappi y DiDi Food.</span>
        </div>

        {/* Apple-style pill CTA — full width, green */}
        <div style={{
          ...reveal(f, 44, fps),
          transform: `${reveal(f, 44, fps).transform} scale(${breathe})`,
          width: "100%",
          background: C.green,
          borderRadius: R, padding: "40px 56px",
          display: "flex", alignItems: "center", justifyContent: "center", gap: 20,
          boxShadow: `0 0 80px rgba(37,211,102,0.42)`,
          marginBottom: 24,
        }}>
          <svg width="42" height="42" viewBox="0 0 24 24" fill="white">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          <span style={{ fontFamily: font, fontWeight: 800, fontSize: 46, color: C.white, letterSpacing: -0.8 }}>
            Auditoría gratis →
          </span>
        </div>

        <div style={{
          ...reveal(f, 65, fps),
          fontFamily: font, fontWeight: 300, fontSize: 22,
          color: "rgba(255,255,255,0.2)", letterSpacing: 5, textTransform: "uppercase",
        }}>
          zubamx.vercel.app
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Main ──────────────────────────────────────────────────────────────────────
export const ZubaAd: React.FC<Props> = ({ hook }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s1 = sceneOp(frame, 0,   108);
  const s2 = sceneOp(frame, 118, 312);
  const s3 = sceneOp(frame, 322, 462);
  const s4 = sceneOp(frame, 470, 720);

  const musicVol = interpolate(frame, [0, 45, 555, 600], [0, 0.12, 0.12, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: C.black }}>
      <Audio src={staticFile("bg-music.mp3")} volume={musicVol} loop />
      <Audio src={staticFile(`vo-${hook}.mp3`)} volume={1} />

      <AbsoluteFill style={{ opacity: s1 }}><SceneHook   hook={hook} frame={frame} fps={fps} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s2 }}><SceneAlgo   frame={frame} fps={fps} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s3 }}><SceneSolution frame={frame} fps={fps} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s4 }}><SceneCTA    frame={frame} fps={fps} /></AbsoluteFill>

      <Caption hook={hook} frame={frame} />
    </AbsoluteFill>
  );
};
