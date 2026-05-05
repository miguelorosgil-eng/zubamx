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

// ── Brand ─────────────────────────────────────────────────────────────────────
const C = {
  black: "#000000",
  nearBlack: "#0A0A0A",
  white: "#FFFFFF",
  offWhite: "#F5F5F7",
  cream: "#FBF7F4",
  orange: "#FF6B35",
  orangeWarm: "#FF8C42",
  gray: "#86868B",
  darkGray: "#1D1D1F",
  green: "#25D366",
};
const font =
  '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif';

// ── Voiceover scripts (regenerated — shorter, punchier) ───────────────────────
// pain:      "¿Tu restaurante está en Uber Eats o Rappi y no te llegan pedidos?
//             No es tu comida. Es cómo te ve el algoritmo.
//             ZUBA optimiza los 5 factores clave.
//             Si no creces, no cobramos."
//
// mecanismo: "El algoritmo de Uber Eats y Rappi decide quién vende y quién no.
//             Premia 5 cosas exactas. Si fallas en una, quedas abajo.
//             ZUBA los optimiza todos por ti.
//             Si no creces, no cobramos."
//
// riesgo:    "¿Cuánto llevas perdiendo en apps sin resultados?
//             El problema siempre es el mismo: operación mal configurada.
//             ZUBA lo arregla todo.
//             Con garantía: si no creces, no pagas."

// ── Caption timing per hook (frames at 30fps) ─────────────────────────────────
// Sync these to match the voiceover phrases
const CAPTIONS: Record<Props["hook"], { text: string; from: number; to: number }[]> = {
  pain: [
    { text: "¿Tu restaurante está en Uber Eats o Rappi", from: 5,   to: 95  },
    { text: "y no te llegan pedidos?",                  from: 90,  to: 155 },
    { text: "No es tu comida.",                          from: 150, to: 205 },
    { text: "Es cómo te ve el algoritmo.",               from: 200, to: 275 },
    { text: "ZUBA optimiza los 5 factores clave.",       from: 270, to: 355 },
    { text: "Si no creces, no cobramos.",                from: 350, to: 440 },
  ],
  mecanismo: [
    { text: "El algoritmo decide quién vende y quién no.", from: 5,   to: 110 },
    { text: "Premia 5 cosas exactas.",                     from: 105, to: 170 },
    { text: "Si fallas en una, quedas abajo.",             from: 165, to: 250 },
    { text: "ZUBA los optimiza todos por ti.",             from: 245, to: 330 },
    { text: "Si no creces, no cobramos.",                  from: 325, to: 420 },
  ],
  riesgo: [
    { text: "¿Cuánto llevas perdiendo en apps?",         from: 5,   to: 90  },
    { text: "Siempre el mismo problema:",                 from: 85,  to: 150 },
    { text: "operación mal configurada.",                  from: 145, to: 220 },
    { text: "ZUBA lo arregla todo.",                      from: 215, to: 290 },
    { text: "Si no creces, no pagas.",                    from: 285, to: 380 },
  ],
};

// ── Utils ─────────────────────────────────────────────────────────────────────
const spr = (frame: number, from: number, fps: number, d = 20, s = 80) =>
  spring({ fps, frame: frame - from, config: { damping: d, stiffness: s }, durationInFrames: 50 });

const ease = (frame: number, from: number, to: number, easeIn = false) =>
  interpolate(frame, [from, to], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeIn ? Easing.bezier(0.4, 0, 1, 1) : Easing.bezier(0.16, 1, 0.3, 1),
  });

// Word-by-word spring reveal
function wordEnter(frame: number, startAt: number, fps: number) {
  const p = spr(frame, startAt, fps, 28, 90);
  return {
    opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 1], [30, 0])}px)`,
    display: "inline-block",
  };
}

// Scene cross-fade
function blend(frame: number, inF: number, outF: number, fadeLen = 25) {
  const i = ease(frame, inF, inF + fadeLen);
  const o = ease(frame, outF, outF + fadeLen, true);
  return Math.max(0, i - o);
}

// ── Caption component ─────────────────────────────────────────────────────────
const CaptionBar: React.FC<{ hook: Props["hook"]; frame: number }> = ({ hook, frame }) => {
  const caps = CAPTIONS[hook];
  const active = caps.find((c) => frame >= c.from && frame <= c.to);
  if (!active) return null;

  const progress = ease(frame, active.from, active.from + 20);
  const fadeOut = ease(frame, active.to - 15, active.to);
  const opacity = Math.max(0, progress - fadeOut);

  return (
    <div style={{
      position: "absolute",
      bottom: 210,
      left: 0, right: 0,
      padding: "0 60px",
      textAlign: "center",
      opacity,
      transform: `translateY(${interpolate(progress, [0, 1], [14, 0])}px)`,
      pointerEvents: "none",
    }}>
      <div style={{
        display: "inline-block",
        background: "rgba(0,0,0,0.72)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderRadius: 16,
        padding: "14px 28px",
      }}>
        <span style={{
          fontFamily: font,
          fontSize: 32,
          fontWeight: 500,
          color: C.offWhite,
          letterSpacing: 0.2,
          lineHeight: 1.3,
        }}>
          {active.text}
        </span>
      </div>
    </div>
  );
};

// ── WordReveal ─────────────────────────────────────────────────────────────────
const WordReveal: React.FC<{
  text: string;
  frame: number;
  fps: number;
  startAt: number;
  fontSize: number;
  color?: string;
  accentWord?: string;
  accentColor?: string;
  stagger?: number;
  weight?: number;
  align?: "left" | "center";
}> = ({
  text, frame, fps, startAt, fontSize, color = C.white,
  accentWord, accentColor = C.orange, stagger = 10, weight = 700, align = "center",
}) => {
  const words = text.split(" ");
  return (
    <div style={{
      fontFamily: font,
      fontSize,
      fontWeight: weight,
      lineHeight: 1.05,
      letterSpacing: fontSize > 80 ? -3.5 : -1,
      textAlign: align,
      display: "flex",
      flexWrap: "wrap",
      gap: fontSize > 100 ? "0 16px" : "0 10px",
      justifyContent: align === "center" ? "center" : "flex-start",
    }}>
      {words.map((word, i) => {
        const isAccent = accentWord && word.replace(/[¿?,!.]/g, "").toLowerCase() === accentWord.toLowerCase();
        return (
          <span
            key={i}
            style={{
              ...wordEnter(frame, startAt + i * stagger, fps),
              color: isAccent ? accentColor : color,
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// ── Divider line ──────────────────────────────────────────────────────────────
const Line: React.FC<{ frame: number; startAt: number; color?: string }> = ({
  frame, startAt, color = C.orange,
}) => {
  const w = interpolate(spr(frame, startAt, 30, 22, 100), [0, 1], [0, 480], {
    extrapolateRight: "clamp",
  });
  return (
    <div style={{
      height: 3,
      width: w,
      background: `linear-gradient(90deg, ${color}, transparent)`,
      borderRadius: 2,
    }} />
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 1 — HOOK  (0–120f · 4s)  ·  Apple: big single question
// ─────────────────────────────────────────────────────────────────────────────
const HOOK_TEXT = {
  pain:      { l1: "¿Por qué", l2: "tu restaurante", l3: "no vende?" },
  mecanismo: { l1: "El algoritmo", l2: "decide", l3: "quién gana." },
  riesgo:    { l1: "¿Cuánto llevas", l2: "perdiendo", l3: "en apps?" },
};

const SceneHook: React.FC<{ hook: Props["hook"]; frame: number; fps: number }> = ({ hook, frame, fps }) => {
  const t = HOOK_TEXT[hook];
  return (
    <AbsoluteFill style={{ background: C.black, overflow: "hidden" }}>
      {/* Subtle ambient glow */}
      <div style={{
        position: "absolute",
        top: "20%", left: "50%",
        transform: "translate(-50%,-50%)",
        width: 800, height: 800,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${C.orange}18 0%, transparent 65%)`,
        opacity: interpolate(frame, [0, 60], [0, 1], { extrapolateRight: "clamp" }),
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center",
        padding: "140px 64px 240px",
        gap: 0,
      }}>
        {/* Tag */}
        <div style={{
          opacity: ease(frame, 0, 25),
          transform: `translateY(${interpolate(ease(frame, 0, 25), [0, 1], [20, 0])}px)`,
          marginBottom: 48,
          display: "flex", alignItems: "center", gap: 10,
          background: `${C.orange}18`,
          border: `1px solid ${C.orange}35`,
          borderRadius: 100, padding: "10px 24px",
        }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.orange }} />
          <span style={{ fontFamily: font, fontWeight: 600, fontSize: 22, color: C.orange, letterSpacing: 1, textTransform: "uppercase" }}>
            Uber Eats · Rappi · DiDi
          </span>
        </div>

        {/* Big question */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
          <WordReveal text={t.l1} frame={frame} fps={fps} startAt={8} fontSize={96} weight={900} color={C.offWhite} />
          <WordReveal text={t.l2} frame={frame} fps={fps} startAt={20} fontSize={112} weight={900} accentWord={t.l2.split(" ")[0]} accentColor={C.orange} />
          <WordReveal text={t.l3} frame={frame} fps={fps} startAt={32} fontSize={96} weight={900} color={C.offWhite} />
        </div>

        <div style={{ marginTop: 40 }}>
          <Line frame={frame} startAt={55} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 2 — ALGORITMO  (120–270f · 5s)
// ─────────────────────────────────────────────────────────────────────────────
const PROBLEMS = ["Rating", "Fotografía", "Menú", "Horarios", "Pauta interna"];

const SceneAlgo: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 120;

  return (
    <AbsoluteFill style={{ background: C.nearBlack, overflow: "hidden" }}>
      {/* Right-side glow */}
      <div style={{
        position: "absolute", right: -100, top: "30%",
        width: 600, height: 600, borderRadius: "50%",
        background: `radial-gradient(circle, ${C.orange}15 0%, transparent 70%)`,
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center",
        padding: "140px 72px 240px",
        gap: 48,
      }}>
        {/* Statement */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{
            opacity: ease(f, 0, 30),
            transform: `translateY(${interpolate(ease(f, 0, 30), [0, 1], [30, 0])}px)`,
            fontFamily: font, fontWeight: 900, fontSize: 78,
            color: C.offWhite, lineHeight: 1.05, letterSpacing: -2.5,
          }}>
            El algoritmo
          </div>
          <div style={{
            opacity: ease(f, 12, 40),
            transform: `translateY(${interpolate(ease(f, 12, 40), [0, 1], [30, 0])}px)`,
            fontFamily: font, fontWeight: 900, fontSize: 78,
            lineHeight: 1.05, letterSpacing: -2.5,
            color: C.orange,
          }}>
            premia 5 cosas.
          </div>
          <div style={{
            opacity: ease(f, 28, 55),
            fontFamily: font, fontWeight: 300, fontSize: 34,
            color: C.gray, marginTop: 8,
          }}>
            Fallar en una te manda al fondo.
          </div>
        </div>

        {/* 5 factors */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {PROBLEMS.map((p, i) => {
            const op = ease(f, 50 + i * 14, 80 + i * 14);
            return (
              <div key={p} style={{
                opacity: op,
                transform: `translateX(${interpolate(op, [0, 1], [-40, 0])}px)`,
                display: "flex", alignItems: "center", gap: 20,
              }}>
                <div style={{
                  width: 10, height: 10, borderRadius: "50%",
                  background: C.orange,
                  flexShrink: 0,
                  boxShadow: `0 0 12px ${C.orange}80`,
                }} />
                <span style={{
                  fontFamily: font, fontWeight: 500, fontSize: 38,
                  color: C.offWhite, letterSpacing: -0.5,
                }}>{p}</span>
                <div style={{
                  marginLeft: "auto",
                  fontFamily: font, fontWeight: 400, fontSize: 26,
                  color: "rgba(255,60,0,0.5)",
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
// SCENE 3 — ZUBA  (270–450f · 6s)  · white bg, brand reveal
// ─────────────────────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", label: "Diagnóstico" },
  { n: "02", label: "Fotografía" },
  { n: "03", label: "Menú" },
  { n: "04", label: "Activación" },
  { n: "05", label: "Pauta interna" },
];

const SceneZuba: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 270;

  return (
    <AbsoluteFill style={{ background: C.cream, overflow: "hidden" }}>
      {/* Top-right warm glow */}
      <div style={{
        position: "absolute", top: -80, right: -80,
        width: 560, height: 560, borderRadius: "50%",
        background: `radial-gradient(circle, ${C.orange}22 0%, transparent 65%)`,
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center",
        padding: "140px 72px 240px",
        gap: 44,
      }}>
        {/* ZUBA brand stamp */}
        <div style={{
          opacity: ease(f, 0, 30),
          transform: `scale(${interpolate(ease(f, 0, 30), [0, 1], [0.92, 1])})`,
          display: "flex", alignItems: "center", gap: 18,
        }}>
          <div style={{
            width: 68, height: 68, borderRadius: 20,
            background: `linear-gradient(135deg, ${C.orange}, #FF3D00)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 12px 40px ${C.orange}50`,
          }}>
            <span style={{ color: C.white, fontFamily: font, fontWeight: 900, fontSize: 34 }}>Z</span>
          </div>
          <div>
            <div style={{ fontFamily: font, fontWeight: 900, fontSize: 44, color: C.darkGray, letterSpacing: -1 }}>ZUBA</div>
            <div style={{ fontFamily: font, fontWeight: 400, fontSize: 22, color: C.gray, letterSpacing: 0.5 }}>Consultoría de operación</div>
          </div>
        </div>

        {/* Big statement */}
        <div style={{
          opacity: ease(f, 15, 45),
          transform: `translateY(${interpolate(ease(f, 15, 45), [0, 1], [28, 0])}px)`,
        }}>
          <div style={{ fontFamily: font, fontWeight: 900, fontSize: 80, color: C.darkGray, lineHeight: 1.0, letterSpacing: -3 }}>
            No es marketing.
          </div>
          <div style={{
            fontFamily: font, fontWeight: 900, fontSize: 80, lineHeight: 1.0, letterSpacing: -3,
            background: `linear-gradient(135deg, ${C.orange}, #FF3D00)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>
            Es operación.
          </div>
        </div>

        {/* 5 steps horizontal pills */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {STEPS.map((s, i) => {
            const op = ease(f, 40 + i * 13, 65 + i * 13);
            return (
              <div key={s.n} style={{
                opacity: op,
                transform: `translateX(${interpolate(op, [0, 1], [-32, 0])}px)`,
                display: "flex", alignItems: "center", gap: 18,
                background: i === 0 ? `${C.orange}12` : C.white,
                border: `1.5px solid ${i === 0 ? C.orange + "30" : "rgba(0,0,0,0.06)"}`,
                borderRadius: 20, padding: "16px 24px",
              }}>
                <span style={{
                  fontFamily: font, fontWeight: 900, fontSize: 22,
                  color: C.orange, minWidth: 36,
                }}>{s.n}</span>
                <span style={{
                  fontFamily: font, fontWeight: 600, fontSize: 32,
                  color: C.darkGray, letterSpacing: -0.3,
                }}>{s.label}</span>
                {i === 0 && (
                  <div style={{
                    marginLeft: "auto",
                    background: C.orange,
                    borderRadius: 100,
                    padding: "4px 16px",
                    fontFamily: font, fontWeight: 700, fontSize: 20,
                    color: C.white,
                  }}>Paso 1</div>
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
// SCENE 4 — CTA  (450–600f · 5s)
// ─────────────────────────────────────────────────────────────────────────────
const SceneCTA: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 450;
  const pulse = interpolate(Math.sin(f * 0.12), [-1, 1], [0.94, 1.0]);

  return (
    <AbsoluteFill style={{ background: C.black, overflow: "hidden" }}>
      {/* Center glow */}
      <div style={{
        position: "absolute", top: "35%", left: "50%",
        transform: "translate(-50%,-50%)",
        width: 1000, height: 800,
        background: `radial-gradient(ellipse, ${C.orange}18 0%, transparent 65%)`,
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center", alignItems: "center",
        padding: "140px 64px 260px",
        gap: 0,
      }}>
        {/* Guarantee — Apple-style big text */}
        <div style={{
          opacity: ease(f, 0, 30),
          transform: `translateY(${interpolate(ease(f, 0, 30), [0, 1], [40, 0])}px)`,
          textAlign: "center",
          marginBottom: 48,
        }}>
          <div style={{
            fontFamily: font, fontWeight: 900, fontSize: 104,
            color: C.offWhite, lineHeight: 0.95, letterSpacing: -4,
          }}>Si no creces,</div>
          <div style={{
            fontFamily: font, fontWeight: 900, fontSize: 104,
            lineHeight: 0.95, letterSpacing: -4,
            background: `linear-gradient(135deg, ${C.orange} 0%, #FF3D00 100%)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}>no cobramos.</div>
        </div>

        {/* Sub copy */}
        <div style={{
          opacity: ease(f, 18, 45),
          fontFamily: font, fontWeight: 300, fontSize: 30,
          color: C.gray, textAlign: "center", lineHeight: 1.6,
          maxWidth: 720, marginBottom: 60,
        }}>
          Operación técnica en{" "}
          <span style={{ color: C.offWhite, fontWeight: 500 }}>
            Uber Eats, Rappi y DiDi.
          </span>
        </div>

        {/* WhatsApp CTA */}
        <div style={{
          opacity: ease(f, 30, 55),
          transform: `scale(${pulse}) translateY(${interpolate(ease(f, 30, 55), [0, 1], [30, 0])}px)`,
          width: "100%",
          background: C.green,
          borderRadius: 28, padding: "38px 48px",
          display: "flex", alignItems: "center",
          justifyContent: "center", gap: 18,
          boxShadow: `0 20px 60px ${C.green}55`,
          marginBottom: 24,
        }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="white">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          <span style={{
            fontFamily: font, fontWeight: 800,
            fontSize: 44, color: C.white, letterSpacing: -0.5,
          }}>Auditoría gratis →</span>
        </div>

        {/* Domain */}
        <div style={{
          opacity: ease(f, 50, 75),
          fontFamily: font, fontWeight: 300,
          fontSize: 24, color: "rgba(255,255,255,0.22)",
          letterSpacing: 5, textTransform: "uppercase",
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

  const s1 = blend(frame, 0, 100);
  const s2 = blend(frame, 108, 250);
  const s3 = blend(frame, 258, 432);
  const s4 = blend(frame, 438, 680);

  const musicVol = interpolate(frame, [0, 40, 560, 600], [0, 0.14, 0.14, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: C.black }}>
      <Audio src={staticFile("bg-music.mp3")} volume={musicVol} loop />
      <Audio src={staticFile(`vo-${hook}.mp3`)} volume={1} />

      <AbsoluteFill style={{ opacity: s1 }}>
        <SceneHook hook={hook} frame={frame} fps={fps} />
      </AbsoluteFill>

      <AbsoluteFill style={{ opacity: s2 }}>
        <SceneAlgo frame={frame} fps={fps} />
      </AbsoluteFill>

      <AbsoluteFill style={{ opacity: s3 }}>
        <SceneZuba frame={frame} fps={fps} />
      </AbsoluteFill>

      <AbsoluteFill style={{ opacity: s4 }}>
        <SceneCTA frame={frame} fps={fps} />
      </AbsoluteFill>

      {/* Caption overlay — always on top */}
      <CaptionBar hook={hook} frame={frame} />
    </AbsoluteFill>
  );
};
