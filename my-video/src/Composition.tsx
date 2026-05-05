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

// ─────────────────────────────────────────────────────────────────────────────
// Design tokens  · Dark/Light Premium Consulting · 60fps · 15s
// ─────────────────────────────────────────────────────────────────────────────
const C = {
  bone:       "#F2F2F2",   // premium bone background
  dark:       "#111111",   // deep almost-black
  darkScene:  "#1C1C1E",   // dark scene bg
  carbon:     "#1A1A1A",   // carbon text
  orange:     "#FF4F00",   // ZUBA orange — spec
  orangeGlow: "rgba(255,79,0,0.4)",
  white:      "#FFFFFF",
  gray:       "#6E6E73",
};
const font = '"Helvetica Neue",Helvetica,"Arial",sans-serif';

// ─── Helpers ──────────────────────────────────────────────────────────────────
const ei = (frame: number, from: number, to: number, ease = Easing.bezier(0.16, 1, 0.3, 1)) =>
  interpolate(frame, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

const eo = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, to], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.4, 0, 1, 1) });

// ─── Vignette overlay (always on) ────────────────────────────────────────────
const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.45 }) => (
  <div style={{
    position: "absolute", inset: 0, pointerEvents: "none", zIndex: 100,
    background: `radial-gradient(ellipse 110% 100% at 50% 50%, transparent 45%, rgba(0,0,0,${strength}) 100%)`,
  }} />
);

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 1  ·  0–240f  ·  0–4s
// "Tu restaurante está en apps…" → blur-to-focus
// "RENTABLE" slams in with glitch pulse
// ─────────────────────────────────────────────────────────────────────────────
const Scene1: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  // Line 1: blur-to-focus  0→90f
  const blurAmt = interpolate(frame, [0, 90], [18, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  const line1Op = Math.min(ei(frame, 0, 40), eo(frame, 155, 195));

  // RENTABLE enters at f=160, glitch for first 25 frames
  const rentableEnter = frame >= 160;
  const gf = frame - 160;  // local glitch frame

  // Glitch: rapid offset + subtle scale snap
  const glitchActive = gf >= 0 && gf < 28;
  const glitchSeq = [6, -5, 4, -3, 2, -2, 1, -1, 0, 0, 0, 3, -2, 1, 0, 0, 0, 2, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  const glitchX = glitchActive ? (glitchSeq[gf] ?? 0) : 0;
  const glitchScale = glitchActive && gf < 6 ? interpolate(gf, [0, 6], [1.06, 1.0]) : 1.0;
  // Chromatic aberration for first 12f
  const aberr = glitchActive && gf < 12 ? interpolate(gf, [0, 12], [5, 0]) : 0;

  const rentableOp = rentableEnter ? Math.min(1, (gf + 1) / 3) : 0;
  // Pulse ring after glitch
  const pulseRing = gf > 28 ? interpolate(gf, [28, 70], [0, 1], { extrapolateRight: "clamp" }) : 0;
  const ringScale = 1 + pulseRing * 0.15;
  const ringOp   = 1 - pulseRing;

  return (
    <AbsoluteFill style={{ background: C.bone }}>
      <Vignette />
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "flex-start", justifyContent: "center",
        padding: "0 88px",
      }}>

        {/* Line 1 — blur to focus */}
        <div style={{
          opacity: line1Op,
          filter: `blur(${blurAmt}px)`,
          marginBottom: 8,
          textShadow: "0 2px 12px rgba(0,0,0,0.12)",
        }}>
          <span style={{ fontFamily: font, fontWeight: 300, fontSize: 56, color: C.carbon, letterSpacing: -1.5, lineHeight: 1.2, display: "block" }}>
            Tu restaurante
          </span>
          <span style={{ fontFamily: font, fontWeight: 600, fontSize: 56, color: C.carbon, letterSpacing: -1.5, lineHeight: 1.2, display: "block" }}>
            está en apps...
          </span>
        </div>

        {/* RENTABLE — slam in with glitch */}
        {rentableEnter && (
          <div style={{ position: "relative" }}>
            {/* Pulse ring */}
            {pulseRing < 1 && (
              <div style={{
                position: "absolute", inset: -8,
                borderRadius: 8,
                border: `3px solid ${C.orange}`,
                opacity: ringOp * 0.6,
                transform: `scale(${ringScale})`,
                pointerEvents: "none",
              }} />
            )}

            {/* Chromatic ghost (red) */}
            {aberr > 0 && (
              <div style={{
                position: "absolute",
                transform: `translateX(${aberr}px)`,
                opacity: 0.4,
              }}>
                <span style={{ fontFamily: font, fontWeight: 900, fontSize: 108, color: "#FF0000", letterSpacing: -4, lineHeight: 1 }}>
                  RENTABLE.
                </span>
              </div>
            )}
            {/* Chromatic ghost (cyan) */}
            {aberr > 0 && (
              <div style={{
                position: "absolute",
                transform: `translateX(${-aberr}px)`,
                opacity: 0.35,
              }}>
                <span style={{ fontFamily: font, fontWeight: 900, fontSize: 108, color: "#00FFFF", letterSpacing: -4, lineHeight: 1 }}>
                  RENTABLE.
                </span>
              </div>
            )}

            {/* Main RENTABLE */}
            <div style={{
              opacity: rentableOp,
              transform: `translateX(${glitchX}px) scale(${glitchScale})`,
              textShadow: `0 0 40px ${C.orangeGlow}, 0 4px 16px rgba(0,0,0,0.15)`,
            }}>
              <span style={{
                fontFamily: font, fontWeight: 900, fontSize: 108,
                color: C.orange, letterSpacing: -4, lineHeight: 1,
                display: "block",
              }}>
                RENTABLE.
              </span>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 2  ·  240–480f  ·  4–8s
// Problems flash in/out with vertical motion blur
// ─────────────────────────────────────────────────────────────────────────────
const PROBLEMS = ["Sin estructura.", "Sin control.", "Sin rentabilidad."];

const MotionItem: React.FC<{
  text: string; frame: number; fps: number;
  enterAt: number; holdUntil: number; exitAt: number;
  accent?: boolean;
}> = ({ text, frame, enterAt, holdUntil, exitAt, accent }) => {
  const entering = frame >= enterAt && frame < holdUntil;
  const holding  = frame >= holdUntil && frame < exitAt;
  const exiting  = frame >= exitAt && frame < exitAt + 22;
  if (!entering && !holding && !exiting) return null;

  let opacity = 0, blurPx = 0, translateY = 0;
  if (entering) {
    const p = ei(frame, enterAt, enterAt + 22);
    opacity    = p;
    blurPx     = interpolate(p, [0, 1], [14, 0]);
    translateY = interpolate(p, [0, 1], [32, 0]);
  } else if (holding) {
    opacity = 1; blurPx = 0; translateY = 0;
  } else if (exiting) {
    const p = eo(frame, exitAt, exitAt + 22);
    opacity    = p;
    blurPx     = interpolate(p, [0, 1], [14, 0]);
    translateY = interpolate(p, [0, 1], [-32, 0]);
  }

  return (
    <div style={{
      position: "absolute", inset: 0,
      display: "flex", alignItems: "center", justifyContent: "flex-start",
      padding: "0 88px",
    }}>
      <div style={{
        opacity,
        filter: `blur(${blurPx}px)`,
        transform: `translateY(${translateY}px)`,
        textShadow: accent ? `0 0 32px ${C.orangeGlow}` : "0 2px 10px rgba(0,0,0,0.10)",
      }}>
        <span style={{
          fontFamily: font, fontWeight: 700, fontSize: 82,
          color: accent ? C.orange : C.carbon,
          letterSpacing: -3, lineHeight: 1.0,
        }}>
          {text}
        </span>
      </div>
    </div>
  );
};

const Scene2: React.FC<{ frame: number; fps: number }> = ({ frame }) => {
  const f = frame - 240;
  return (
    <AbsoluteFill style={{ background: C.bone }}>
      <Vignette />
      {/* Label */}
      <div style={{
        position: "absolute", top: 780, left: 88,
        opacity: Math.min(ei(f, 0, 30), eo(f, 210, 240)),
        textShadow: "0 1px 4px rgba(0,0,0,0.08)",
      }}>
        <span style={{ fontFamily: font, fontWeight: 400, fontSize: 24, color: C.gray, letterSpacing: 3, textTransform: "uppercase" }}>
          El problema
        </span>
      </div>
      <MotionItem text="Sin estructura."   frame={f} fps={60} enterAt={10}  holdUntil={70}  exitAt={80}  />
      <MotionItem text="Sin control."      frame={f} fps={60} enterAt={75}  holdUntil={140} exitAt={150} />
      <MotionItem text="Sin rentabilidad." frame={f} fps={60} enterAt={145} holdUntil={215} exitAt={225} accent />
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 3  ·  480–720f  ·  8–12s
// Dark mode. Light beam. "No es marketing. Es DECISIÓN."
// ─────────────────────────────────────────────────────────────────────────────
const Scene3: React.FC<{ frame: number; fps: number }> = ({ frame }) => {
  const f = frame - 480;

  const line1Op = Math.min(ei(f, 0, 35), eo(f, 185, 215));
  const line2Op = Math.min(ei(f, 40, 75), eo(f, 195, 225));
  const beamOp  = ei(f, 0, 60);

  return (
    <AbsoluteFill style={{ background: C.darkScene }}>
      {/* Ceiling light beam */}
      <div style={{
        position: "absolute", top: 0, left: "50%",
        transform: "translateX(-50%)",
        width: 600, height: 1400,
        background: "radial-gradient(ellipse 280px 700px at 50% 0%, rgba(255,255,255,0.09) 0%, transparent 65%)",
        opacity: beamOp, pointerEvents: "none",
      }} />
      {/* Orange accent glow (floor) */}
      <div style={{
        position: "absolute", bottom: 0, left: "50%",
        transform: "translateX(-50%)",
        width: 800, height: 400,
        background: `radial-gradient(ellipse 400px 200px at 50% 100%, ${C.orangeGlow} 0%, transparent 70%)`,
        opacity: Math.min(ei(f, 60, 120), 0.55), pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "flex-start", justifyContent: "center",
        padding: "0 88px",
        gap: 10,
      }}>
        <div style={{ opacity: line1Op, transform: `translateY(${interpolate(ei(f, 0, 35), [0, 1], [28, 0])}px)` }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 68,
            color: C.white, letterSpacing: -2.5, lineHeight: 1.1,
            textShadow: "0 2px 20px rgba(0,0,0,0.4)",
          }}>
            No es marketing.
          </span>
        </div>
        <div style={{ opacity: line2Op, transform: `translateY(${interpolate(ei(f, 40, 75), [0, 1], [28, 0])}px)` }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 68,
            color: C.white, letterSpacing: -2.5, lineHeight: 1.1,
          }}>
            Es{" "}
          </span>
          <span style={{
            fontFamily: font, fontWeight: 900, fontSize: 68,
            color: C.orange, letterSpacing: -2.5, lineHeight: 1.1,
            textShadow: `0 0 48px ${C.orangeGlow}, 0 2px 10px rgba(0,0,0,0.3)`,
          }}>
            DECISIÓN.
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 4  ·  720–900f  ·  12–15s
// ZUBA logo with metallic shimmer. Pulsing orange pill.
// ─────────────────────────────────────────────────────────────────────────────
const Scene4: React.FC<{ frame: number; fps: number }> = ({ frame }) => {
  const f = frame - 720;

  // Metallic shine: gradient sweeps left-to-right over the logo (repeats)
  const shinePos = ((f % 120) / 120) * 260 - 40; // -40 to 220
  const shineOp  = f < 30 ? 0 : Math.min(1, (f - 30) / 20);

  const logoOp    = ei(f, 0, 40);
  const taglineOp = ei(f, 30, 60);
  const btnOp     = ei(f, 55, 85);

  // Gentle pulse on button
  const pulse = 1 + 0.022 * Math.sin((f / 60) * Math.PI * 2 * 1.4);

  // Dark bg for this scene (stays dark from scene 3)
  return (
    <AbsoluteFill style={{ background: C.darkScene }}>
      {/* Subtle orange halo center */}
      <div style={{
        position: "absolute", top: "38%", left: "50%",
        transform: "translate(-50%,-50%)",
        width: 700, height: 700, borderRadius: "50%",
        background: `radial-gradient(circle, rgba(255,79,0,0.12) 0%, transparent 65%)`,
        opacity: ei(f, 0, 60), pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "0 80px", gap: 0,
      }}>

        {/* ZUBA logotype with metallic shimmer */}
        <div style={{
          opacity: logoOp,
          transform: `scale(${interpolate(logoOp, [0, 1], [0.92, 1.0])})`,
          marginBottom: 20,
          position: "relative", display: "inline-flex", flexDirection: "column",
          alignItems: "center", gap: 14,
        }}>
          {/* Z icon */}
          <div style={{
            width: 84, height: 84, borderRadius: 24,
            background: C.orange,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 8px 40px ${C.orangeGlow}`,
          }}>
            <span style={{ fontFamily: font, fontWeight: 900, fontSize: 44, color: C.white }}>Z</span>
          </div>

          {/* ZUBA text + shine overlay */}
          <div style={{ position: "relative", overflow: "hidden" }}>
            <span style={{
              fontFamily: font, fontWeight: 900, fontSize: 72,
              color: C.orange, letterSpacing: -2,
              textShadow: `0 0 60px ${C.orangeGlow}`,
              display: "block",
            }}>ZUBA</span>
            {/* Metallic shine sweep */}
            <div style={{
              position: "absolute", top: 0, bottom: 0,
              left: shinePos - 40, width: 80,
              background: "linear-gradient(105deg, transparent 0%, rgba(255,255,255,0.55) 50%, transparent 100%)",
              opacity: shineOp * 0.9,
              pointerEvents: "none",
            }} />
          </div>
        </div>

        {/* Tagline */}
        <div style={{ opacity: taglineOp, marginBottom: 52 }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 26,
            color: "rgba(255,255,255,0.45)", letterSpacing: 2,
            textTransform: "uppercase",
          }}>Consultoría de operación</span>
        </div>

        {/* Guarantee text */}
        <div style={{ opacity: Math.min(ei(f, 45, 72), 1), marginBottom: 36 }}>
          <span style={{
            fontFamily: font, fontWeight: 300, fontSize: 30,
            color: "rgba(255,255,255,0.55)",
          }}>
            Si no creces,{" "}
            <span style={{ color: C.white, fontWeight: 600 }}>no cobramos.</span>
          </span>
        </div>

        {/* Orange pill CTA */}
        <div style={{
          opacity: btnOp,
          transform: `scale(${pulse * interpolate(btnOp, [0, 1], [0.9, 1.0])})`,
          background: C.orange,
          borderRadius: 980,
          padding: "22px 56px",
          display: "inline-flex", alignItems: "center", gap: 16,
          boxShadow: `0 6px 48px ${C.orangeGlow}, 0 2px 8px rgba(0,0,0,0.25)`,
          cursor: "pointer",
        }}>
          <svg width="26" height="26" viewBox="0 0 24 24" fill="white">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          <span style={{ fontFamily: font, fontWeight: 700, fontSize: 34, color: C.white, letterSpacing: -0.3 }}>
            Auditoría Gratis
          </span>
        </div>

      </div>
    </AbsoluteFill>
  );
};

// ── Main ──────────────────────────────────────────────────────────────────────
export const ZubaAd: React.FC<Props> = ({ hook }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene blend-in/out
  const s1 = Math.min(ei(frame, 0, 20),       eo(frame, 218, 248));
  const s2 = Math.min(ei(frame, 228, 258),     eo(frame, 458, 488));
  const s3 = Math.min(ei(frame, 468, 498),     eo(frame, 698, 728));
  const s4 = Math.min(ei(frame, 708, 740),     1);

  const musicVol = interpolate(frame, [0, 60, 820, 900], [0, 0.11, 0.11, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: C.bone }}>
      <Audio src={staticFile("bg-music.mp3")} volume={musicVol} loop />
      <Audio src={staticFile(`vo-${hook}.mp3`)} volume={0.9} />

      <AbsoluteFill style={{ opacity: s1 }}><Scene1 frame={frame} fps={fps} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s2 }}><Scene2 frame={frame} fps={fps} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s3 }}><Scene3 frame={frame} fps={fps} /></AbsoluteFill>
      <AbsoluteFill style={{ opacity: s4 }}><Scene4 frame={frame} fps={fps} /></AbsoluteFill>
    </AbsoluteFill>
  );
};
