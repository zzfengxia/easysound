import { runFfprobe } from "./process-utils.js";

export async function probeAudio(filePath) {
  const { stdout } = await runFfprobe([
    "-v",
    "error",
    "-print_format",
    "json",
    "-show_streams",
    "-show_format",
    filePath
  ]);

  const parsed = JSON.parse(stdout);
  const audioStream = parsed.streams?.find((stream) => stream.codec_type === "audio");

  return {
    durationSeconds: Number(parsed.format?.duration || 0),
    sampleRate: Number(audioStream?.sample_rate || 0),
    channels: Number(audioStream?.channels || 0),
    codec: audioStream?.codec_name || "unknown",
    formatName: parsed.format?.format_name || "unknown",
    bitRate: Number(parsed.format?.bit_rate || 0)
  };
}
