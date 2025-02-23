# M3U8 视频下载转换器

一个基于Python的GUI工具，支持从多个M3U8链接下载加密视频流，自动合并TS片段并解密为MP4文件。

![1740238109986](C:\Users\liking\AppData\Roaming\Typora\typora-user-images\1740238109986.png) 
（可将截图上传至仓库后替换此链接）

## 功能特性

- 🖥️ 图形化界面操作，简单易用
- 🔗 支持同时输入多个M3U8链接
- 🚀 可自定义下载线程数（1-50）
- 🔒 自动处理AES-128加密流
- 📊 实时显示下载进度
- 🗑️ 自动清理临时文件

## 环境要求

- Python 3.7+
- Windows/macOS/Linux（需GUI支持）

## 快速开始

### 安装依赖

```bash
# 安装核心依赖库
pip install requests m3u8 pycryptodome

# Linux系统可能需要额外安装tkinter
sudo apt-get install python3-tk  # Ubuntu/Debian
sudo dnf install python3-tkinter # Fedora
```
