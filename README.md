# EasySound

EasySound 现在采用 `Python + FastAPI` 作为后端，前端仍然使用仓库里的静态页面。用户上传一段录制好的歌曲音频后，可以选择 `干声模式` 或 `带伴奏模式`，并按步骤完成降噪、修音、润色和场景效果处理，最终导出处理后的成品音频。

## 当前后端状态

- 后端入口位于 `backend/app/main.py`。
- API 与前端保持兼容，并扩展了修音参数：
  - `GET /api/config`
  - `GET /api/tasks`
  - `GET /api/tasks/{id}`
  - `POST /api/tasks`
  - `GET /media/results/{file}`
- `POST /api/tasks` 额外支持：
  - `pitchMode`: `auto_scale` | `midi_reference` | `reference_vocal`
  - `pitchStyle`: `natural` | `autotune`
  - `pitchStrength`: 0-100
  - `referenceDurationRatioMin` / `referenceDurationRatioMax`: 仅参考干声模式生效
  - `midiFile`: 可选 MIDI 文件
  - `referenceVocalFile`: 可选参考干声文件
- FastAPI 生命周期里会初始化：
  - 任务持久化 `backend/app/services/task_store.py`
  - 单 worker 异步队列 `backend/app/services/job_queue.py`
  - 音频处理流水线 `backend/app/services/audio_pipeline.py`
  - Provider 工厂 `backend/app/providers/provider_factory.py`

## 自动修音当前实现

现在已经不是单纯占位了，修音 provider 已经升级为一版可工作的原型：[`backend/app/providers/pitch_provider.py`](backend/app/providers/pitch_provider.py)。

当前逻辑：
- 默认模式 `auto_scale`
  - 跟踪音高，优先尝试 `CREPE`
  - 若 `CREPE` 不可用，则回退到 `librosa.pyin`
  - 自动估计音阶
  - 对检测到的音符段做目标音高吸附
- `midi_reference` 模式
  - 读取上传的 MIDI
  - 用 note anchoring 把演唱时间映射到参考旋律
  - 再对每个音符段做目标音高修正
- `reference_vocal` 模式
  - 提取参考干声的音高轨和音符段
  - 对参考段做轻度平滑，弱化颤音和细碎抖动
  - 通过 note anchoring + 轻量 DTW 候选匹配待修与参考干声
  - 用参考干声主旋律中心为待修段生成目标音高
  - 支持配置参考干声与待修音频的时长比例阈值，超出区间会回退到自动修音，并在任务状态里显示红色提示
- 渲染层
  - 使用 ffmpeg 内置 `rubberband` 过滤器按片段做变调
  - `natural` 和 `autotune` 两种风格会映射到不同的吸附阈值和修正力度

### 修音风格说明

- `natural`
  - 修得更柔和，优先保留原唱的滑音、颤音和情绪表达
  - 只有明显跑调时才会更积极地拉回目标音
  - 更适合普通流行歌曲、翻唱润色、希望“听起来像没怎么修过”的场景
- `autotune`
  - 吸附更明显，音高会更快贴近目标音
  - 风格感更强，更容易听出修音效果
  - 更适合电子感、流行风格化处理，或者明确想要 Auto-Tune 味道的场景

### 修音强度说明

- `pitchStrength` 越低
  - 修音越轻
  - 会更保留原唱的起伏和细节
  - 更适合本身音准偏差不大、只想轻微润色的情况
- `pitchStrength` 越高
  - 修音越积极
  - 音高会更明显地被拉向目标音
  - 更适合跑调更明显、或者希望风格更突出的情况
- 实际使用建议
  - 想自然一点：从 `40-60` 开始
  - 想更稳更准：从 `60-80` 开始
  - 想明显风格化：搭配 `autotune` 再把强度继续往上调

这仍然是 **原型级实现**，不是专业 DAW 级修音：
- 目前是 `note-segment` 级修正，不是连续 target F0 曲线重建
- `midi_reference` 模式目前采用 note anchoring，没有做真正的 DTW
- `reference_vocal` 模式以“同一首歌、相近拍点结构”为默认假设
- `带伴奏` 模式仍然只是原型支持，不作为首版质量验收目标

## 目录结构

- `backend/app/main.py`: FastAPI 应用入口
- `backend/app/api/routes.py`: HTTP API
- `backend/app/services`: 队列、任务存储、处理流水线、上传解析
- `backend/app/providers`: 音频处理 provider 与自动修音 provider
- `public`: 前端静态页面
- `backend/tests`: Python 测试
- `storage`: 上传、结果和临时文件
- `data/tasks`: 任务元数据

## 运行方式

当前机器上我没有发现可直接调用的 Python 解释器，所以这次我完成了迁移和修音模块实现，但 **没有办法在本机直接启动 Python 服务做实跑验证**。

在有 Python 3.11+ 的环境里，运行方式是：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 3000
```

在 conda 中运行：
```powershell
conda activate easysound
cd {项目文件夹}/backend
uvicorn app.main:app --reload --port 3000
```

然后打开 [http://localhost:3000](http://localhost:3000)

## 测试

```powershell
pytest
```

## 已知限制

- `CREPE` 是可选依赖；如果环境里不可用，会自动退回 `librosa.pyin`。
- 当前修音渲染是按片段调用 `rubberband`，边界处仍可能有轻微拼接痕迹。
- `midi_reference` 模式目前是 note anchoring，不是完整 DTW。
- `reference_vocal` 模式默认要求参考干声和待修音频是同一首歌、相近拍点结构。
- 当前队列是单 worker 的进程内队列，不是 Celery/Redis。
- 结果与任务元数据仍保存在本地文件系统。
