# 句间（桌面学习版）

Windows 桌面日语精听与日英写作学习工具。可以打开本地音视频、整理媒体资料、转写音频，并使用本地 Ollama 或 OpenAI 兼容云端接口进行翻译、解析和作文批改。

## 从源码运行

需要 Windows 10/11、Python 3.11（64 位）和 Git。首次启动 PowerShell，进入克隆目录并运行：

```powershell
git clone https://github.com/Normanchine/mainichi-nihongo.git
cd mainichi-nihongo
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\run.cmd
```

`setup.ps1` 会创建 `.venv` 并安装 `requirements.txt` 中的依赖。之后可直接运行 `run.cmd`。首次使用 Whisper 转写时，如果本机还没有 `small` 模型，程序会下载模型文件（约 460 MB）；下载和转写都需要网络或可用的本地模型文件。CPU 可以运行，NVIDIA GPU 可使用兼容的 CUDA 版 PyTorch 加速。

## 配置云端 API

打开应用的“设置”，选择云端后端，填写服务商提供的 OpenAI 兼容接口地址和模型名称，保存后输入 API Key。API Key 保存在当前 Windows 用户的凭据管理器中，不写入源码目录。翻译、解析和写作批改可以分别选择本地或云端后端。

也可选用本地 Ollama：安装并运行 Ollama，下载应用设置页显示的模型，再将相应任务切换到本地。使用云端接口不需要安装 Ollama。

## 数据与隐私

媒体文件保留在原位置。作文、项目、设置、下载内容和 API 凭据均保存在本机，并已排除在 Git 版本管理之外。克隆仓库不会带入开发者的个人项目、音视频、API Key、模型或打包程序。

## 验证

项目附有源码验证脚本。在已安装依赖的环境中可运行云端请求格式和写作存储检查（两者都使用临时数据和模拟服务，不需要真实 API Key）：

```powershell
.\.venv\Scripts\python.exe verify_cloud.py
.\.venv\Scripts\python.exe verify_feedback.py
```

这些脚本用于源码功能检查；运行它们不代表云端 API 凭据、外部下载或打包版已在你的电脑上验证。
