import { FfmpegAudioProvider } from "./ffmpeg-audio-provider.js";
import { OptionalPitchProvider } from "./pitch-provider.js";

export function createProviders() {
  return {
    audio: new FfmpegAudioProvider(),
    pitch: new OptionalPitchProvider()
  };
}
