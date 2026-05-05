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

// ── Brand ────────────────────────────────────────────────────────────────────
const C = {
  orange: "#FF6B35",
  orangeDark: "#FF3D00",
  orange2: "#FF8C42",
  black: "#0A0A0A",
  dark: "#111111",
  white: "#FFFFFF",
  cream: "#FBF7F4",
  green: "#25D366",
  muted: "rgba(255,255,255,0.5)",
  card: "rgba(255,255,255,0.06)",
  cardBorder: "rgba(255,255,255,0.1)",
};
const font =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif';

// ── Voiceover scripts (place generated MP3 in public/vo-pain.mp3 etc.) ───────
// Hook "pain":      "¿Tu restaurante está en Uber Eats o Rappi… y casi no te llegan pedidos?
//                    El problema no es tu comida. Es cómo te ve el algoritmo.
//                    ZUBA optimiza los 5 factores que las apps premian:
//                    foto, menú, rating, horarios y pauta interna.
//                    Operación técnica completa. Y si no creces… no cobramos.
//                    Agenda tu auditoría gratis hoy."
//
// Hook "mecanismo": "El algoritmo de Uber Eats, Rappi y DiDi decide quién aparece primero.
//                    Y premia exactamente 5 cosas. Si fallas en una, quedas abajo.
//                    ZUBA entra a tu operación y optimiza las 5 por ti.
//                    Sin gastar en publicidad externa. Si no creces, no cobramos."
//
// Hook "riesgo":    "¿Cuánto llevas perdiendo en apps sin ver resultados reales?
//                    El problema casi siempre es el mismo: operación mal configurada.
//                    ZUBA lo arregla todo: foto, menú, rating, horarios y pauta interna.
//                    Con garantía: si no creces, no pagas."

// ── Utils ────────────────────────────────────────────────────────────────────
const spr = (frame: number, from: number, fps: number, d = 22, s = 120) =>
  spring({ fps, frame: frame - from, config: { damping: d, stiffness: s }, durationInFrames: 45 });

const op = (p: number, edge = 0.35) =>
  interpolate(p, [0, edge], [0, 1], { extrapolateRight: "clamp" });

function fadeUp(frame: number, from: number, fps: number, dist = 55) {
  const p = spr(frame, from, fps);
  return {
    opacity: op(p),
    transform: `translateY(${interpolate(p, [0, 1], [dist, 0])}px)`,
  };
}

function fadeLeft(frame: number, from: number, fps: number, dist = 80) {
  const p = spr(frame, from, fps, 20, 100);
  return {
    opacity: op(p),
    transform: `translateX(${interpolate(p, [0, 1], [-dist, 0], {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    })}px)`,
  };
}

function sceneBlend(frame: number, inF: number, outF: number) {
  const i = interpolate(frame, [inF, inF + 22], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const o = interpolate(frame, [outF, outF + 18], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  return Math.max(0, i - o);
}

// ── Ambient orbs ─────────────────────────────────────────────────────────────
const Orb: React.FC<{ x: number; y: number; size: number; color: string; opacity: number }> = ({
  x, y, size, color, opacity,
}) => (
  <div style={{
    position: "absolute", left: x, top: y, width: size, height: size,
    borderRadius: "50%",
    background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
    opacity, transform: "translate(-50%,-50%)", pointerEvents: "none",
  }} />
);

// ── ZUBA Logo ─────────────────────────────────────────────────────────────────
const Logo: React.FC<{ size?: "sm" | "md" }> = ({ size = "md" }) => {
  const box = size === "md" ? 72 : 52;
  const fontSize = size === "md" ? 36 : 26;
  const textSize = size === "md" ? 46 : 34;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <div style={{
        width: box, height: box, borderRadius: box * 0.3,
        background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
        display: "flex", alignItems: "center", justifyContent: "center",
        boxShadow: `0 8px 32px ${C.orange}55`,
      }}>
        <span style={{ color: C.white, fontFamily: font, fontWeight: 900, fontSize }}> Z </span>
      </div>
      <span style={{ fontFamily: font, fontWeight: 900, fontSize: textSize, color: C.white, letterSpacing: -1 }}>
        ZUBA
      </span>
    </div>
  );
};

// ── Badge ────────────────────────────────────────────────────────────────────
const Tag: React.FC<{ children: string; dark?: boolean }> = ({ children, dark }) => (
  <div style={{
    display: "inline-flex", alignItems: "center", gap: 10,
    background: dark ? `${C.orange}22` : `${C.black}18`,
    border: `1px solid ${dark ? C.orange + "45" : C.orange + "35"}`,
    borderRadius: 100, padding: "10px 24px",
  }}>
    <div style={{ width: 7, height: 7, borderRadius: "50%", background: C.orange }} />
    <span style={{
      fontFamily: font, fontWeight: 700, fontSize: 24,
      color: dark ? C.orange : C.orange,
      letterSpacing: 0.5, textTransform: "uppercase",
    }}>{children}</span>
  </div>
);

// ────────────────────────────────────────────────────────────────────────────
// SCENE 1 — HOOK  (0–75f · 2.5s)
// ────────────────────────────────────────────────────────────────────────────
const HOOKS = {
  pain:      { l1: "¿Por qué tu", l2: "restaurante no", l3: "vende en apps?" },
  mecanismo: { l1: "El algoritmo", l2: "decide quién", l3: "vende y quién no." },
  riesgo:    { l1: "¿Cuánto llevas", l2: "perdiendo en apps", l3: "sin resultados?" },
};

const SceneHook: React.FC<{ hook: Props["hook"]; frame: number; fps: number }> = ({ hook, frame, fps }) => {
  const h = HOOKS[hook];
  const pulse = interpolate(Math.sin(frame * 0.06), [-1, 1], [0.18, 0.28]);

  return (
    <AbsoluteFill style={{ background: C.black, overflow: "hidden" }}>
      <Orb x={180} y={350} size={700} color={`${C.orange}35`} opacity={pulse} />
      <Orb x={900} y={1500} size={500} color={`${C.orangeDark}20`} opacity={pulse * 0.7} />

      {/* Grid */}
      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `linear-gradient(${C.orange}08 1px, transparent 1px),
                          linear-gradient(90deg, ${C.orange}08 1px, transparent 1px)`,
        backgroundSize: "90px 90px",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center", padding: "0 72px", gap: 32,
      }}>
        <div style={fadeUp(frame, 0, fps, 30)}>
          <Tag dark>Consultoría · Uber Eats · Rappi · DiDi</Tag>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {[h.l1, h.l2, h.l3].map((line, i) => (
            <div key={i} style={{
              ...fadeUp(frame, 10 + i * 14, fps),
              fontFamily: font, fontWeight: 900,
              fontSize: i === 1 ? 100 : 90,
              lineHeight: 1.0, letterSpacing: -3.5,
              color: i === 1 ? "transparent" : C.white,
              background: i === 1
                ? `linear-gradient(135deg, ${C.orange}, ${C.orange2})`
                : "none",
              WebkitBackgroundClip: i === 1 ? "text" : "unset",
              WebkitTextFillColor: i === 1 ? "transparent" : C.white,
            }}>
              {line}
            </div>
          ))}
        </div>

        {/* Animated underline */}
        <div style={{
          ...fadeUp(frame, 45, fps),
          height: 4, borderRadius: 2,
          background: `linear-gradient(90deg, ${C.orange}, ${C.orangeDark}, transparent)`,
          width: interpolate(spr(frame, 45, fps), [0, 1], [0, 600]),
        }} />

        <div style={{
          ...fadeUp(frame, 52, fps),
          fontFamily: font, fontWeight: 300, fontSize: 34,
          color: C.muted, lineHeight: 1.5,
        }}>
          No es tu comida.{" "}
          <span style={{ color: C.white, fontWeight: 600 }}>Es cómo te ve el algoritmo.</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SCENE 2 — PROBLEMA  (75–210f · 2.5–7s)
// ────────────────────────────────────────────────────────────────────────────
const PROBLEMS = [
  { icon: "📉", text: "Rating bajo en plataformas" },
  { icon: "📷", text: "Fotos que no convierten" },
  { icon: "📋", text: "Menú sin estrategia de precio" },
  { icon: "🔍", text: "Sin visibilidad en búsqueda" },
  { icon: "📢", text: "Pauta interna mal configurada" },
];

const SceneProblem: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 75;
  return (
    <AbsoluteFill style={{ background: C.dark, overflow: "hidden" }}>
      <Orb x={1000} y={300} size={600} color={`${C.orangeDark}20`} opacity={0.6} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        justifyContent: "center", padding: "0 68px", gap: 44,
      }}>
        <div style={fadeUp(f, 0, fps, 40)}>
          <div style={{
            fontFamily: font, fontWeight: 900,
            fontSize: 72, color: C.white,
            lineHeight: 1.1, letterSpacing: -2.5,
          }}>
            El algoritmo premia{" "}
            <span style={{
              background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>5 factores.</span>
          </div>
          <div style={{
            fontFamily: font, fontWeight: 400, fontSize: 36,
            color: C.muted, marginTop: 12,
          }}>
            Fallar en uno te manda al fondo.
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          {PROBLEMS.map((p, i) => {
            const pf = f - i * 12;
            const sp = spr(pf, 12, fps, 22, 100);
            return (
              <div key={p.text} style={{
                opacity: op(sp),
                transform: `translateX(${interpolate(sp, [0, 1], [-80, 0], {
                  easing: Easing.bezier(0.16, 1, 0.3, 1),
                })}px)`,
                display: "flex", alignItems: "center", gap: 22,
                background: C.card,
                border: `1px solid ${C.cardBorder}`,
                borderRadius: 22, padding: "20px 28px",
              }}>
                <div style={{
                  width: 68, height: 68, borderRadius: 18,
                  background: `${C.orange}15`,
                  border: `1.5px solid ${C.orange}30`,
                  display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: 28, flexShrink: 0,
                }}>{p.icon}</div>
                <span style={{
                  fontFamily: font, fontWeight: 600,
                  fontSize: 36, color: "rgba(255,255,255,0.8)",
                }}>{p.text}</span>
                <div style={{
                  marginLeft: "auto", width: 36, height: 36,
                  borderRadius: "50%", background: "rgba(255,60,0,0.2)",
                  display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: 20, flexShrink: 0,
                }}>✕</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SCENE 3 — SOLUCIÓN  (210–420f · 7–14s)
// ────────────────────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", icon: "🔍", title: "Diagnóstico completo", desc: "Auditamos tu cuenta en todas las apps" },
  { n: "02", icon: "📸", title: "Fotografía de impacto", desc: "Sesión profesional que convierte" },
  { n: "03", icon: "📐", title: "Menú estratégico", desc: "Nombre, precio y descripción optimizados" },
  { n: "04", icon: "🚀", title: "Activación y seguimiento", desc: "Monitoreamos el crecimiento semana a semana" },
  { n: "05", icon: "🎯", title: "Pauta interna", desc: "Top posición en las plataformas" },
];

const SceneSolution: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 210;
  return (
    <AbsoluteFill style={{ background: C.cream, overflow: "hidden" }}>
      {/* Orange glow top-right */}
      <div style={{
        position: "absolute", top: -100, right: -100,
        width: 500, height: 500, borderRadius: "50%",
        background: `radial-gradient(circle, ${C.orange}20 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{
        position: "absolute", inset: 0,
        display: "flex", flexDirection: "column",
        padding: "0 64px", justifyContent: "center", gap: 32,
      }}>
        {/* Header */}
        <div style={fadeUp(f, 0, fps, 40)}>
          <Tag>ZUBA · Así funciona</Tag>
          <div style={{
            fontFamily: font, fontWeight: 900,
            fontSize: 76, color: C.black,
            lineHeight: 1.05, letterSpacing: -2.5, marginTop: 20,
          }}>
            No es marketing.{"\n"}
            <span style={{
              background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            }}>Es operación.</span>
          </div>
        </div>

        {/* Steps */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {STEPS.map((step, i) => {
            const style = fadeLeft(f, 25 + i * 16, fps);
            const isHighlight = i === 0;
            return (
              <div key={step.n} style={{
                ...style,
                display: "flex", alignItems: "center", gap: 20,
                background: isHighlight
                  ? `linear-gradient(135deg, ${C.orange}18, ${C.orange}08)`
                  : C.white,
                border: `1.5px solid ${isHighlight ? C.orange + "40" : "rgba(0,0,0,0.07)"}`,
                borderRadius: 24, padding: "18px 24px",
                boxShadow: isHighlight ? `0 4px 24px ${C.orange}18` : "none",
              }}>
                <div style={{
                  width: 64, height: 64, borderRadius: 18,
                  background: `${C.orange}14`,
                  border: `1.5px solid ${C.orange}30`,
                  display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: 26, flexShrink: 0,
                }}>{step.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontFamily: font, fontWeight: 800,
                    fontSize: 32, color: C.black, letterSpacing: -0.5,
                  }}>{step.title}</div>
                  <div style={{
                    fontFamily: font, fontWeight: 400,
                    fontSize: 24, color: "rgba(10,10,10,0.45)", marginTop: 2,
                  }}>{step.desc}</div>
                </div>
                <div style={{
                  fontFamily: font, fontWeight: 900,
                  fontSize: 28, color: `${C.orange}60`,
                }}>{step.n}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// SCENE 4 — CTA  (420–600f · 14–20s)
// ────────────────────────────────────────────────────────────────────────────
const SceneCTA: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 420;
  const pulse = interpolate(Math.sin(f * 0.1), [-1, 1], [0.85, 1.0]);

  return (
    <AbsoluteFill style={{ background: C.black, overflow: "hidden" }}>
      <Orb x={540} y={400} size={900} color={`${C.orange}20`} opacity={0.9} />
      <Orb x={100} y={1700} size={400} color={`${C.orangeDark}25`} opacity={0.6} />

      <div style={{
        position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", justifyContent: "center",
        alignItems: "center", padding: "0 64px", gap: 0,
      }}>
        {/* Logo */}
        <div style={{ ...fadeUp(f, 0, fps, 40), marginBottom: 52 }}>
          <Logo size="md" />
        </div>

        {/* Guarantee */}
        <div style={{ ...fadeUp(f, 18, fps, 50), textAlign: "center", marginBottom: 32 }}>
          <div style={{
            fontFamily: font, fontWeight: 900,
            fontSize: 92, color: C.white,
            lineHeight: 1.0, letterSpacing: -3.5,
          }}>Si no creces,</div>
          <div style={{
            fontFamily: font, fontWeight: 900,
            fontSize: 92, lineHeight: 1.0, letterSpacing: -3.5,
            background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
          }}>no cobramos.</div>
        </div>

        {/* Sub */}
        <div style={{
          ...fadeUp(f, 30, fps, 35),
          fontFamily: font, fontWeight: 300, fontSize: 32,
          color: C.muted, textAlign: "center",
          lineHeight: 1.6, maxWidth: 780, marginBottom: 72,
        }}>
          Operación técnica completa en{" "}
          <span style={{ color: C.white, fontWeight: 600 }}>Uber Eats, Rappi y DiDi.</span>
          {"\n"}Sin gastar en publicidad externa.
        </div>

        {/* WhatsApp CTA */}
        <div style={{
          ...fadeUp(f, 50, fps, 40),
          width: "100%",
          transform: `${fadeUp(f, 50, fps, 40).transform} scale(${pulse})`,
          background: C.green,
          borderRadius: 32, padding: "42px 48px",
          display: "flex", alignItems: "center",
          justifyContent: "center", gap: 18,
          boxShadow: `0 24px 64px ${C.green}55`,
          marginBottom: 28,
        }}>
          <svg width="44" height="44" viewBox="0 0 24 24" fill="white">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          <span style={{
            fontFamily: font, fontWeight: 800,
            fontSize: 48, color: C.white, letterSpacing: -0.5,
          }}>Auditoría gratis →</span>
        </div>

        {/* Domain */}
        <div style={{
          ...fadeUp(f, 70, fps, 20),
          fontFamily: font, fontWeight: 400,
          fontSize: 26, color: "rgba(255,255,255,0.28)",
          letterSpacing: 4, textTransform: "uppercase",
        }}>
          zubamx.vercel.app · Sin compromiso
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Main ─────────────────────────────────────────────────────────────────────
export const ZubaAd: React.FC<Props> = ({ hook }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s1 = sceneBlend(frame, 0, 58);
  const s2 = sceneBlend(frame, 63, 195);
  const s3 = sceneBlend(frame, 200, 402);
  const s4 = sceneBlend(frame, 408, 660);

  // Volume: fade in first 30f, fade out last 30f
  const musicVol = interpolate(frame, [0, 30, 570, 600], [0, 0.18, 0.18, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: C.black, overflow: "hidden" }}>
      {/* Background music — place bg-music.mp3 in public/ */}
      {/* Voiceover — place vo-pain.mp3 / vo-mecanismo.mp3 / vo-riesgo.mp3 in public/ */}
      <Audio src={staticFile("bg-music.wav")} volume={musicVol} loop />
      <Audio src={staticFile(`vo-${hook}.wav`)} volume={1} />

      <AbsoluteFill style={{ opacity: s1 }}>
        <SceneHook hook={hook} frame={frame} fps={fps} />
      </AbsoluteFill>

      <AbsoluteFill style={{ opacity: s2 }}>
        <SceneProblem frame={frame} fps={fps} />
      </AbsoluteFill>

      <AbsoluteFill style={{ opacity: s3 }}>
        <SceneSolution frame={frame} fps={fps} />
      </AbsoluteFill>

      <AbsoluteFill style={{ opacity: s4 }}>
        <SceneCTA frame={frame} fps={fps} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
