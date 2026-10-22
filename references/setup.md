# 首次使用与环境配置

仅在首次使用、换机器或依赖缺失时读取。本文件是 Skill 第2阶段的必读说明。Python脚本不会自动安装任何组件。

## 先明确目录与用户选择

先按 output-format.md 取得尚未明确的输出选择。示例中的 `<...>` 都要替换；不可把尖括号占位符直接交给 shell。

向新用户明确提醒：**“下面出现的 Skill、Python、模型、音频和输出地址，请替换成你自己的实际地址；不是复制作者电脑的目录。”** 在终端执行前展示已经解析的路径。路径包含空格时保留引号。Windows可使用绝对路径或正斜杠路径，不能照抄POSIX环境变量语法。

- `SKILL_DIR`：下载/安装后的本技能目录。
- `PYTHON`：实际运行转写的虚拟环境中的 Python。
- `MODEL_DIR`：本地 CTranslate2 模型文件夹，应有 `model.bin`、`config.json`、`tokenizer.json`。Whisper `.pt` 不能当作此文件夹。
- `AUDIO`：原始音频文件；全程保持不变。
- `WORK_DIR`：用户已同意的临时任务目录，保存音频片段、检查点、原始识别与校订过程。
- 最终目录：只有用户选择本地交付时才需要，独立于临时目录。

## 依赖范围

| 组件 | 用于什么 | 本包是否自带 | 费用和许可说明 |
|---|---|---|---|
| Python >=3.9、venv、pip | 运行本包脚本 | 否 | 本地软件；确认所用发行版条件 |
| faster-whisper 1.2.1 及其依赖 | CPU/int8 转写 | 仅提供 requirements.txt | 核心引擎 MIT；无按次API费用，依赖/模型单独核对 |
| CTranslate2 Whisper 模型 | 本地推理 | 否 | 需下载或复用缓存；核对实际模型卡，不能将某个模型许可泛化到全部模型 |
| ffmpeg **和 ffprobe** | 本包探测、归一化、切块 | 否 | 开源构建许可取决于组件；本包不分发二进制 |
| python-docx | 仅在选择 Word `.docx` 时 | 否，可选 | 安装前核对当前版本及许可，不是转写必需项 |
| 说话人分离引擎 | 可选自动分离 | 否 | 单独环境、模型条件/令牌；不能把ASR当分离引擎 |
| 云文档连接器 | 仅用户选择云端时 | 否，可选 | 需相应账号、登录和权限，可能受套餐限制 |

faster-whisper本身可通过PyAV解码而不要求系统FFmpeg；**本包分块路线额外使用 ffmpeg/ffprobe**。两者不要混淆。CPU路线不要求CUDA；GPU是另行配置的可选路线，不自动安装驱动或宣称支持已测试。

核心引擎固定1.2.1，传递依赖因平台而异；不是跨系统全量锁文件。安装成功后记录实际解析版本。先用现有环境，兼容性问题先短样本验证，不随意升级全局环境。

## 只读检查

以下命令先替换路径，再用实际目标 Python 执行；不会写文件或触发模型下载：

```text
"<PYTHON>" "<SKILL_DIR>/scripts/preflight.py" --audio "<AUDIO>" --model-dir "<MODEL_DIR>" --work-dir "<WORK_DIR>" --ffmpeg "<FFMPEG>" --ffprobe "<FFPROBE>"
```

工具已经在 PATH 时可省略 `--ffmpeg`/`--ffprobe`。返回码2表示仍有缺项，查看JSON中的具体项目；不要将它当作“转写已经失败”或开始反复安装。检查只证明文件/元数据可见，模型能否加载仍要短样本验证。

## 需要安装时

先告诉用户：安装什么、用途、为何现有环境不能满足、所需下载/磁盘范围、是否免费和商业许可条件、用于测试还是最终交付。取得该范围授权后再执行；账户条款、费用和隐私不能用默认同意代替。

安装示例（均在用户确认目录后执行）：

```text
python3 -m venv "<VENV_DIR>"
"<VENV_PYTHON>" -m pip install -r "<SKILL_DIR>/requirements.txt"
```

Windows创建环境可用已存在的 `py -3 -m venv "<VENV_DIR>"`；Python路径通常是 `<VENV_DIR>/Scripts/python.exe`，POSIX通常是 `<VENV_DIR>/bin/python`。先检测实际Python，不保证系统一定有 `py` 或 `python3`。无需强制激活环境，直接调用该Python即可。

FFmpeg/ffprobe先检查已有安装，否则在用户批准后按所选系统和官方安装来源配置；不要静默安装 Homebrew、winget 或其它包管理器。确保两个可执行文件可用，再重跑 preflight。

模型示例：`Systran/faster-whisper-small`（中文/混合语言），模型大小影响时间、磁盘和质量，先说明取舍。若已有合适模型无需再下载。取得模型下载授权后，可以使用已安装的 huggingface_hub：

```text
"<VENV_PYTHON>" -c "from huggingface_hub import snapshot_download; print(snapshot_download(repo_id='Systran/faster-whisper-small', local_dir=r'<MODEL_DIR>'))"
```

将模型目录也替换成用户的路径；含引号等特殊字符时改用安全的参数脚本，不拼接不可信字符串。模型下载不上传录音。本包ASR运行阶段强制使用本地模型，缺模型会报错，不自行联网补齐。

## 作者电脑的可选现有资源（仅此电脑）

只在当前机器存在这些路径时复用：

- `/Users/admin/Documents/Codex/.venv-whisper/bin/python`
- `/Users/admin/Documents/Codex/tools/ffmpeg/ffmpeg`；音频探测器需独立检查，本机可用 `/usr/local/bin/ffprobe`（不能假定与ffmpeg同目录）。工作区同目录可能存在只处理图片的兼容脚本，不能用于音频
- `/Users/admin/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/<实际修订>/`
- OpenAI Whisper的 `.whisper-models/base.pt` 仅供它自身的引擎，不能用于本包 CTranslate2 脚本。

**给其他用户必须提示更换为自己的地址。** 此处是可选本机事实，不是自动创建这些目录的指令，也不要求下载者具有 `.venv-whisper` 或相同用户名。

## 安装后验证与故障边界

1. 重跑 preflight，确认所选解释器和模型格式。
2. 用一段代表性短音频测试，记录实际版本与设备；成功后再跑长音频。
3. 缺模块：先核对是否调用错Python；不要连续在多个环境安装。
4. Intel macOS若出现重复OpenMP运行库错误，先确认安装来源和冲突；仅针对该问题可在单次进程设置 `KMP_DUPLICATE_LIB_OK=TRUE` 试验，不能全局写入系统配置，也不保证解决。
5. 模型或系统兼容仍失败：保留错误和已完成检查点，说明阻塞原因，协商另一条已授权路线；不私自上传音频或改成收费服务。

## 官方来源（配置前复核可能变化的要求）

- [faster-whisper 要求、CPU及API](https://github.com/SYSTRAN/faster-whisper)
- [small 模型卡和许可](https://huggingface.co/Systran/faster-whisper-small)
- [FFmpeg安装来源](https://ffmpeg.org/download.html)及[许可说明](https://ffmpeg.org/legal.html)
- [python-docx 安装](https://python-docx.readthedocs.io/en/latest/user/install.html)

## 自动声音分离的独立环境

用户选择自动分离时使用pyannote.audio 4.x兼容环境（Python要求以所选版本官方元数据为准，不能沿用ASR的Python3.9而假定兼容）。安装前检查目标平台PyTorch/torchcodec及FFmpeg兼容性，展示拟安装版本与下载/磁盘规模，取得批准。`requirements-diarization.txt`是可选范围声明，不是已实测的跨平台锁文件。安装在独立环境；不升级原ASR环境。

取得批准后，用现有且兼容的Python创建用户指定虚拟环境，并用其Python执行 `-m pip install -r "<SKILL_DIR>/requirements-diarization.txt"`。pyannote.audio为MIT，community-1模型为CC-BY-4.0，免费、允许商业使用但须履行各自署名/许可义务及访问条件；依赖许可证也须检查。软件/模型用于最终本地分离及配置测试，无按次API费用，不包含托管服务。下载体积和平台兼容实际解析后记录，不承诺固定大小。

用户本人登录Hugging Face，接受community-1访问条件（包括向提供方共享账户信息），配置最小必要的读取权限令牌。不得让用户将令牌贴到聊天。按官方离线说明准备完整模型到 `<COMMUNITY1_DIR>`；也可在已批准且已安装huggingface_hub的环境中使用 `snapshot_download` 下载该完整仓库，令牌由安全凭证读取，不写入命令或日志。完成后运行脚本的本地路径模式，不使用模型ID触发下载。模型访问授权与本地录音上传是两回事，本路线不上传录音。

[community-1官方安装、许可与离线路线](https://huggingface.co/pyannote/speaker-diarization-community-1)。若模型权重未安装或用户未接受访问条件，明确自动分离尚未启用；不将配置说明或模拟测试报为真实音频分离成功。
