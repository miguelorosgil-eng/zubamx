import { Audio, Sequence, staticFile, AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";

export const ZubaAdSchema = z.object({
  hook: z.enum(["pain", "mecanismo", "riesgo"]),
});
type Props = z.infer<typeof ZubaAdSchema>;

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bone:       "#F5F5F7",
  carbon:     "#1D1D1F",
  gray:       "#6E6E73",
  orange:     "#FF4F00",
  orangeGlow: "rgba(255,79,0,0.35)",
  white:      "#FFFFFF",
};
const font = '"Helvetica Neue",Helvetica,Arial,sans-serif';

// ─── Helpers ──────────────────────────────────────────────────────────────────
const ei = (frame: number, from: number, to: number, ease = Easing.bezier(0.16, 1, 0.3, 1)) =>
  interpolate(frame, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

const eo = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, to], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.4, 0, 1, 1) });

// ─── Vignette ─────────────────────────────────────────────────────────────────
const Vignette: React.FC<{ dark?: boolean }> = ({ dark }) => (
  <div style={{
    position: "absolute", inset: 0, pointerEvents: "none", zIndex: 50,
    background: dark
      ? "radial-gradient(ellipse 100% 100% at 50% 50%, transparent 35%, rgba(0,0,0,0.55) 100%)"
      : "radial-gradient(ellipse 100% 100% at 50% 50%, transparent 50%, rgba(0,0,0,0.16) 100%)",
  }} />
);

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 1  ·  0–180f  ·  0–3s  ·  BONE WHITE  ·  Hook
// ─────────────────────────────────────────────────────────────────────────────
const Scene1: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame;

  const blur1 = interpolate(f, [0, 50], [20, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  const op1 = ei(f, 0, 30);
  const op2 = ei(f, 46, 68);
  const ty2 = interpolate(op2, [0, 1], [28, 0]);

  const rf = f - 88;
  const glitchSeq = [8, -6, 5, -4, 3, -2, 2, -1, 1, 0, 0, 0, 2, -1, 0, 0, 0, 0, 0, 0, 0, 0];
  const glitchX = f >= 88 && rf < 22 ? (glitchSeq[rf] ?? 0) : 0;
  const rentScale = f >= 88
    ? interpolate(rf, [0, 8, 14], [1.38, 0.95, 1.0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 1.38;
  const rentOp = f >= 88 ? Math.min(1, (rf + 1) / 4) : 0;
  const aberr = f >= 88 && rf < 12
    ? interpolate(rf, [0, 12], [10, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 0;

  return (
    <AbsoluteFill style={{ background: C.bone }}>
      <Vignette />
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "flex-start", justifyContent: "center",
        padding: "0 80px", gap: 4,
      }}>
        {/* "Tu restaurante está en apps..." — blur to focus */}
        <div style={{ opacity: op1, filter: `blur(${blur1}px)`, marginBottom: 8 }}>
          <span style={{ fontFamily: font, fontWeight: 300, fontSize: 54, color: C.gray, letterSpacing: -1.5, lineHeight: 1.2, display: "block" }}>
            Tu restaurante
          </span>
          <span style={{ fontFamily: font, fontWeight: 600, fontSize: 54, color: C.carbon, letterSpacing: -1.5, lineHeight: 1.2, display: "block" }}>
            está en apps...
          </span>
        </div>

        {/* "pero NO es" — slides up */}
        <div style={{ opacity: op2, transform: `translateY(${ty2}px)`, marginBottom: 2 }}>
          <span style={{ fontFamily: font, fontWeight: 400, fontSize: 46, color: C.carbon, letterSpacing: -1.2 }}>
            pero <span style={{ fontWeight: 800 }}>NO es</span>
          </span>
        </div>

        {/* RENTABLE — slams in with glitch */}
        <div style={{ position: "relative" }}>
          {aberr > 0 && (
            <>
              <div style={{ position: "absolute", transform: `translateX(${aberr}px)`, opacity: 0.45, lineHeight: 1 }}>
                <span style={{ fontFamily: font, fontWeight: 900, fontSize: 116, color: "#FF0000", letterSpacing: -4 }}>RENTABLE</span>
              </div>
              <div style={{ position: "absolute", transform: `translateX(${-aberr}px)`, opacity: 0.38, lineHeight: 1 }}>
                <span style={{ fontFamily: font, fontWeight: 900, fontSize: 116, color: "#00FFFF", letterSpacing: -4 }}>RENTABLE</span>
              </div>
            </>
          )}
          <div style={{
            opacity: rentOp,
            transform: `translateX(${glitchX}px) scale(${rentScale})`,
            transformOrigin: "left center",
            textShadow: `0 0 50px ${C.orangeGlow}, 0 4px 20px rgba(255,79,0,0.2)`,
          }}>
            <span style={{ fontFamily: font, fontWeight: 900, fontSize: 116, color: C.orange, letterSpacing: -4, lineHeight: 1 }}>
              RENTABLE
            </span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 2  ·  180–420f  ·  3–7s  ·  CARBON BLACK  ·  Pain
// ─────────────────────────────────────────────────────────────────────────────
const PAIN_ITEMS = [
  { text: "Vendes sin crecer", enterAt: 15 },
  { text: "Sin estructura",    enterAt: 80 },
  { text: "Sin control",       enterAt: 150 },
];

const PainRow: React.FC<{ text: string; frame: number; enterAt: number }> = ({ text, frame, enterAt }) => {
  const rf = frame - enterAt;
  if (rf < -2) return null;
  const p = ei(Math.max(0, rf), 0, 20);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 22,
      opacity: p,
      filter: `blur(${interpolate(p, [0, 1], [18, 0])}px)`,
      transform: `translateY(${interpolate(p, [0, 1], [55, 0])}px)`,
    }}>
      <div style={{
        width: 13, height: 13, borderRadius: "50%",
        background: C.orange, flexShrink: 0,
        boxShadow: `0 0 14px ${C.orangeGlow}`,
      }} />
      <span style={{ fontFamily: font, fontWeight: 700, fontSize: 70, color: C.white, letterSpacing: -2.5, lineHeight: 1.05 }}>
        {text}
      </span>
    </div>
  );
};

const Scene2: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame - 180;
  return (
    <AbsoluteFill style={{ background: C.carbon }}>
      <Vignette dark />
      <div style={{
        position: "absolute", top: 196, left: 80,
        opacity: Math.min(ei(f, 0, 25), eo(f, 210, 240)),
        fontFamily: font, fontWeight: 400, fontSize: 21,
        color: "rgba(255,255,255,0.32)", letterSpacing: 4, textTransform: "uppercase",
      }}>
        El problema
      </div>
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center",
        padding: "0 80px", gap: 30,
      }}>
        {PAIN_ITEMS.map(item => (
          <PainRow key={item.text} text={item.text} frame={f} enterAt={item.enterAt} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 3  ·  420–660f  ·  7–11s  ·  BONE WHITE  ·  Authority
// ─────────────────────────────────────────────────────────────────────────────
const CARDS = [
  { letter: "D", label: "Diagnóstico",  sub: "en 48 horas",        enterAt: 18 },
  { letter: "E", label: "Estrategia",   sub: "basada en datos",     enterAt: 62 },
  { letter: "R", label: "Resultados",   sub: "medibles y reales",   enterAt: 106 },
];

const UICard: React.FC<{ letter: string; label: string; sub: string; frame: number; enterAt: number }> =
  ({ letter, label, sub, frame, enterAt }) => {
    const rf = frame - enterAt;
    if (rf < -3) return null;
    const p = ei(Math.max(0, rf), 0, 22);
    return (
      <div style={{
        opacity: p,
        transform: `translateY(${interpolate(p, [0, 1], [68, 0])}px)`,
        display: "flex", alignItems: "center", gap: 20,
        background: C.white,
        borderRadius: 22,
        padding: "20px 28px",
        boxShadow: "0 6px 40px rgba(0,0,0,0.10), 0 1px 3px rgba(0,0,0,0.06)",
        width: "100%",
      }}>
        <div style={{
          width: 48, height: 48, borderRadius: 14,
          background: C.orange,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
          boxShadow: `0 4px 16px ${C.orangeGlow}`,
        }}>
          <span style={{ fontFamily: font, fontWeight: 900, fontSize: 22, color: C.white }}>{letter}</span>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: font, fontWeight: 700, fontSize: 28, color: C.carbon, lineHeight: 1.1 }}>{label}</div>
          <div style={{ fontFamily: font, fontWeight: 400, fontSize: 20, color: C.gray, marginTop: 2 }}>{sub}</div>
        </div>
        <div style={{
          width: 26, height: 26, borderRadius: "50%",
          background: "#34C759",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <span style={{ color: "white", fontSize: 14, fontWeight: 700 }}>✓</span>
        </div>
      </div>
    );
  };

const Scene3: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame - 420;

  const textOp1 = ei(f, 145, 175);
  const textOp2 = ei(f, 162, 196);
  const decScale = f >= 162
    ? interpolate(f - 162, [0, 10, 16], [1.38, 0.95, 1.0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 1.0;

  return (
    <AbsoluteFill style={{ background: C.bone }}>
      <Vignette />
      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center",
        padding: "0 64px", gap: 0,
      }}>
        {/* UI notification cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 60 }}>
          {CARDS.map(card => (
            <UICard key={card.label} {...card} frame={f} />
          ))}
        </div>

        {/* "No es marketing. Es DECISIÓN." */}
        <div style={{ opacity: textOp1, transform: `translateY(${interpolate(textOp1, [0, 1], [32, 0])}px)`, marginBottom: 4 }}>
          <span style={{ fontFamily: font, fontWeight: 300, fontSize: 60, color: C.carbon, letterSpacing: -2, lineHeight: 1.1 }}>
            No es marketing.
          </span>
        </div>
        <div style={{ opacity: textOp2, transform: `translateY(${interpolate(textOp2, [0, 1], [32, 0])}px)` }}>
          <span style={{ fontFamily: font, fontWeight: 300, fontSize: 60, color: C.carbon, letterSpacing: -2, lineHeight: 1.1 }}>Es </span>
          <span style={{
            fontFamily: font, fontWeight: 900, fontSize: 60,
            color: C.orange, letterSpacing: -2, lineHeight: 1.1,
            display: "inline-block",
            transform: `scale(${decScale})`, transformOrigin: "left center",
            textShadow: `0 0 40px ${C.orangeGlow}`,
          }}>
            DECISIÓN.
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 4  ·  660–900f  ·  11–15s  ·  DARK  ·  CTA
// ─────────────────────────────────────────────────────────────────────────────
const Scene4: React.FC<{ frame: number }> = ({ frame }) => {
  const f = frame - 660;

  const shinePos = ((f % 120) / 120) * 280 - 50;
  const shineOp  = f < 40 ? 0 : Math.min(1, (f - 40) / 20);
  const logoOp   = ei(f, 0, 40);
  const tagOp    = ei(f, 28, 55);
  const subOp    = ei(f, 44, 70);
  const btnOp    = ei(f, 58, 88);
  const pulse    = 1 + 0.024 * Math.sin((f / 60) * Math.PI * 2 * 1.3);

  return (
    <AbsoluteFill style={{ background: C.carbon }}>
      {/* Central orange halo */}
      <div style={{
        position: "absolute", top: "38%", left: "50%",
        transform: "translate(-50%,-50%)",
        width: 650, height: 650, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(255,79,0,0.10) 0%, transparent 65%)",
        opacity: ei(f, 0, 60), pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "0 80px", gap: 0,
      }}>
        {/* ZUBA logo with metallic shine */}
        <div style={{
          opacity: logoOp,
          transform: `scale(${interpolate(logoOp, [0, 1], [0.88, 1.0])})`,
          marginBottom: 18,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 14,
        }}>
          <div style={{
            width: 88, height: 88, borderRadius: 24,
            background: C.orange,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 8px 48px ${C.orangeGlow}`,
          }}>
            <span style={{ fontFamily: font, fontWeight: 900, fontSize: 46, color: C.white }}>Z</span>
          </div>
          <div style={{ position: "relative", overflow: "hidden" }}>
            <span style={{ fontFamily: font, fontWeight: 900, fontSize: 76, color: C.orange, letterSpacing: -2, textShadow: `0 0 60px ${C.orangeGlow}`, display: "block" }}>
              ZUBA
            </span>
            <div style={{
              position: "absolute", top: 0, bottom: 0,
              left: shinePos - 40, width: 80,
              background: "linear-gradient(105deg, transparent 0%, rgba(255,255,255,0.55) 50%, transparent 100%)",
              opacity: shineOp * 0.85, pointerEvents: "none",
            }} />
          </div>
        </div>

        {/* Tagline */}
        <div style={{ opacity: tagOp, marginBottom: 44 }}>
          <span style={{ fontFamily: font, fontWeight: 300, fontSize: 26, color: "rgba(255,255,255,0.4)", letterSpacing: 3, textTransform: "uppercase" }}>
            Consultoría de operación
          </span>
        </div>

        {/* Guarantee */}
        <div style={{ opacity: subOp, marginBottom: 36 }}>
          <span style={{ fontFamily: font, fontWeight: 300, fontSize: 30, color: "rgba(255,255,255,0.5)" }}>
            Si no creces,{" "}
            <span style={{ color: C.white, fontWeight: 600 }}>no cobramos.</span>
          </span>
        </div>

        {/* Orange pill CTA */}
        <div style={{
          opacity: btnOp,
          transform: `scale(${pulse * interpolate(btnOp, [0, 1], [0.88, 1.0])})`,
          background: C.orange,
          borderRadius: 980,
          padding: "24px 60px",
          display: "inline-flex", alignItems: "center", gap: 18,
          boxShadow: `0 8px 56px ${C.orangeGlow}, 0 2px 8px rgba(0,0,0,0.3)`,
        }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          <span style={{ fontFamily: font, fontWeight: 700, fontSize: 36, color: C.white, letterSpacing: -0.3 }}>
            Auditoría Gratis
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Main ──────────────────────────────────────────────────────────────────────
export const ZubaAd: React.FC<Props> = (_props) => {
  const frame = useCurrentFrame();

  // Hard cuts at scene boundaries + white flash overlay
  const activeScene = frame < 180 ? 1 : frame < 420 ? 2 : frame < 660 ? 3 : 4;

  const fl1 = frame >= 178 && frame <= 188
    ? interpolate(frame, [178, 180, 183, 188], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 0;
  const fl2 = frame >= 418 && frame <= 428
    ? interpolate(frame, [418, 420, 423, 428], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : 0;
  const flashOp = Math.max(fl1, fl2);

  const musicVol = interpolate(frame, [0, 60, 840, 900], [0, 0.09, 0.09, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: C.bone }}>
      {/* Background music */}
      <Audio src={staticFile("bg-music.mp3")} volume={musicVol} loop />

      {/* Voiceover — one audio file per scene, starts exactly at scene boundary */}
      <Sequence from={0} durationInFrames={200}>
        <Audio src={staticFile("vo-s1.mp3")} volume={0.92} />
      </Sequence>
      <Sequence from={180} durationInFrames={260}>
        <Audio src={staticFile("vo-s2.mp3")} volume={0.92} />
      </Sequence>
      <Sequence from={420} durationInFrames={260}>
        <Audio src={staticFile("vo-s3.mp3")} volume={0.92} />
      </Sequence>
      <Sequence from={660} durationInFrames={260}>
        <Audio src={staticFile("vo-s4.mp3")} volume={0.92} />
      </Sequence>

      {/* SFX: thud when RENTABLE slams in at frame 88 */}
      <Sequence from={88} durationInFrames={45}>
        <Audio src={staticFile("sfx-thud.mp3")} volume={0.8} />
      </Sequence>

      {/* Scenes — hard cut, no opacity crossfade */}
      {activeScene === 1 && <Scene1 frame={frame} />}
      {activeScene === 2 && <Scene2 frame={frame} />}
      {activeScene === 3 && <Scene3 frame={frame} />}
      {activeScene === 4 && <Scene4 frame={frame} />}

      {/* White flash overlay at cut points */}
      {flashOp > 0 && (
        <div style={{
          position: "absolute", inset: 0,
          background: C.white, opacity: flashOp,
          zIndex: 200, pointerEvents: "none",
        }} />
      )}
    </AbsoluteFill>
  );
};
