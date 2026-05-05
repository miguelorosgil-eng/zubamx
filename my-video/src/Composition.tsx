import { Audio, staticFile } from "remotion";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";

export const ZubaAdSchema = z.object({
  hook: z.enum(["pain", "mecanismo", "riesgo"]),
});
type Props = z.infer<typeof ZubaAdSchema>;

// ─────────────────────────────────────────────────────────────────────────────
// Design tokens — Premium Fintech / Apple aesthetic
// Hook: 3s · Benefit: 8s · CTA: 15s
// Text ≤ 40% of screen · Massive negative space
// ─────────────────────────────────────────────────────────────────────────────
const C = {
  bg:      "#F5F5F7",  // broken white — Apple
  black:   "#1A1A1A",  // carbon black
  gray:    "#8A8A8E",  // secondary text
  divider: "#D1D1D6",  // ultra-thin separators
  orange:  "#FF6B35",  // ZUBA accent — ONLY color
  white:   "#FFFFFF",
};
const font = '"SF Pro Display","SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif';

// ─── Animation primitives ────────────────────────────────────────────────────

/** Smooth slide-up + fade. Apple/Fintech style: elegant, never hurried. */
const slideUp = (frame: number, from: number, duration = 28) => {
  const p = interpolate(frame, [from, from + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  return {
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [40, 0])}px)`,
  };
};

/** Scene cross-fade */
const sceneAlpha = (frame: number, inAt: number, outAt: number) => {
  const i = interpolate(frame, [inAt, inAt + 22], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const o = interpolate(frame, [outAt, outAt + 18], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 1, 1),
  });
  return Math.min(i, o);
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 1  ·  0 – 108f  ·  3.6s
// Hook: problema en 3 palabras. RENTABLE en naranja.
// ─────────────────────────────────────────────────────────────────────────────
const Scene1: React.FC<{ frame: number }> = ({ frame }) => (
  <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
    <div style={{ padding: "0 80px", width: "100%" }}>

      {/* Supporting line — small, gray */}
      <div style={{ ...slideUp(frame, 4), marginBottom: 28 }}>
        <span style={{
          fontFamily: font, fontWeight: 400, fontSize: 28,
          color: C.gray, letterSpacing: 0.2,
        }}>
          Uber Eats · Rappi · DiDi Food
        </span>
      </div>

      {/* Main statement */}
      <div style={{ ...slideUp(frame, 16), marginBottom: 12 }}>
        <span style={{
          fontFamily: font, fontWeight: 600, fontSize: 72,
          color: C.black, letterSpacing: -2.5, lineHeight: 1.05,
          display: "block",
        }}>
          Tu restaurante<br />está en apps...
        </span>
      </div>

      {/* Thin divider */}
      <div style={{
        ...slideUp(frame, 32),
        height: 1, background: C.divider, marginBottom: 28,
      }} />

      {/* "pero no es RENTABLE" */}
      <div style={{ ...slideUp(frame, 42) }}>
        <span style={{
          fontFamily: font, fontWeight: 300, fontSize: 52,
          color: C.black, letterSpacing: -1.5, lineHeight: 1.1,
          display: "block",
        }}>
          pero no es
        </span>
        <span style={{
          fontFamily: font, fontWeight: 900, fontSize: 96,
          color: C.orange, letterSpacing: -4, lineHeight: 0.95,
          display: "block",
        }}>
          RENTABLE.
        </span>
      </div>

    </div>
  </AbsoluteFill>
);

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 2  ·  108 – 248f  ·  4.7s
// Pain points. Line-by-line with ultra-thin dividers.
// ─────────────────────────────────────────────────────────────────────────────
const PAINS = ["Vendes sin crecer.", "Sin estructura.", "Sin control."];

const Scene2: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame - 108;
  return (
    <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ padding: "0 80px", width: "100%" }}>

        {/* Label */}
        <div style={{ ...slideUp(f, 0), marginBottom: 40 }}>
          <span style={{
            fontFamily: font, fontWeight: 500, fontSize: 24,
            color: C.gray, letterSpacing: 2, textTransform: "uppercase",
          }}>
            El problema
          </span>
        </div>

        {/* List with hairline dividers */}
        {PAINS.map((pain, i) => (
          <div key={pain}>
            {/* Top divider */}
            <div style={{
              ...slideUp(f, 12 + i * 28),
              height: 1, background: C.divider, marginBottom: 0,
            }} />
            <div style={{
              ...slideUp(f, 18 + i * 28),
              padding: "32px 0",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{
                fontFamily: font, fontWeight: 500, fontSize: 52,
                color: C.black, letterSpacing: -1.5,
              }}>
                {pain}
              </span>
              {/* Subtle orange dash accent */}
              <span style={{
                fontFamily: font, fontWeight: 300, fontSize: 32,
                color: C.orange, opacity: 0.6,
              }}>—</span>
            </div>
          </div>
        ))}
        {/* Bottom divider */}
        <div style={{
          ...slideUp(f, 12 + PAINS.length * 28),
          height: 1, background: C.divider,
        }} />

      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 3  ·  248 – 355f  ·  3.6s
// Solution statement. Maximum negative space. "DECISIÓN" in orange.
// ─────────────────────────────────────────────────────────────────────────────
const Scene3: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame - 248;
  return (
    <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ padding: "0 80px", width: "100%", textAlign: "left" }}>

        <div style={{ ...slideUp(f, 0), marginBottom: 8 }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 60,
            color: C.black, letterSpacing: -2, lineHeight: 1.1,
            display: "block",
          }}>
            No es marketing.
          </span>
        </div>

        <div style={{ ...slideUp(f, 18), marginBottom: 52 }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 60,
            color: C.black, letterSpacing: -2, lineHeight: 1.1,
          }}>
            Es{" "}
          </span>
          <span style={{
            fontFamily: font, fontWeight: 800, fontSize: 60,
            color: C.orange, letterSpacing: -2, lineHeight: 1.1,
          }}>
            DECISIÓN.
          </span>
        </div>

        {/* Thin divider */}
        <div style={{ ...slideUp(f, 34), height: 1, background: C.divider, marginBottom: 36 }} />

        {/* 5 steps — ultra minimal, text only */}
        {["Diagnóstico", "Fotografía", "Menú estratégico", "Activación", "Pauta interna"].map((s, i) => (
          <div key={s} style={{
            ...slideUp(f, 42 + i * 10),
            display: "flex", alignItems: "center", gap: 20,
            paddingBottom: 14,
          }}>
            <span style={{ fontFamily: font, fontWeight: 700, fontSize: 22, color: C.orange }}>
              {String(i + 1).padStart(2, "0")}
            </span>
            <span style={{ fontFamily: font, fontWeight: 400, fontSize: 32, color: C.black, letterSpacing: -0.5 }}>
              {s}
            </span>
          </div>
        ))}

      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 4  ·  355 – 450f  ·  3.2s
// ZUBA logo centered + capsule CTA. Nothing else.
// ─────────────────────────────────────────────────────────────────────────────
const Scene4: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame - 355;
  const breathe = 1 + 0.008 * Math.sin(f * 0.12);
  return (
    <AbsoluteFill style={{ background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0, padding: "0 80px", width: "100%" }}>

        {/* ZUBA logotype — centered, orange */}
        <div style={{ ...slideUp(f, 0), display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 40 }}>
          <div style={{
            width: 80, height: 80, borderRadius: 22,
            background: C.orange,
            display: "flex", alignItems: "center", justifyContent: "center",
            marginBottom: 18,
          }}>
            <span style={{ fontFamily: font, fontWeight: 900, fontSize: 42, color: C.white }}>Z</span>
          </div>
          <span style={{
            fontFamily: font, fontWeight: 900, fontSize: 56,
            color: C.orange, letterSpacing: -1.5,
          }}>ZUBA</span>
          <span style={{
            fontFamily: font, fontWeight: 400, fontSize: 26,
            color: C.gray, marginTop: 6, letterSpacing: 0.2,
          }}>Consultoría de operación</span>
        </div>

        {/* Thin divider */}
        <div style={{ ...slideUp(f, 18), height: 1, background: C.divider, width: "100%", marginBottom: 44 }} />

        {/* Guarantee — subtle */}
        <div style={{ ...slideUp(f, 28), marginBottom: 36, textAlign: "center" }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 30,
            color: C.gray, letterSpacing: 0,
          }}>
            Si no creces,{" "}
            <span style={{ color: C.black, fontWeight: 500 }}>no cobramos.</span>
          </span>
        </div>

        {/* Capsule CTA — small, elegant, orange */}
        <div style={{
          ...slideUp(f, 42),
          transform: `${slideUp(f, 42).transform} scale(${breathe})`,
          background: C.orange,
          borderRadius: 980,
          padding: "20px 52px",
          display: "inline-flex", alignItems: "center", gap: 14,
          boxShadow: `0 8px 32px rgba(255,107,53,0.30)`,
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          <span style={{ fontFamily: font, fontWeight: 600, fontSize: 32, color: C.white, letterSpacing: -0.3 }}>
            Auditoría gratis →
          </span>
        </div>

        <div style={{
          ...slideUp(f, 58),
          marginTop: 24,
          fontFamily: font, fontWeight: 300, fontSize: 22,
          color: C.gray, letterSpacing: 3, textTransform: "uppercase",
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

  const s1 = sceneAlpha(frame, 0,   90);
  const s2 = sceneAlpha(frame, 100, 232);
  const s3 = sceneAlpha(frame, 240, 340);
  const s4 = sceneAlpha(frame, 348, 500);

  const musicVol = interpolate(frame, [0, 30, 410, 450], [0, 0.1, 0.1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <Audio src={staticFile("bg-music.mp3")} volume={musicVol} loop />
      <Audio src={staticFile(`vo-${hook}.mp3`)} volume={0.85} />

      <AbsoluteFill style={{ opacity: s1 }}><Scene1 frame={frame} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s2 }}><Scene2 frame={frame} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s3 }}><Scene3 frame={frame} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s4 }}><Scene4 frame={frame} /></AbsoluteFill>
    </AbsoluteFill>
  );
};
