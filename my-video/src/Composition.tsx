import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const ORANGE = "#FF6B35";
const ORANGE_DARK = "#FF3D00";
const CREAM = "#FBF7F4";
const BLACK = "#0A0A0A";
const WHITE = "#FFFFFF";
const font = '-apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif';

// ── helpers ──────────────────────────────────────────────────────────────────

function fadeSlide(
  frame: number,
  from: number,
  fps: number,
  dir: "up" | "left" = "up"
) {
  const p = spring({
    fps,
    frame: frame - from,
    config: { damping: 22, stiffness: 120 },
    durationInFrames: 40,
  });
  const dist = 60;
  const tx = dir === "left" ? interpolate(p, [0, 1], [-dist, 0]) : 0;
  const ty = dir === "up" ? interpolate(p, [0, 1], [dist, 0]) : 0;
  const opacity = interpolate(p, [0, 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });
  return { opacity, transform: `translate(${tx}px, ${ty}px)` };
}

// ── sub-components ────────────────────────────────────────────────────────────

const ZubaLogo: React.FC<{ scale: number; opacity: number }> = ({
  scale,
  opacity,
}) => (
  <div
    style={{
      opacity,
      transform: `scale(${scale})`,
      display: "flex",
      alignItems: "center",
      gap: 20,
    }}
  >
    <div
      style={{
        width: 80,
        height: 80,
        borderRadius: 24,
        background: `linear-gradient(135deg, ${ORANGE}, ${ORANGE_DARK})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: `0 12px 40px ${ORANGE}66`,
      }}
    >
      <span
        style={{
          color: WHITE,
          fontFamily: font,
          fontWeight: 900,
          fontSize: 40,
          letterSpacing: -1,
        }}
      >
        Z
      </span>
    </div>
    <span
      style={{
        fontFamily: font,
        fontWeight: 900,
        fontSize: 52,
        color: BLACK,
        letterSpacing: -1.5,
      }}
    >
      ZUBA
    </span>
  </div>
);

const Hook: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const line1 = fadeSlide(frame, 0, fps, "up");
  const line2 = fadeSlide(frame, 12, fps, "up");
  const badge = fadeSlide(frame, 25, fps, "up");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 20,
        padding: "0 64px",
      }}
    >
      {/* Badge */}
      <div
        style={{
          ...badge,
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          background: `${ORANGE}18`,
          border: `1px solid ${ORANGE}40`,
          borderRadius: 100,
          padding: "10px 24px",
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: ORANGE,
          }}
        />
        <span
          style={{
            fontFamily: font,
            fontWeight: 700,
            fontSize: 28,
            color: ORANGE,
            letterSpacing: 1,
            textTransform: "uppercase",
          }}
        >
          Consultoría de Delivery · México
        </span>
      </div>

      {/* Headline */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <div
          style={{
            ...line1,
            fontFamily: font,
            fontWeight: 900,
            fontSize: 88,
            color: BLACK,
            lineHeight: 1.0,
            letterSpacing: -3,
          }}
        >
          Tu restaurante
        </div>
        <div
          style={{
            ...line1,
            fontFamily: font,
            fontWeight: 900,
            fontSize: 88,
            lineHeight: 1.0,
            letterSpacing: -3,
            background: `linear-gradient(135deg, ${ORANGE}, ${ORANGE_DARK})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          en el Top de
        </div>
        <div
          style={{
            ...line2,
            fontFamily: font,
            fontWeight: 900,
            fontSize: 88,
            color: BLACK,
            lineHeight: 1.0,
            letterSpacing: -3,
          }}
        >
          Uber Eats, Rappi
        </div>
        <div
          style={{
            ...line2,
            fontFamily: font,
            fontWeight: 900,
            fontSize: 88,
            color: BLACK,
            lineHeight: 1.0,
            letterSpacing: -3,
          }}
        >
          y DiDi.
        </div>
      </div>

      {/* Sub */}
      <div
        style={{
          ...badge,
          fontFamily: font,
          fontWeight: 300,
          fontSize: 38,
          color: "rgba(10,10,10,0.55)",
          lineHeight: 1.55,
          maxWidth: 820,
        }}
      >
        Optimizamos los 5 factores que el algoritmo premia.{" "}
        <strong style={{ fontWeight: 700, color: BLACK }}>
          Sin gastar en publicidad.
        </strong>
      </div>
    </div>
  );
};

const Stats: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const stats = [
    {
      n: "+65%",
      l: "Incremento en ventas",
      bg: `linear-gradient(135deg, ${ORANGE}, ${ORANGE_DARK})`,
      text: WHITE,
      sub: "rgba(255,255,255,0.75)",
    },
    {
      n: "Top 3",
      l: "En plataformas",
      bg: BLACK,
      text: WHITE,
      sub: "rgba(255,255,255,0.5)",
    },
    {
      n: "$0",
      l: "Sin crecimiento\n= sin fee",
      bg: "#F0FDF4",
      text: "#16a34a",
      sub: "rgba(22,163,74,0.65)",
      border: "1.5px solid rgba(22,163,74,0.25)",
    },
  ];

  return (
    <div
      style={{
        display: "flex",
        gap: 20,
        padding: "0 64px",
        flexWrap: "wrap",
      }}
    >
      {stats.map((s, i) => {
        const p = spring({
          fps,
          frame: frame - i * 10,
          config: { damping: 20, stiffness: 100 },
          durationInFrames: 35,
        });
        const opacity = interpolate(p, [0, 0.4], [0, 1], {
          extrapolateRight: "clamp",
        });
        const ty = interpolate(p, [0, 1], [50, 0]);

        return (
          <div
            key={s.n}
            style={{
              opacity,
              transform: `translateY(${ty}px)`,
              flex: "1 1 auto",
              background: s.bg,
              border: s.border ?? "none",
              borderRadius: 28,
              padding: "28px 32px",
              display: "flex",
              flexDirection: "column",
              gap: 6,
            }}
          >
            <div
              style={{
                fontFamily: font,
                fontWeight: 900,
                fontSize: 68,
                color: s.text,
                letterSpacing: -2,
                lineHeight: 1,
              }}
            >
              {s.n}
            </div>
            <div
              style={{
                fontFamily: font,
                fontWeight: 500,
                fontSize: 26,
                color: s.sub,
                lineHeight: 1.3,
                whiteSpace: "pre-line",
              }}
            >
              {s.l}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const Features: React.FC<{ frame: number; fps: number }> = ({
  frame,
  fps,
}) => {
  const items = [
    { icon: "📷", text: "Fotografía ×3 conversión" },
    { icon: "🗂", text: "Arquitectura de menú" },
    { icon: "💎", text: "Éxito compartido" },
  ];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 20,
        padding: "0 64px",
      }}
    >
      {items.map((item, i) => {
        const p = spring({
          fps,
          frame: frame - i * 12,
          config: { damping: 22, stiffness: 110 },
          durationInFrames: 35,
        });
        const opacity = interpolate(p, [0, 0.4], [0, 1], {
          extrapolateRight: "clamp",
        });
        const tx = interpolate(p, [0, 1], [-80, 0], {
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        });

        return (
          <div
            key={item.text}
            style={{
              opacity,
              transform: `translateX(${tx}px)`,
              display: "flex",
              alignItems: "center",
              gap: 24,
              background: WHITE,
              border: `1.5px solid ${ORANGE}25`,
              borderRadius: 28,
              padding: "28px 36px",
            }}
          >
            <div
              style={{
                width: 80,
                height: 80,
                borderRadius: 22,
                background: `${ORANGE}14`,
                border: `1.5px solid ${ORANGE}30`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 36,
                flexShrink: 0,
              }}
            >
              {item.icon}
            </div>
            <span
              style={{
                fontFamily: font,
                fontWeight: 700,
                fontSize: 40,
                color: BLACK,
                letterSpacing: -0.5,
              }}
            >
              {item.text}
            </span>
          </div>
        );
      })}
    </div>
  );
};

const CTA: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const p = spring({
    fps,
    frame,
    config: { damping: 18, stiffness: 90 },
    durationInFrames: 40,
  });
  const scale = interpolate(p, [0, 1], [0.85, 1]);
  const opacity = interpolate(p, [0, 0.4], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `scale(${scale})`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 24,
        padding: "0 64px",
        width: "100%",
      }}
    >
      <div
        style={{
          width: "100%",
          background: `linear-gradient(135deg, ${ORANGE}, ${ORANGE_DARK})`,
          borderRadius: 36,
          padding: "44px 48px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          boxShadow: `0 24px 64px ${ORANGE}55`,
        }}
      >
        <span
          style={{
            fontFamily: font,
            fontWeight: 900,
            fontSize: 52,
            color: WHITE,
            letterSpacing: -1,
          }}
        >
          Auditoría gratuita →
        </span>
        <span
          style={{
            fontFamily: font,
            fontWeight: 400,
            fontSize: 30,
            color: "rgba(255,255,255,0.75)",
          }}
        >
          Sin costo · Sin compromiso
        </span>
      </div>

      <span
        style={{
          fontFamily: font,
          fontWeight: 400,
          fontSize: 28,
          color: "rgba(10,10,10,0.35)",
          letterSpacing: 3,
          textTransform: "uppercase",
        }}
      >
        zubamx.vercel.app
      </span>
    </div>
  );
};

// ── scene layout ──────────────────────────────────────────────────────────────
// Total: 270 frames = 9s @ 30fps
// Scene 1 (0–90):   Hook — headline + badge + sub
// Scene 2 (90–180): Stats + features
// Scene 3 (180–270): CTA

export const ZubaTikTok: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Ambient glow pulse
  const glowOpacity = interpolate(
    Math.sin(frame * 0.04),
    [-1, 1],
    [0.12, 0.22]
  );

  // Scene transitions
  const scene1Out = interpolate(frame, [72, 90], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  const scene2In = interpolate(frame, [90, 110], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const scene2Out = interpolate(frame, [162, 180], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  const scene3In = interpolate(frame, [180, 200], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  const logoP = spring({
    fps,
    frame,
    config: { damping: 20, stiffness: 100 },
    durationInFrames: 40,
  });

  return (
    <AbsoluteFill style={{ backgroundColor: CREAM, overflow: "hidden" }}>
      {/* Ambient background glow */}
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${ORANGE}30 0%, transparent 70%)`,
          top: -300,
          left: -200,
          opacity: glowOpacity,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${ORANGE}18 0%, transparent 70%)`,
          bottom: -100,
          right: -100,
          opacity: glowOpacity * 0.7,
          pointerEvents: "none",
        }}
      />

      {/* ── Logo top ── */}
      <div
        style={{
          position: "absolute",
          top: 80,
          left: 64,
        }}
      >
        <ZubaLogo
          scale={logoP}
          opacity={interpolate(logoP, [0, 0.4], [0, 1], {
            extrapolateRight: "clamp",
          })}
        />
      </div>

      {/* ── Scene 1: Hook ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 36,
          opacity: 1 - scene1Out,
          transform: `translateY(${interpolate(scene1Out, [0, 1], [0, -80])}px)`,
        }}
      >
        <Hook frame={frame} fps={fps} />
      </div>

      {/* ── Scene 2: Stats + Features ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 36,
          opacity: scene2In * (1 - scene2Out),
          transform: `translateY(${interpolate(scene2In, [0, 1], [80, 0])}px)`,
        }}
      >
        <Stats frame={frame - 90} fps={fps} />
        <Features frame={frame - 115} fps={fps} />
      </div>

      {/* ── Scene 3: CTA ── */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 48,
          opacity: scene3In,
          transform: `translateY(${interpolate(scene3In, [0, 1], [80, 0])}px)`,
        }}
      >
        <div style={{ padding: "0 64px" }}>
          <ZubaLogo
            scale={1}
            opacity={1}
          />
        </div>
        <div style={{ padding: "0 64px" }}>
          <p
            style={{
              fontFamily: font,
              fontWeight: 900,
              fontSize: 80,
              color: BLACK,
              lineHeight: 1.05,
              letterSpacing: -2.5,
              margin: 0,
            }}
          >
            Si no creces,{" "}
            <span
              style={{
                background: `linear-gradient(135deg, ${ORANGE}, ${ORANGE_DARK})`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              no cobramos.
            </span>
          </p>
        </div>
        <CTA frame={frame - 195} fps={fps} />
      </div>
    </AbsoluteFill>
  );
};
