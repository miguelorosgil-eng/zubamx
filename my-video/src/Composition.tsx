import { Audio, Sequence, staticFile, AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";

export const ZubaAdSchema = z.object({ hook: z.enum(["pain", "mecanismo", "riesgo"]) });
type Props = z.infer<typeof ZubaAdSchema>;

const C = {
  bg:         "#0F0F0F",
  orange:     "#FF5100",
  orangeGlow: "rgba(255,81,0,0.45)",
  orangeDim:  "rgba(255,81,0,0.08)",
  border:     "rgba(255,81,0,0.22)",
  white:      "#FFFFFF",
  gray:       "rgba(255,255,255,0.38)",
  grayMid:    "rgba(255,255,255,0.55)",
};
const font = '"Helvetica Neue",Helvetica,Arial,sans-serif';
const FAST = 18;

const prog = (f: number, at: number, dur = FAST) =>
  Math.min(1, Math.max(0, (f - at) / dur));

const slideY = (p: number, dist = 36) =>
  `translateY(${interpolate(p, [0, 1], [dist, 0])}px)`;

// ─── Film grain ───────────────────────────────────────────────────────────────
const Grain: React.FC<{ frame: number }> = ({ frame }) => (
  <svg style={{ position:"absolute", inset:0, width:"100%", height:"100%", pointerEvents:"none", zIndex:80, opacity:0.042 }}>
    <filter id={`gr${frame % 64}`}>
      <feTurbulence type="fractalNoise" baseFrequency="0.78" numOctaves="4" seed={frame % 64} stitchTiles="stitch" />
      <feColorMatrix type="saturate" values="0" />
    </filter>
    <rect width="100%" height="100%" filter={`url(#gr${frame % 64})`} />
  </svg>
);

// ─── B-Roll placeholder ───────────────────────────────────────────────────────
const BRoll: React.FC<{ label: string; frame: number; at: number; h?: number }> =
  ({ label, frame, at, h = 280 }) => {
    const p = prog(frame, at);
    const blink = Math.sin(frame * 0.14) > 0.1;
    return (
      <div style={{
        opacity:p, transform:slideY(p, 44),
        background:"#0d0d0d", border:`1px solid ${C.border}`,
        borderRadius:4, overflow:"hidden", position:"relative", height:h, flexShrink:0,
      }}>
        <div style={{ position:"absolute", inset:0, background:"linear-gradient(150deg,#1c0800 0%,#0d0400 45%,#030000 100%)" }} />
        <div style={{ position:"absolute", inset:0, backgroundImage:"repeating-linear-gradient(0deg,transparent 0,transparent 3px,rgba(0,0,0,0.14) 3px,rgba(0,0,0,0.14) 4px)" }} />
        <div style={{ position:"absolute", top:14, left:14, width:26, height:26, borderTop:`2px solid ${C.orange}`, borderLeft:`2px solid ${C.orange}`, opacity:0.55 }} />
        <div style={{ position:"absolute", top:14, right:14, width:26, height:26, borderTop:`2px solid ${C.orange}`, borderRight:`2px solid ${C.orange}`, opacity:0.55 }} />
        <div style={{ position:"absolute", bottom:14, left:14, width:26, height:26, borderBottom:`2px solid ${C.orange}`, borderLeft:`2px solid ${C.orange}`, opacity:0.55 }} />
        <div style={{ position:"absolute", bottom:14, right:14, width:26, height:26, borderBottom:`2px solid ${C.orange}`, borderRight:`2px solid ${C.orange}`, opacity:0.55 }} />
        <div style={{ position:"absolute", top:18, right:48, display:"flex", alignItems:"center", gap:5 }}>
          <div style={{ width:7, height:7, borderRadius:"50%", background:"#ff2020", opacity:blink ? 1 : 0 }} />
          <span style={{ fontFamily:font, fontWeight:800, fontSize:10, color:"rgba(255,255,255,0.45)", letterSpacing:2.5 }}>REC</span>
        </div>
        <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:8 }}>
          <span style={{ fontFamily:font, fontWeight:800, fontSize:12, color:`rgba(255,81,0,0.55)`, letterSpacing:4, textTransform:"uppercase" }}>{label}</span>
          <span style={{ fontFamily:font, fontWeight:400, fontSize:10, color:"rgba(255,255,255,0.22)", letterSpacing:3, textTransform:"uppercase" }}>Replace with 4K footage</span>
        </div>
        <div style={{ position:"absolute", bottom:0, left:0, right:0, background:"rgba(255,81,0,0.06)", borderTop:`1px solid ${C.border}`, padding:"6px 14px", display:"flex", justifyContent:"space-between" }}>
          <span style={{ fontFamily:font, fontSize:9, color:"rgba(255,255,255,0.28)", letterSpacing:2.5, textTransform:"uppercase" }}>B-Roll Footage</span>
          <span style={{ fontFamily:font, fontSize:9, color:`rgba(255,81,0,0.45)`, letterSpacing:1 }}>4K · 60fps</span>
        </div>
      </div>
    );
  };

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 1  ·  0–180f  ·  0–3s  ·  Hook negro
// ─────────────────────────────────────────────────────────────────────────────
const Scene1: React.FC<{ frame: number }> = ({ frame: f }) => {
  const p1     = prog(f, 3);
  const p2     = prog(f, 28);
  const rentOp = f >= 50 ? Math.min(1, (f - 49) / 4) : 0;
  const rf     = f - 50;
  const rentSc = f >= 50
    ? interpolate(rf, [0, 4, 10, 16, 20], [1.38, 0.88, 1.07, 0.97, 1.0], { extrapolateLeft:"clamp", extrapolateRight:"clamp" })
    : 1.38;
  const aberr  = f >= 50 && rf < 12
    ? interpolate(rf, [0, 12], [10, 0], { extrapolateLeft:"clamp", extrapolateRight:"clamp" }) : 0;
  const pStat  = prog(f, 98);

  return (
    <AbsoluteFill style={{ background:"radial-gradient(ellipse 120% 90% at 50% 20%,#1c0800 0%,#0F0F0F 58%)" }}>
      <Grain frame={f} />
      <div style={{ position:"absolute", top:0, left:0, right:0, height:3, background:C.orange }} />
      <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", justifyContent:"center", padding:"0 72px" }}>
        {/* Eyebrow */}
        <div style={{ display:"flex", alignItems:"center", gap:12, opacity:p1, transform:slideY(p1,18), marginBottom:18 }}>
          <div style={{ width:36, height:2, background:C.orange }} />
          <span style={{ fontFamily:font, fontWeight:800, fontSize:13, color:C.orange, letterSpacing:4, textTransform:"uppercase" }}>Restaurantero, atención</span>
        </div>
        {/* Headlines */}
        <div style={{ opacity:p1, transform:slideY(p1,38), marginBottom:8 }}>
          <span style={{ fontFamily:font, fontWeight:900, fontSize:80, color:C.white, letterSpacing:-3, lineHeight:1.05, display:"block" }}>TU RESTAURANTE</span>
          <span style={{ fontFamily:font, fontWeight:900, fontSize:80, color:"rgba(255,255,255,0.5)", letterSpacing:-3, lineHeight:1.05, display:"block" }}>ESTÁ EN APPS...</span>
        </div>
        {/* pero NO es */}
        <div style={{ opacity:p2, transform:slideY(p2,30), marginBottom:4 }}>
          <span style={{ fontFamily:font, fontWeight:800, fontSize:56, color:"rgba(255,255,255,0.38)", letterSpacing:-2 }}>PERO NO ES</span>
        </div>
        {/* RENTABLE */}
        <div style={{ position:"relative" }}>
          {aberr > 0 && (
            <>
              <div style={{ position:"absolute", transform:`translateX(${aberr}px)`, opacity:0.5, lineHeight:1 }}>
                <span style={{ fontFamily:font, fontWeight:900, fontSize:134, color:"#FF0000", letterSpacing:-5 }}>RENTABLE.</span>
              </div>
              <div style={{ position:"absolute", transform:`translateX(${-aberr}px)`, opacity:0.42, lineHeight:1 }}>
                <span style={{ fontFamily:font, fontWeight:900, fontSize:134, color:"#00FFFF", letterSpacing:-5 }}>RENTABLE.</span>
              </div>
            </>
          )}
          <div style={{ opacity:rentOp, transform:`scale(${rentSc})`, transformOrigin:"left center", textShadow:`0 0 70px ${C.orangeGlow}` }}>
            <span style={{ fontFamily:font, fontWeight:900, fontSize:134, color:C.orange, letterSpacing:-5, lineHeight:1, display:"block" }}>RENTABLE.</span>
          </div>
        </div>
        {/* Stat */}
        <div style={{ opacity:pStat, transform:slideY(pStat,18), marginTop:24, borderLeft:`3px solid ${C.orange}`, paddingLeft:18 }}>
          <span style={{ fontFamily:font, fontWeight:400, fontSize:22, color:C.gray, lineHeight:1.55 }}>
            El <span style={{ color:C.white, fontWeight:900 }}>73%</span> de restaurantes en apps<br />no logra ser rentable.
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 2  ·  180–420f  ·  3–7s  ·  El problema real (dark)
// ─────────────────────────────────────────────────────────────────────────────
const PAIN = [
  { text:"VENDES SIN CRECER", at:55 },
  { text:"SIN ESTRUCTURA",    at:90 },
  { text:"SIN CONTROL",       at:125 },
];

const Scene2: React.FC<{ frame: number }> = ({ frame }) => {
  const f    = frame - 180;
  const pH   = prog(f, 0);  // main title
  const pStat = prog(f, 162);

  return (
    <AbsoluteFill style={{ background:"radial-gradient(ellipse 100% 70% at 50% 0%,#1a0700 0%,#0F0F0F 55%)" }}>
      <Grain frame={frame} />

      {/* ── Fixed top: BIG section title ── */}
      <div style={{ position:"absolute", top:80, left:72, right:72 }}>
        <div style={{ opacity:pH, transform:slideY(pH, 30) }}>
          <span style={{ fontFamily:font, fontWeight:900, fontSize:72, color:C.white, letterSpacing:-3, lineHeight:1 }}>
            EL PROBLEMA
          </span>
          <span style={{ fontFamily:font, fontWeight:900, fontSize:72, color:C.orange, letterSpacing:-3, lineHeight:1 }}>
            {" "}REAL
          </span>
        </div>
      </div>

      {/* ── Content area below title ── */}
      <div style={{ position:"absolute", top:200, bottom:80, left:0, right:0, display:"flex", flexDirection:"column", justifyContent:"space-around", padding:"0 0" }}>

        {/* B-Roll */}
        <div style={{ padding:"0 72px" }}>
          <BRoll label="B-Roll · Comida en primer plano" frame={f} at={8} h={270} />
        </div>

        {/* Pain stripes — full width */}
        <div style={{ display:"flex", flexDirection:"column", gap:0 }}>
          {PAIN.map(({ text, at }) => {
            const p = prog(f, at);
            return (
              <div key={text} style={{
                opacity:p, transform:slideY(p, 40),
                display:"flex", alignItems:"center",
                background:C.orangeDim, borderLeft:`4px solid ${C.orange}`,
                padding:"20px 72px",
              }}>
                <span style={{ fontFamily:font, fontWeight:900, fontSize:68, color:C.white, letterSpacing:-2.5, lineHeight:1.05 }}>{text}</span>
              </div>
            );
          })}
        </div>

        {/* Stat chip */}
        <div style={{ padding:"0 72px", opacity:pStat, transform:slideY(pStat,16) }}>
          <div style={{ display:"inline-flex", alignItems:"center", gap:14, background:"rgba(255,81,0,0.08)", border:`1px solid ${C.border}`, borderRadius:4, padding:"12px 22px" }}>
            <span style={{ fontFamily:font, fontWeight:900, fontSize:30, color:C.orange }}>73%</span>
            <span style={{ fontFamily:font, fontWeight:400, fontSize:17, color:C.grayMid }}>de restaurantes en apps no es rentable</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 3  ·  420–660f  ·  7–11s  ·  Tu aliado estratégico (dark)
// ─────────────────────────────────────────────────────────────────────────────
const SOLUTION = [
  { l:"D", label:"DIAGNÓSTICO",  sub:"Análisis operativo en 48h",          at:50 },
  { l:"E", label:"ESTRATEGIA",   sub:"Decisiones basadas en datos reales",  at:84 },
  { l:"R", label:"RESULTADOS",   sub:"Medibles · Rentables · Garantizados", at:118 },
];

const Scene3: React.FC<{ frame: number }> = ({ frame }) => {
  const f     = frame - 420;
  const pH    = prog(f, 0);
  const pTxt1 = prog(f, 152);
  const pTxt2 = prog(f, 168);
  const dsc   = f >= 168
    ? interpolate(f - 168, [0, 5, 10, 15], [1.32, 0.9, 1.05, 1.0], { extrapolateLeft:"clamp", extrapolateRight:"clamp" })
    : 1.0;

  return (
    <AbsoluteFill style={{ background:"radial-gradient(ellipse 100% 60% at 50% 100%,#1a0700 0%,#0F0F0F 60%)" }}>
      <Grain frame={frame} />

      {/* ── Fixed top: BIG brand title ── */}
      <div style={{ position:"absolute", top:80, left:72, right:72 }}>
        <div style={{ opacity:pH, transform:slideY(pH, 30) }}>
          <span style={{ fontFamily:font, fontWeight:800, fontSize:58, color:C.white, letterSpacing:-2, lineHeight:1.05, display:"block" }}>
            TU ALIADO
          </span>
          <span style={{ fontFamily:font, fontWeight:900, fontSize:90, color:C.orange, letterSpacing:-3.5, lineHeight:0.95, display:"block", textShadow:`0 0 50px ${C.orangeGlow}` }}>
            ZUBA
          </span>
        </div>
      </div>

      {/* ── Content area below title ── */}
      <div style={{ position:"absolute", top:250, bottom:80, left:0, right:0, display:"flex", flexDirection:"column", justifyContent:"space-around", padding:"0 0" }}>

        {/* B-Roll */}
        <div style={{ padding:"0 72px" }}>
          <BRoll label="B-Roll · Tablet / Operaciones" frame={f} at={8} h={240} />
        </div>

        {/* Solution strips */}
        <div style={{ display:"flex", flexDirection:"column", gap:6, padding:"0 72px" }}>
          {SOLUTION.map(({ l, label, sub, at }) => {
            const p = prog(f, at);
            return (
              <div key={label} style={{
                opacity:p, transform:`translateX(${interpolate(p,[0,1],[-44,0])}px)`,
                display:"flex", alignItems:"center",
                background:C.orangeDim, borderLeft:`3px solid ${C.orange}`,
                padding:"14px 20px", borderRadius:0,
              }}>
                <div style={{ width:36, height:36, background:C.orange, borderRadius:0, display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0, marginRight:16 }}>
                  <span style={{ fontFamily:font, fontWeight:900, fontSize:18, color:C.white }}>{l}</span>
                </div>
                <div style={{ flex:1 }}>
                  <div style={{ fontFamily:font, fontWeight:900, fontSize:24, color:C.white, letterSpacing:-0.5 }}>{label}</div>
                  <div style={{ fontFamily:font, fontWeight:400, fontSize:15, color:C.grayMid, marginTop:1 }}>{sub}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* "No es marketing. Es DECISIÓN." */}
        <div style={{ padding:"0 72px" }}>
          <div style={{ opacity:pTxt1, transform:slideY(pTxt1,20), marginBottom:2 }}>
            <span style={{ fontFamily:font, fontWeight:800, fontSize:50, color:"rgba(255,255,255,0.45)", letterSpacing:-2, lineHeight:1.1 }}>No es marketing.</span>
          </div>
          <div style={{ opacity:pTxt2, transform:slideY(pTxt2,20) }}>
            <span style={{ fontFamily:font, fontWeight:800, fontSize:50, color:"rgba(255,255,255,0.45)", letterSpacing:-2, lineHeight:1.1 }}>Es{" "}</span>
            <span style={{ fontFamily:font, fontWeight:900, fontSize:50, color:C.orange, letterSpacing:-2, lineHeight:1.1, display:"inline-block", transform:`scale(${dsc})`, transformOrigin:"left center", textShadow:`0 0 40px ${C.orangeGlow}` }}>DECISIÓN.</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// SCENE 4  ·  660–900f  ·  11–15s  ·  CTA
// ─────────────────────────────────────────────────────────────────────────────
const STATS = [
  { val:"+47%", lbl:"RENTABILIDAD", sub:"promedio" },
  { val:"48h",  lbl:"DIAGNÓSTICO",  sub:"inicial" },
  { val:"$0",   lbl:"SIN FEE",      sub:"si no creces" },
];

const Scene4: React.FC<{ frame: number }> = ({ frame }) => {
  const f        = frame - 660;
  const shinePos = ((f % 120) / 120) * 280 - 50;
  const shineOp  = f < 30 ? 0 : Math.min(1, (f - 30) / 20);
  const pLogo    = prog(f, 0);
  const pTag     = prog(f, 20);
  const pStats   = prog(f, 44);
  const pGuar    = prog(f, 70);
  const pBtn     = prog(f, 88);
  const r1       = (f % 55) / 55;
  const r2       = ((f + 28) % 55) / 55;
  const breath   = 1 + 0.022 * Math.sin((f / 60) * Math.PI * 2 * 1.2);

  return (
    <AbsoluteFill style={{ background:"radial-gradient(ellipse 80% 80% at 50% 50%,#1a0600 0%,#0F0F0F 65%)" }}>
      <Grain frame={frame} />
      <div style={{ position:"absolute", top:0, left:0, right:0, height:3, background:C.orange }} />
      <div style={{ position:"absolute", inset:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"0 72px" }}>

        {/* Logo */}
        <div style={{ opacity:pLogo, transform:`scale(${interpolate(pLogo,[0,0.7,1],[0.78,1.07,1.0])})`, marginBottom:8, display:"flex", flexDirection:"column", alignItems:"center", gap:12 }}>
          <div style={{ width:80, height:80, borderRadius:4, background:C.orange, display:"flex", alignItems:"center", justifyContent:"center", boxShadow:`0 8px 52px ${C.orangeGlow}` }}>
            <span style={{ fontFamily:font, fontWeight:900, fontSize:44, color:C.white }}>Z</span>
          </div>
          <div style={{ position:"relative", overflow:"hidden" }}>
            <span style={{ fontFamily:font, fontWeight:900, fontSize:78, color:C.white, letterSpacing:-2.5, display:"block" }}>ZUBA</span>
            <div style={{ position:"absolute", top:0, bottom:0, left:shinePos-40, width:80, background:"linear-gradient(105deg,transparent 0%,rgba(255,255,255,0.4) 50%,transparent 100%)", opacity:shineOp, pointerEvents:"none" }} />
          </div>
        </div>

        <div style={{ opacity:pTag, marginBottom:28 }}>
          <span style={{ fontFamily:font, fontWeight:700, fontSize:17, color:C.gray, letterSpacing:4, textTransform:"uppercase" }}>
            Consultoría de Operación Gastronómica
          </span>
        </div>

        {/* Stats */}
        <div style={{ opacity:pStats, transform:slideY(pStats,26), display:"flex", gap:8, width:"100%", marginBottom:24 }}>
          {STATS.map(({ val, lbl, sub }) => (
            <div key={lbl} style={{ flex:1, background:C.orangeDim, border:`1px solid ${C.border}`, borderRadius:4, borderTop:`2px solid ${C.orange}`, padding:"18px 10px", textAlign:"center" }}>
              <div style={{ fontFamily:font, fontWeight:900, fontSize:46, color:C.orange, lineHeight:1 }}>{val}</div>
              <div style={{ fontFamily:font, fontWeight:800, fontSize:13, color:C.white, marginTop:6, letterSpacing:0.5 }}>{lbl}</div>
              <div style={{ fontFamily:font, fontWeight:400, fontSize:12, color:C.gray, marginTop:3 }}>{sub}</div>
            </div>
          ))}
        </div>

        <div style={{ opacity:pGuar, marginBottom:26 }}>
          <span style={{ fontFamily:font, fontWeight:400, fontSize:22, color:C.gray }}>
            Si no creces, <span style={{ color:C.white, fontWeight:900 }}>NO COBRAMOS.</span>
          </span>
        </div>

        {/* CTA + pulse rings */}
        <div style={{ position:"relative", opacity:pBtn }}>
          {[r1, r2].map((rp, i) => (
            <div key={i} style={{ position:"absolute", inset:-10, border:`2px solid ${C.orange}`, borderRadius:4, transform:`scale(${1 + rp * 0.42})`, opacity:(1 - rp) * 0.38, pointerEvents:"none" }} />
          ))}
          <div style={{ background:C.orange, borderRadius:4, padding:"26px 58px", display:"inline-flex", alignItems:"center", gap:18, boxShadow:`0 8px 52px ${C.orangeGlow}`, transform:`scale(${breath * interpolate(pBtn,[0,1],[0.88,1.0])})` }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            <span style={{ fontFamily:font, fontWeight:900, fontSize:36, color:C.white, letterSpacing:-0.5 }}>AUDITORÍA GRATIS →</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Main ──────────────────────────────────────────────────────────────────────
export const ZubaAd: React.FC<Props> = (_props) => {
  const frame = useCurrentFrame();
  const scene = frame < 180 ? 1 : frame < 420 ? 2 : frame < 660 ? 3 : 4;
  const musicVol = interpolate(frame, [0, 60, 840, 900], [0, 0.09, 0.09, 0], { extrapolateLeft:"clamp", extrapolateRight:"clamp" });

  return (
    <AbsoluteFill style={{ background:C.bg }}>
      <Audio src={staticFile("bg-music.mp3")} volume={musicVol} loop />
      <Sequence from={0}   durationInFrames={200}><Audio src={staticFile("vo-s1.mp3")} volume={0.92} /></Sequence>
      <Sequence from={180} durationInFrames={260}><Audio src={staticFile("vo-s2.mp3")} volume={0.92} /></Sequence>
      <Sequence from={420} durationInFrames={260}><Audio src={staticFile("vo-s3.mp3")} volume={0.92} /></Sequence>
      <Sequence from={660} durationInFrames={260}><Audio src={staticFile("vo-s4.mp3")} volume={0.92} /></Sequence>
      <Sequence from={50}  durationInFrames={45}> <Audio src={staticFile("sfx-thud.mp3")} volume={0.82} /></Sequence>
      {scene === 1 && <Scene1 frame={frame} />}
      {scene === 2 && <Scene2 frame={frame} />}
      {scene === 3 && <Scene3 frame={frame} />}
      {scene === 4 && <Scene4 frame={frame} />}
    </AbsoluteFill>
  );
};
