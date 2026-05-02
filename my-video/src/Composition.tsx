import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif';

// Brand colors
const PURPLE = "#7C3AED";
const PINK = "#EC4899";
const WHITE = "#FFFFFF";
const BG = "#0A0A0A";

const features = [
  { emoji: "⚡", text: "Pagos instantáneos" },
  { emoji: "🔒", text: "100% seguro" },
  { emoji: "💸", text: "Sin comisiones" },
];

const Logo: React.FC<{ progress: number }> = ({ progress }) => {
  const scale = interpolate(progress, [0, 1], [0.6, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(progress, [0, 0.4], [0, 1], {
    extrapolateLeft: "clamp",
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
        gap: 16,
      }}
    >
      <div
        style={{
          fontSize: 140,
          fontWeight: 900,
          fontFamily,
          background: `linear-gradient(135deg, ${PURPLE}, ${PINK})`,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          letterSpacing: -4,
          lineHeight: 1,
        }}
      >
        ZUBA
      </div>
      <div
        style={{
          fontSize: 36,
          fontWeight: 400,
          fontFamily,
          color: "rgba(255,255,255,0.7)",
          letterSpacing: 8,
          textTransform: "uppercase",
        }}
      >
        Tu dinero, tu poder
      </div>
    </div>
  );
};

const FeatureRow: React.FC<{
  emoji: string;
  text: string;
  progress: number;
}> = ({ emoji, text, progress }) => {
  const x = interpolate(progress, [0, 1], [-120, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const opacity = interpolate(progress, [0, 0.5], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 24,
        transform: `translateX(${x}px)`,
        opacity,
      }}
    >
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: 24,
          background: `linear-gradient(135deg, ${PURPLE}33, ${PINK}33)`,
          border: `2px solid ${PURPLE}66`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 36,
          flexShrink: 0,
        }}
      >
        {emoji}
      </div>
      <div
        style={{
          fontSize: 44,
          fontWeight: 700,
          fontFamily,
          color: WHITE,
        }}
      >
        {text}
      </div>
    </div>
  );
};

const GlowOrb: React.FC<{
  x: number;
  y: number;
  color: string;
  size: number;
  opacity: number;
}> = ({ x, y, color, size, opacity }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: size,
      height: size,
      borderRadius: "50%",
      background: color,
      filter: `blur(${size * 0.4}px)`,
      opacity,
      transform: "translate(-50%, -50%)",
    }}
  />
);

export const ZubaTikTok: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Phase 1: Logo reveal (0-60)
  const logoProgress = spring({
    fps,
    frame,
    config: { damping: 18, stiffness: 80 },
    durationInFrames: 50,
  });

  // Phase 2: Features slide in (60-150)
  const featuresStart = 60;
  const featureProgresses = features.map((_, i) =>
    spring({
      fps,
      frame: frame - featuresStart - i * 15,
      config: { damping: 20, stiffness: 100 },
      durationInFrames: 35,
    })
  );

  // Phase 3: CTA (150-210)
  const ctaProgress = spring({
    fps,
    frame: frame - 150,
    config: { damping: 15, stiffness: 80 },
    durationInFrames: 40,
  });

  const ctaScale = interpolate(ctaProgress, [0, 1], [0.8, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Ambient orb pulse
  const pulse = interpolate(frame, [0, 60], [0.15, 0.25], {
    extrapolateRight: "clamp",
  });

  const featuresOpacity = interpolate(frame, [55, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const logoY = interpolate(frame, [55, 80], [0, -220], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });

  return (
    <AbsoluteFill style={{ backgroundColor: BG, overflow: "hidden" }}>
      {/* Background glow orbs */}
      <GlowOrb x={200} y={400} color={PURPLE} size={500} opacity={pulse} />
      <GlowOrb
        x={900}
        y={1600}
        color={PINK}
        size={400}
        opacity={pulse * 0.8}
      />
      <GlowOrb
        x={1000}
        y={600}
        color={PURPLE}
        size={300}
        opacity={pulse * 0.6}
      />

      {/* Grid lines */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(124,58,237,0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(124,58,237,0.05) 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
        }}
      />

      {/* Logo section */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 1920,
          transform: `translateY(${logoY}px)`,
        }}
      >
        <Logo progress={logoProgress} />
      </div>

      {/* Features section */}
      <div
        style={{
          position: "absolute",
          top: 820,
          left: 80,
          right: 80,
          display: "flex",
          flexDirection: "column",
          gap: 40,
          opacity: featuresOpacity,
        }}
      >
        {features.map((f, i) => (
          <FeatureRow
            key={f.text}
            emoji={f.emoji}
            text={f.text}
            progress={featureProgresses[i]}
          />
        ))}
      </div>

      {/* CTA */}
      <div
        style={{
          position: "absolute",
          bottom: 180,
          left: 80,
          right: 80,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 32,
          opacity: ctaProgress,
          transform: `scale(${ctaScale})`,
        }}
      >
        <div
          style={{
            width: "100%",
            height: 120,
            borderRadius: 36,
            background: `linear-gradient(135deg, ${PURPLE}, ${PINK})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: `0 20px 60px ${PURPLE}66`,
          }}
        >
          <span
            style={{
              fontSize: 48,
              fontWeight: 900,
              fontFamily,
              color: WHITE,
              letterSpacing: 2,
            }}
          >
            Descarga gratis →
          </span>
        </div>
        <div
          style={{
            fontSize: 32,
            fontFamily,
            color: "rgba(255,255,255,0.4)",
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          zuba.mx
        </div>
      </div>
    </AbsoluteFill>
  );
};
