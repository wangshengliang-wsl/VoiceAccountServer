# VoiceAccount 录音功能配置指南

## 后端配置

### 1. 安装依赖

```bash
cd /Users/wangshengliang/Desktop/i/VoiceAccount/VoiceAccountServer
source venv/bin/activate
pip install Flask python-dotenv supabase
```

### 2. 配置环境变量

编辑 `.env` 文件，填入你的 Supabase 配置：

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
```

### 3. 创建 Supabase Storage Bucket

1. 登录 Supabase 控制台
2. 进入 Storage 页面
3. 创建一个新的 bucket，名称为 `user-audio`
4. 设置 bucket 为 public（或根据需求设置权限）

### 4. 启动服务器

```bash
python app.py
```

服务器将在 `http://localhost:5000` 启动

### 5. 测试接口

```bash
# 测试服务器
curl http://localhost:5000/

# 测试 Supabase 连接
curl http://localhost:5000/supabase-test
```

## iOS 配置

### 1. 添加麦克风权限

在 Xcode 中：
1. 选择项目的 Target
2. 进入 "Info" 标签页
3. 在 "Custom iOS Target Properties" 中添加新行
4. 添加键：`Privacy - Microphone Usage Description`
5. 添加值：`需要使用麦克风进行语音记账`

或者直接编辑 `Info.plist` 文件，添加：

```xml
<key>NSMicrophoneUsageDescription</key>
<string>需要使用麦克风进行语音记账</string>
```

### 2. 配置服务器地址

编辑 `NetworkManager.swift` 中的 `baseURL`：

```swift
// 本地开发
private let baseURL = "http://localhost:5000"

// 使用实际 IP（真机测试时）
// private let baseURL = "http://192.168.x.x:5000"

// 生产环境
// private let baseURL = "https://your-production-server.com"
```

### 3. 运行应用

1. 在 Xcode 中打开项目
2. 选择目标设备（模拟器或真机）
3. 运行应用（Cmd + R）

## 使用流程

1. 点击主页的"语音输入"按钮
2. 首次使用会请求麦克风权限
3. 点击麦克风图标开始录音
4. 再次点击停止录音
5. 录音文件会自动保存为 .m4a 格式并上传到 Supabase
6. 上传成功后会显示成功提示

## API 接口说明

### POST /api/upload-audio

上传音频文件到 Supabase Storage

**请求参数**:
- `file`: 音频文件 (multipart/form-data)
- `user_id`: 用户ID (可选，默认为 "anonymous")

**支持的音频格式**:
- .m4a
- .mp3
- .wav
- .aac

**响应示例**:

```json
{
    "status": "success",
    "message": "文件上传成功",
    "data": {
        "url": "https://your-project.supabase.co/storage/v1/object/public/user-audio/...",
        "filename": "anonymous_20241110_123456_a1b2c3d4.m4a",
        "path": "anonymous/anonymous_20241110_123456_a1b2c3d4.m4a",
        "size": 123456,
        "content_type": "audio/m4a"
    }
}
```

## 文件结构

```
VoiceAccountServer/
├── app.py                    # Flask 应用主文件
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量（需要配置）
├── .gitignore               # Git 忽略文件
└── venv/                     # Python 虚拟环境

VoiceAccountClient/VoiceAccount/
├── Helpers/
│   ├── AudioRecorder.swift   # 录音管理器
│   └── NetworkManager.swift  # 网络管理器
└── Views/
    ├── HomeView.swift        # 主页（已更新）
    └── VoiceInputView.swift  # 录音界面
```

## 故障排查

### 问题：无法连接到服务器

- 检查服务器是否正在运行
- 检查 NetworkManager 中的 baseURL 是否正确
- 真机测试时，确保手机和电脑在同一网络，使用电脑的 IP 地址

### 问题：Supabase 连接失败

- 检查 .env 文件中的配置是否正确
- 确保 SUPABASE_SERVICE_ROLE_KEY 是服务端密钥（不是 anon key）
- 检查 user-audio bucket 是否已创建

### 问题：没有麦克风权限

- 在 iOS 设置 > VoiceAccount > 允许麦克风访问
- 确保 Info.plist 中已添加 NSMicrophoneUsageDescription

### 问题：上传失败

- 检查文件大小（最大 50MB）
- 检查文件格式是否支持
- 查看服务器日志获取详细错误信息

## 下一步开发

1. **语音识别**: 集成 OpenAI Whisper API 或其他语音识别服务
2. **AI 解析**: 使用 GPT 解析语音内容，提取金额、分类等信息
3. **自动记账**: 根据解析结果自动创建记账记录
4. **历史记录**: 查看和管理已上传的录音文件

