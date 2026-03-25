import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const FFMPEG_PATH = process.env.FFMPEG_PATH || "D:\\soft202502\\ffmpeg-2025-04-23\\bin\\ffmpeg.exe";
export const FFPROBE_PATH = process.env.FFPROBE_PATH || "D:\\soft202502\\ffmpeg-2025-04-23\\bin\\ffprobe.exe";

export async function runCommand(file, args, options = {}) {
  const { stdout, stderr } = await execFileAsync(file, args, {
    windowsHide: true,
    maxBuffer: 16 * 1024 * 1024,
    ...options
  });

  return { stdout, stderr };
}

export async function runFfmpeg(args, options = {}) {
  return runCommand(FFMPEG_PATH, ["-y", ...args], options);
}

export async function runFfprobe(args, options = {}) {
  return runCommand(FFPROBE_PATH, args, options);
}
