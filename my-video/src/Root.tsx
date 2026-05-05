import "./index.css";
import { Composition } from "remotion";
import { ZubaAd, ZubaAdSchema } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ZubaAd"
      component={ZubaAd}
      durationInFrames={600}
      fps={30}
      width={1080}
      height={1920}
      schema={ZubaAdSchema}
      defaultProps={{ hook: "pain" }}
    />
  );
};
