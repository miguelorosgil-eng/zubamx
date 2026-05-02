import "./index.css";
import { Composition } from "remotion";
import { ZubaTikTok } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ZubaTikTok"
      component={ZubaTikTok}
      durationInFrames={270}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
