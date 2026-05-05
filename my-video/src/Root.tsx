import "./index.css";
import { Composition } from "remotion";
import { ZubaAd, ZubaAdSchema } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ZubaAd"
      component={ZubaAd}
      durationInFrames={900}
      fps={60}
      width={1080}
      height={1920}
      schema={ZubaAdSchema}
      defaultProps={{ hook: "pain" }}
    />
  );
};
