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
  black: "#0A0A0A",
  white: "#FFFFFF",
  cream: "#FBF7F4",
  green: "#25D366",
  muted: "rgba(255,255,255,0.55)",
};
const font =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif';

// ── Hooks copy ───────────────────────────────────────────────────────────────
const HOOKS = {
  pain: {
    line1: "¿Por qué tu restaurante",
    line2: "no aparece",
    line3: "en las apps?",
  },
  mecanismo: {
    line1: "El algoritmo decide",
    line2: "quién vende",
    line3: "y quién no.",
  },
  riesgo: {
    line1: "¿Cuánto llevas",
    line2: "perdiendo en apps",
    line3: "sin resultados?",
  },
};

const STEPS = [
  { icon: "🔍", title: "Diagnóstico", desc: "Auditamos tu cuenta completa" },
  { icon: "📸", title: "Fotografía", desc: "Imágenes que convierten" },
  { icon: "📐", title: "Menú estratégico", desc: "Nombre, precio y descripción" },
  { icon: "🚀", title: "Activación", desc: "Publicamos y monitoreamos" },
  { icon: "🎯", title: "Pauta interna", desc: "Top posición en plataformas" },
];

// ── Utils ────────────────────────────────────────────────────────────────────
function spr(frame: number, from: number, fps: number, damping = 22, stiffness = 120) {
  return spring({
    fps,
    frame: frame - from,
    config: { damping, stiffness },
    durationInFrames: 40,
  });
}

function fadeUp(frame: number, from: number, fps: number, dist = 50) {
  const p = spr(frame, from, fps);
  return {
    opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 1], [dist, 0])}px)`,
  };
}

function fadeLeft(frame: number, from: number, fps: number) {
  const p = spr(frame, from, fps, 20, 110);
  return {
    opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateX(${interpolate(p, [0, 1], [-70, 0], {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
    })}px)`,
  };
}

function sceneOpacity(frame: number, inStart: number, outStart: number) {
  const inVal = interpolate(frame, [inStart, inStart + 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const outVal = interpolate(frame, [outStart, outStart + 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  return Math.max(0, inVal - outVal);
}

// ── Scene 1: Hook (0–75f / 0–2.5s) ─────────────────────────────────────────
const SceneHook: React.FC<{ hook: Props["hook"]; frame: number; fps: number }> = ({
  hook,
  frame,
  fps,
}) => {
  const copy = HOOKS[hook];
  return (
    <AbsoluteFill
      style={{
        background: C.black,
        justifyContent: "center",
        alignItems: "flex-start",
        padding: "0 72px",
      }}
    >
      {/* Glow */}
      <div
        style={{
          position: "absolute",
          width: 700,
          height: 700,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${C.orange}28 0%, transparent 70%)`,
          top: -200,
          left: -200,
          pointerEvents: "none",
        }}
      />

      {/* Badge */}
      <div
        style={{
          ...fadeUp(frame, 0, fps, 30),
          position: "absolute",
          top: 160,
          left: 72,
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          background: `${C.orange}18`,
          border: `1px solid ${C.orange}40`,
          borderRadius: 100,
          padding: "10px 24px",
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: C.orange,
          }}
        />
        <span
          style={{
            fontFamily: font,
            fontWeight: 700,
            fontSize: 26,
            color: C.orange,
            letterSpacing: 0.5,
            textTransform: "uppercase",
          }}
        >
          Consultoría de Delivery · MX
        </span>
      </div>

      {/* Headline */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 80 }}>
        <div
          style={{
            ...fadeUp(frame, 8, fps),
            fontFamily: font,
            fontWeight: 900,
            fontSize: 96,
            color: C.white,
            lineHeight: 1.0,
            letterSpacing: -3,
          }}
        >
          {copy.line1}
        </div>
        <div
          style={{
            ...fadeUp(frame, 18, fps),
            fontFamily: font,
            fontWeight: 900,
            fontSize: 96,
            lineHeight: 1.0,
            letterSpacing: -3,
            background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          {copy.line2}
        </div>
        <div
          style={{
            ...fadeUp(frame, 28, fps),
            fontFamily: font,
            fontWeight: 900,
            fontSize: 96,
            color: C.white,
            lineHeight: 1.0,
            letterSpacing: -3,
          }}
        >
          {copy.line3}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 2: Problem (75–210f / 2.5–7s) ─────────────────────────────────────
const SceneProblem: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 75;
  const problems = [
    "Pocas estrellas y reseñas",
    "Fotos que no convierten",
    "Menú sin estrategia de precio",
    "Sin visibilidad en la búsqueda",
    "Pauta interna mal configurada",
  ];

  return (
    <AbsoluteFill
      style={{
        background: C.black,
        justifyContent: "center",
        padding: "0 72px",
        flexDirection: "column",
        gap: 0,
      }}
    >
      <div
        style={{
          ...fadeUp(f, 0, fps, 40),
          fontFamily: font,
          fontWeight: 900,
          fontSize: 68,
          color: C.white,
          lineHeight: 1.1,
          letterSpacing: -2,
          marginBottom: 48,
        }}
      >
        El algoritmo premia{" "}
        <span
          style={{
            background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          5 factores.
        </span>
        {"\n"}Si fallas en uno,{"\n"}no apareces.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {problems.map((p, i) => {
          const itemF = f - i * 10;
          const sp = spr(itemF, 10, fps, 25, 100);
          const op = interpolate(sp, [0, 0.4], [0, 1], { extrapolateRight: "clamp" });
          const tx = interpolate(sp, [0, 1], [-60, 0], {
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          });
          return (
            <div
              key={p}
              style={{
                opacity: op,
                transform: `translateX(${tx}px)`,
                display: "flex",
                alignItems: "center",
                gap: 20,
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: C.orange,
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontFamily: font,
                  fontWeight: 500,
                  fontSize: 38,
                  color: "rgba(255,255,255,0.75)",
                }}
              >
                {p}
              </span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 3: Solution — 5 pasos (210–420f / 7–14s) ──────────────────────────
const SceneSolution: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 210;

  return (
    <AbsoluteFill
      style={{
        background: C.cream,
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 64px",
        gap: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          ...fadeUp(f, 0, fps, 40),
          marginBottom: 44,
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            background: `${C.orange}18`,
            border: `1px solid ${C.orange}35`,
            borderRadius: 100,
            padding: "8px 20px",
            marginBottom: 16,
          }}
        >
          <span
            style={{
              fontFamily: font,
              fontWeight: 700,
              fontSize: 24,
              color: C.orange,
              textTransform: "uppercase",
              letterSpacing: 1,
            }}
          >
            ZUBA · Así funciona
          </span>
        </div>
        <div
          style={{
            fontFamily: font,
            fontWeight: 900,
            fontSize: 72,
            color: C.black,
            lineHeight: 1.05,
            letterSpacing: -2.5,
          }}
        >
          No es marketing.{"\n"}
          <span
            style={{
              background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Es operación.
          </span>
        </div>
      </div>

      {/* Steps */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {STEPS.map((step, i) => {
          const style = fadeLeft(f, 20 + i * 18, fps);
          return (
            <div
              key={step.title}
              style={{
                ...style,
                display: "flex",
                alignItems: "center",
                gap: 24,
                background: C.white,
                border: `1.5px solid ${C.orange}20`,
                borderRadius: 24,
                padding: "22px 28px",
              }}
            >
              <div
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: 20,
                  background: `${C.orange}12`,
                  border: `1.5px solid ${C.orange}25`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 30,
                  flexShrink: 0,
                }}
              >
                {step.icon}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span
                  style={{
                    fontFamily: font,
                    fontWeight: 800,
                    fontSize: 36,
                    color: C.black,
                    letterSpacing: -0.5,
                  }}
                >
                  {step.title}
                </span>
                <span
                  style={{
                    fontFamily: font,
                    fontWeight: 400,
                    fontSize: 26,
                    color: "rgba(10,10,10,0.45)",
                  }}
                >
                  {step.desc}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── Scene 4: Risk reversal + CTA (420–600f / 14–20s) ────────────────────────
const SceneCTA: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const f = frame - 420;

  const logoP = spr(f, 0, fps, 20, 90);
  const taglineStyle = fadeUp(f, 15, fps, 40);
  const guaranteeStyle = fadeUp(f, 30, fps, 50);
  const ctaStyle = {
    ...fadeUp(f, 55, fps, 40),
  };
  const subStyle = fadeUp(f, 75, fps, 30);

  const scale = interpolate(spr(f, 55, fps, 18, 90), [0, 1], [0.9, 1]);

  return (
    <AbsoluteFill
      style={{
        background: C.black,
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 64px",
        gap: 0,
      }}
    >
      {/* Glow */}
      <div
        style={{
          position: "absolute",
          width: 800,
          height: 800,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${C.orange}22 0%, transparent 70%)`,
          top: -200,
          right: -300,
          pointerEvents: "none",
        }}
      />

      {/* Logo */}
      <div
        style={{
          opacity: interpolate(logoP, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
          transform: `scale(${interpolate(logoP, [0, 1], [0.85, 1])})`,
          display: "flex",
          alignItems: "center",
          gap: 18,
          marginBottom: 56,
        }}
      >
        <div
          style={{
            width: 72,
            height: 72,
            borderRadius: 22,
            background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: `0 12px 40px ${C.orange}55`,
          }}
        >
          <span
            style={{
              color: C.white,
              fontFamily: font,
              fontWeight: 900,
              fontSize: 36,
            }}
          >
            Z
          </span>
        </div>
        <span
          style={{
            fontFamily: font,
            fontWeight: 900,
            fontSize: 48,
            color: C.white,
            letterSpacing: -1.5,
          }}
        >
          ZUBA
        </span>
      </div>

      {/* Guarantee */}
      <div
        style={{
          ...guaranteeStyle,
          textAlign: "center",
          marginBottom: 52,
        }}
      >
        <div
          style={{
            fontFamily: font,
            fontWeight: 900,
            fontSize: 88,
            color: C.white,
            lineHeight: 1.0,
            letterSpacing: -3,
          }}
        >
          Si no creces,
        </div>
        <div
          style={{
            fontFamily: font,
            fontWeight: 900,
            fontSize: 88,
            lineHeight: 1.0,
            letterSpacing: -3,
            background: `linear-gradient(135deg, ${C.orange}, ${C.orangeDark})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          no cobramos.
        </div>
      </div>

      {/* Tagline */}
      <div
        style={{
          ...taglineStyle,
          fontFamily: font,
          fontWeight: 300,
          fontSize: 34,
          color: C.muted,
          textAlign: "center",
          lineHeight: 1.5,
          maxWidth: 780,
          marginBottom: 64,
        }}
      >
        Operación técnica de delivery en{" "}
        <span style={{ color: C.white, fontWeight: 600 }}>
          Uber Eats, Rappi y DiDi.
        </span>
      </div>

      {/* CTA Button — WhatsApp */}
      <div
        style={{
          ...ctaStyle,
          transform: `${ctaStyle.transform ?? ""} scale(${scale})`,
          width: "100%",
          background: C.green,
          borderRadius: 32,
          padding: "44px 48px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          boxShadow: `0 20px 60px ${C.green}44`,
          marginBottom: 28,
        }}
      >
        {/* WhatsApp icon */}
        <svg width="48" height="48" viewBox="0 0 24 24" fill="white">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
        </svg>
        <span
          style={{
            fontFamily: font,
            fontWeight: 800,
            fontSize: 46,
            color: C.white,
            letterSpacing: -0.5,
          }}
        >
          Auditoría gratis →
        </span>
      </div>

      {/* Sub */}
      <div
        style={{
          ...subStyle,
          fontFamily: font,
          fontWeight: 400,
          fontSize: 28,
          color: "rgba(255,255,255,0.3)",
          letterSpacing: 3,
          textTransform: "uppercase",
        }}
      >
        Sin costo · Sin compromiso
      </div>
    </AbsoluteFill>
  );
};

// ── Main composition ──────────────────────────────────────────────────────────
export const ZubaAd: React.FC<Props> = ({ hook }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene visibility
  const s1 = sceneOpacity(frame, 0, 60);
  const s2 = sceneOpacity(frame, 65, 195);
  const s3 = sceneOpacity(frame, 200, 400);
  const s4 = sceneOpacity(frame, 410, 620);

  return (
    <AbsoluteFill style={{ background: C.black, overflow: "hidden" }}>
      {/* Scene 1 — Hook */}
      <AbsoluteFill style={{ opacity: s1 }}>
        <SceneHook hook={hook} frame={frame} fps={fps} />
      </AbsoluteFill>

      {/* Scene 2 — Problem */}
      <AbsoluteFill style={{ opacity: s2 }}>
        <SceneProblem frame={frame} fps={fps} />
      </AbsoluteFill>

      {/* Scene 3 — Solution */}
      <AbsoluteFill style={{ opacity: s3 }}>
        <SceneSolution frame={frame} fps={fps} />
      </AbsoluteFill>

      {/* Scene 4 — CTA */}
      <AbsoluteFill style={{ opacity: s4 }}>
        <SceneCTA frame={frame} fps={fps} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
