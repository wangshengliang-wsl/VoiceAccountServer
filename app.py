#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 服务端
用于语音记账应用的后端服务
"""

import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from openai import OpenAI

# 获取项目根目录(app.py 所在的目录)
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'

# 加载环境变量(明确指定 .env 文件路径)
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
else:
    # 如果当前目录没有,尝试父目录
    parent_env = BASE_DIR.parent / '.env'
    if parent_env.exists():
        load_dotenv(dotenv_path=parent_env)
    else:
        # 最后尝试默认位置
        load_dotenv()

# 初始化 Flask
app = Flask(__name__)

# 配置
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 最大上传 50MB
ALLOWED_EXTENSIONS = {'m4a', 'mp3', 'wav', 'aac'}

# 初始化 Supabase 客户端
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    error_msg = "请在 .env 文件中配置 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY\n"
    error_msg += f"\n.env 文件应该位于: {ENV_FILE}\n"
    error_msg += f"\n.env 文件格式示例:\n"
    error_msg += "SUPABASE_URL=https://your-project.supabase.co\n"
    error_msg += "SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here\n"
    error_msg += f"\n当前工作目录: {os.getcwd()}\n"
    error_msg += f"脚本所在目录: {BASE_DIR}\n"
    if ENV_FILE.exists():
        error_msg += f"\n⚠️  找到 .env 文件,但环境变量未加载,请检查文件格式"
    raise ValueError(error_msg)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# 初始化阿里云 DashScope 客户端
dashscope_client = None
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')

if DASHSCOPE_API_KEY:
    dashscope_client = OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    print("✅ 阿里云 DashScope 客户端初始化成功")
else:
    print("⚠️  未配置 DASHSCOPE_API_KEY，语音解析功能将不可用")


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def hello():
    """
    根路由 - 返回欢迎信息
    """
    return jsonify({
        'message': 'VoiceAccount Server',
        'status': 'success',
        'version': '1.0.0'
    })


@app.route('/api/hello')
def api_hello():
    """
    API 路由 - 返回 hello 信息
    """
    return jsonify({
        'message': 'hello flask',
        'version': '1.0.0',
        'service': 'VoiceAccount API'
    })


@app.route('/health')
def health_check():
    """
    健康检查路由
    """
    return jsonify({
        'status': 'healthy',
        'service': 'flask'
    })


@app.route('/supabase-test')
def supabase_test():
    """
    Supabase 连接测试
    获取用户数量
    """
    try:
        # 使用 admin API 获取用户列表
        response = supabase.auth.admin.list_users()

        # 获取用户数量
        user_count = len(response) if response else 0

        return jsonify({
            'status': 'success',
            'message': 'Supabase 连接成功',
            'user_count': user_count
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'Supabase 连接失败',
            'error': str(e)
        }), 500


@app.route('/storage-test')
def storage_test():
    """
    Supabase Storage 测试
    测试 Storage bucket 是否可访问和上传
    """
    try:
        bucket_name = 'user-audio'

        # 测试 1: 检查 bucket 是否存在
        try:
            buckets = supabase.storage.list_buckets()
            bucket_names = [bucket.name for bucket in buckets] if buckets else []
            bucket_exists = bucket_name in bucket_names
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'无法列出 buckets: {str(e)}',
                'check': '请检查 Service Role Key 是否正确'
            }), 500

        if not bucket_exists:
            return jsonify({
                'status': 'error',
                'message': f'Bucket "{bucket_name}" 不存在',
                'solution': f'请在 Supabase Dashboard 中创建名为 "{bucket_name}" 的 Storage bucket'
            }), 404

        # 测试 2: 尝试上传一个小文件
        test_content = b'test audio file'
        test_path = 'test/test_upload.txt'
        upload_success = False
        upload_error = None

        try:
            upload_response = supabase.storage.from_(bucket_name).upload(
                path=test_path,
                file=test_content,
                file_options={
                    'content-type': 'text/plain',
                    'upsert': 'true'
                }
            )
            upload_success = True

            # 清理测试文件
            try:
                supabase.storage.from_(bucket_name).remove([test_path])
            except:
                pass  # 忽略删除错误

        except Exception as e:
            upload_error = str(e)
            error_code = 500
            if '403' in upload_error or 'Forbidden' in upload_error:
                error_code = 403

        # 测试 3: 尝试获取公开 URL
        url_test = False
        url_error = None
        try:
            test_url = supabase.storage.from_(bucket_name).get_public_url(test_path)
            url_test = True
        except Exception as e:
            url_error = str(e)

        return jsonify({
            'status': 'success' if upload_success else 'error',
            'message': 'Storage 测试完成',
            'bucket_exists': bucket_exists,
            'bucket_name': bucket_name,
            'upload_test': 'success' if upload_success else 'failed',
            'upload_error': upload_error,
            'url_test': 'success' if url_test else 'failed',
            'url_error': url_error,
            'solution': (
                '如果上传失败,请检查:\n'
                '1. Storage bucket 权限设置为公开 (Public)\n'
                '2. 或者设置 Storage Policies 允许服务角色访问\n'
                '3. 在 Supabase Dashboard > Storage > Policies 中配置'
            ) if not upload_success else None
        }), 200 if upload_success else 403

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'Storage 测试失败',
            'error': str(e)
        }), 500


@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    """
    接收录音文件并上传到 Supabase Storage

    请求参数:
        - file: 音频文件 (multipart/form-data)
        - user_id: 用户ID (可选)

    返回:
        - success: 上传成功,返回文件 URL
        - error: 上传失败,返回错误信息
    """
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': '没有找到文件'
            }), 400

        file = request.files['file']

        # 检查文件名是否为空
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': '文件名为空'
            }), 400

        # 检查文件类型
        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': f'不支持的文件类型,仅支持: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        # 获取用户 ID (可选)
        user_id = request.form.get('user_id', 'anonymous')

        # 生成唯一文件名
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{user_id}_{timestamp}_{unique_id}.{file_ext}"

        # 读取文件内容
        file_content = file.read()

        # 上传到 Supabase Storage
        # bucket 名称: user-audio
        storage_path = f"{user_id}/{filename}"

        # 上传文件
        try:
            upload_response = supabase.storage.from_('user-audio').upload(
                path=storage_path,
                file=file_content,
                file_options={
                    'content-type': f'audio/{file_ext}',
                    'cache-control': '3600',
                    'upsert': 'false'
                }
            )
        except Exception as upload_error:
            error_msg = str(upload_error)
            error_code = 500

            # 检查是否是权限错误 (403)
            if '403' in error_msg or 'Forbidden' in error_msg or 'permission' in error_msg.lower() or 'access denied' in error_msg.lower():
                error_code = 403
                error_msg = (
                    "权限不足 (403 Forbidden)\n\n"
                    "请检查 Supabase Storage 配置:\n"
                    "1. Supabase Storage bucket 'user-audio' 是否存在\n"
                    "2. Service Role Key 是否正确配置\n"
                    "3. Storage bucket 权限设置是否正确(建议设置为公开或允许服务角色访问)\n"
                    "4. Storage Policies 是否允许上传操作\n\n"
                    "详细配置指南请查看: SUPABASE_STORAGE_SETUP.md"
                )

            return jsonify({
                'status': 'error',
                'message': error_msg,
                'error_code': error_code
            }), error_code

        # 获取公开 URL
        try:
            public_url = supabase.storage.from_('user-audio').get_public_url(storage_path)
        except Exception as url_error:
            return jsonify({
                'status': 'error',
                'message': f'获取文件 URL 失败: {str(url_error)}'
            }), 500

        return jsonify({
            'status': 'success',
            'message': '文件上传成功',
            'data': {
                'url': public_url,
                'filename': filename,
                'path': storage_path,
                'size': len(file_content),
                'content_type': f'audio/{file_ext}'
            }
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': '文件上传失败',
            'error': str(e)
        }), 500


@app.route('/api/parse-voice', methods=['POST'])
def parse_voice():
    """
    使用 AI 解析语音内容，提取记账明细

    请求参数:
        - audio_url: 语音文件URL
        - categories: 用户自定义的分类列表

    返回:
        - 解析出的记账条目数组 (金额/标题/分类)
    """
    try:
        # 检查 DashScope 客户端是否已初始化
        if not dashscope_client:
            return jsonify({
                'status': 'error',
                'message': '语音解析服务未配置，请联系管理员'
            }), 503

        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({
                'status': 'error',
                'message': '请求数据为空'
            }), 400

        audio_url = data.get('audio_url')
        categories = data.get('categories', [])

        if not audio_url:
            return jsonify({
                'status': 'error',
                'message': '缺少音频URL参数'
            }), 400

        # 构建分类提示文本
        category_text = ""
        if categories:
            category_text = f"\n可用的分类包括：{', '.join(categories)}"

        # 添加日期解析辅助函数
        def parse_chinese_date(date_str, current_time):
            """解析中文日期格式（如"2024年1月14日"、"1月15日"、"1月14号"等）"""
            if not isinstance(date_str, str):
                return None
            
            import re
            from datetime import datetime, timedelta
            
            # 提取时间部分（如果有）
            time_part = None
            hour = current_time.hour
            minute = current_time.minute
            
            # 检查是否包含时间信息
            time_patterns = [
                (r'(\d{1,2}):(\d{2})', lambda m: (int(m.group(1)), int(m.group(2)))),
                (r'(\d{1,2})点', lambda m: (int(m.group(1)), 0)),
                (r'上午|早上|早晨|早', lambda m: (9, 0)),
                (r'中午|午间|正午', lambda m: (12, 0)),
                (r'下午|午后', lambda m: (15, 0)),
                (r'晚上|傍晚|晚', lambda m: (19, 0)),
                (r'夜里|深夜|半夜', lambda m: (22, 0)),
            ]
            
            for pattern, extractor in time_patterns:
                match = re.search(pattern, date_str)
                if match:
                    try:
                        hour, minute = extractor(match)
                        time_part = (hour, minute)
                        break
                    except:
                        pass
            
            # 尝试解析中文日期格式
            # 格式1: "2024年1月14日" 或 "2024年1月14号"
            match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]', date_str)
            if match:
                try:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    date_value = datetime(year, month, day)
                    if time_part:
                        date_value = date_value.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
                    return date_value
                except ValueError:
                    pass
            
            # 格式2: "1月14日" 或 "1月14号" (没有年份，使用当前年份)
            match = re.search(r'(\d{1,2})月(\d{1,2})[日号]', date_str)
            if match:
                try:
                    year = current_time.year
                    month = int(match.group(1))
                    day = int(match.group(2))
                    date_value = datetime(year, month, day)
                    # 如果日期已经过去（在当前日期之前超过30天），可能是明年
                    if date_value < current_time - timedelta(days=30):
                        date_value = datetime(year + 1, month, day)
                    if time_part:
                        date_value = date_value.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
                    return date_value
                except ValueError:
                    pass
            
            # 格式3: "1月14" (没有"日"或"号")
            match = re.search(r'(\d{1,2})月(\d{1,2})(?![日号])', date_str)
            if match:
                try:
                    year = current_time.year
                    month = int(match.group(1))
                    day = int(match.group(2))
                    date_value = datetime(year, month, day)
                    if date_value < current_time - timedelta(days=30):
                        date_value = datetime(year + 1, month, day)
                    if time_part:
                        date_value = date_value.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
                    return date_value
                except ValueError:
                    pass
            
            # 格式4: "14号" 或 "14日" (只有日期，使用当前年月)
            match = re.search(r'(\d{1,2})[日号]', date_str)
            if match and '月' not in date_str:
                try:
                    year = current_time.year
                    month = current_time.month
                    day = int(match.group(1))
                    date_value = datetime(year, month, day)
                    # 如果日期已经过去超过7天，可能是下个月
                    if date_value < current_time - timedelta(days=7):
                        if month == 12:
                            date_value = datetime(year + 1, 1, day)
                        else:
                            date_value = datetime(year, month + 1, day)
                    if time_part:
                        date_value = date_value.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
                    return date_value
                except ValueError:
                    pass
            
            return None
        
        def parse_relative_date(date_str, current_time):
            """解析中文相对日期描述，转换为实际日期"""
            if not isinstance(date_str, str):
                return None
            
            date_str_lower = date_str.lower().strip()
            from datetime import timedelta
            import re
            
            # 提取时间部分（如果有）
            time_part = None
            hour = current_time.hour
            minute = current_time.minute
            
            # 检查是否包含时间信息
            time_patterns = [
                (r'(\d{1,2}):(\d{2})', lambda m: (int(m.group(1)), int(m.group(2)))),
                (r'(\d{1,2})点', lambda m: (int(m.group(1)), 0)),
                (r'上午|早上|早晨|早', lambda m: (9, 0)),
                (r'中午|午间|正午', lambda m: (12, 0)),
                (r'下午|午后', lambda m: (15, 0)),
                (r'晚上|傍晚|晚', lambda m: (19, 0)),
                (r'夜里|深夜|半夜', lambda m: (22, 0)),
            ]
            
            for pattern, extractor in time_patterns:
                match = re.search(pattern, date_str_lower)
                if match:
                    try:
                        hour, minute = extractor(match)
                        time_part = (hour, minute)
                        break  # 找到时间就停止
                    except:
                        pass
            
            # 计算日期偏移（按优先级顺序检查，避免误匹配）
            date_offset = None
            if '大前天' in date_str_lower or '大前日' in date_str_lower:
                date_offset = -3
            elif '大后天' in date_str_lower or '大后日' in date_str_lower:
                date_offset = 3
            elif '前天' in date_str_lower or '前日' in date_str_lower:
                date_offset = -2
            elif '后天' in date_str_lower or '后日' in date_str_lower:
                date_offset = 2
            elif '昨天' in date_str_lower or '昨日' in date_str_lower or date_str_lower == '昨':
                date_offset = -1
            elif '明天' in date_str_lower or '明日' in date_str_lower or date_str_lower == '明':
                date_offset = 1
            elif '今天' in date_str_lower or '今日' in date_str_lower or date_str_lower == '今':
                date_offset = 0
            
            if date_offset is None:
                return None  # 不是相对日期描述
            
            # 计算目标日期
            target_date = current_time + timedelta(days=date_offset)
            
            # 如果有时间信息，更新时间部分
            if time_part:
                target_date = target_date.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
            else:
                # 如果没有时间信息，保持当前时间
                pass
            
            return target_date
        
        # 构建系统提示词
        system_prompt = f"""你是一个智能记账助手，专门帮助用户从语音中提取记账信息。

任务：
1. 仔细听取用户的语音内容
2. 识别并提取所有记账相关信息
3. 对每条记账信息提取：金额（数字）、标题（简短描述）、分类、日期时间
4. 如果语音中包含多条记账信息，请全部提取{category_text}
5. **重要**：如果语音中提到日期或时间（如"今天"、"昨天"、"明天"、"上午"、"下午"、"晚上"、"几点"等），必须识别并提取

输出格式要求：
- 必须返回有效的JSON数组格式
- 每个对象包含：amount（金额，纯数字）、title（标题）、category（分类）、date（日期时间）
- 如果没有提到具体金额，尝试根据常识推断合理金额
- 如果分类不明确，根据内容智能归类
- **日期时间识别规则**（必须严格按照以下规则识别，**重要：date字段请返回相对日期描述，如"昨天"、"今天"、"明天"等，而不是绝对日期**）：
  - "今天"、"今日"、"今" → 当前日期，保持当前时间或语音中提到的时间
  - "昨天"、"昨日"、"昨" → 当前日期减1天
  - "明天"、"明日"、"明" → 当前日期加1天
  - "前天"、"前日" → 当前日期减2天
  - "后天"、"后日" → 当前日期加2天
  - "大后天"、"大后日" → 当前日期加3天
  - "大前天"、"大前日" → 当前日期减3天
  - "上周"、"上星期" → 当前日期减7天
  - "下周"、"下星期" → 当前日期加7天
  - "上周X"（如"上周一"）→ 计算最近的上周一日期
  - "下周X"（如"下周一"）→ 计算最近的下周一日期
  - "上午"、"早上"、"早晨"、"早" → 设置为当天的 09:00
  - "中午"、"午间"、"正午" → 设置为当天的 12:00
  - "下午"、"午后" → 设置为当天的 15:00
  - "晚上"、"傍晚"、"晚" → 设置为当天的 19:00
  - "夜里"、"深夜"、"半夜" → 设置为当天的 22:00
  - 如果提到具体时间（如"3点"、"15:30"、"下午3点"、"晚上8点"），使用该时间
  - 如果提到"X月X日"、"X号"等具体日期，使用该日期
  - 如果未提及日期，使用当前日期和时间
  - **重要**：日期和时间必须同时识别，如果只提到日期，时间使用当前时间；如果只提到时间，日期使用当前日期

示例输出：
[
  {{"amount": 35, "title": "午餐", "category": "餐饮", "date": "今天 中午"}},
  {{"amount": 50, "title": "打车去公司", "category": "交通", "date": "昨天 上午"}},
  {{"amount": 100, "title": "晚餐", "category": "餐饮", "date": "明天 晚上"}}
]

**重要提示**：
- date字段请使用相对日期描述（如"昨天"、"今天"、"明天"、"前天"、"后天"等），而不是绝对日期
- 如果提到具体时间，可以加上时间描述（如"昨天 下午"、"今天 3点"等）
- 服务器会自动将相对日期转换为实际日期"""

        # 调用阿里云语音识别API
        try:
            completion = dashscope_client.chat.completions.create(
                model="qwen-omni-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_url,
                                    "format": "wav",
                                },
                            },
                            {"type": "text", "text": "请分析这段语音中的记账信息，并按要求返回JSON格式的记账条目。"},
                        ],
                    },
                ],
                # 只需要文本输出
                modalities=["text"],
                stream=False,
                temperature=0.3,  # 降低温度以提高输出的确定性
            )

            # 获取AI返回的内容
            ai_response = completion.choices[0].message.content

            # 尝试解析JSON
            try:
                # 清理可能的markdown代码块标记
                if '```json' in ai_response:
                    ai_response = ai_response.split('```json')[1].split('```')[0].strip()
                elif '```' in ai_response:
                    ai_response = ai_response.split('```')[1].split('```')[0].strip()

                parsed_items = json.loads(ai_response)

                # 确保返回的是数组
                if not isinstance(parsed_items, list):
                    parsed_items = [parsed_items]

                # 验证和清理数据
                cleaned_items = []
                from datetime import datetime
                current_time = datetime.now()
                
                for item in parsed_items:
                    if isinstance(item, dict):
                        # 处理日期字段
                        date_value = current_time  # 默认使用当前时间
                        if 'date' in item:
                            try:
                                # 尝试解析 ISO8601 格式的日期
                                date_str = item.get('date')
                                if isinstance(date_str, str):
                                    # 解析顺序：
                                    # 1. 首先尝试解析中文相对日期描述（如"昨天"、"前天"等）
                                    # 2. 然后尝试解析中文日期格式（如"2024年1月14日"、"1月15日"等）
                                    # 3. 最后尝试解析标准日期格式（ISO8601等）
                                    
                                    relative_date = parse_relative_date(date_str, current_time)
                                    if relative_date:
                                        date_value = relative_date
                                    else:
                                        # 尝试解析中文日期格式
                                        chinese_date = parse_chinese_date(date_str, current_time)
                                        if chinese_date:
                                            date_value = chinese_date
                                        else:
                                            # 尝试多种标准日期格式
                                            date_formats = [
                                                '%Y-%m-%dT%H:%M:%S',
                                                '%Y-%m-%dT%H:%M:%S.%f',
                                                '%Y-%m-%d %H:%M:%S',
                                                '%Y-%m-%d %H:%M:%S.%f',
                                                '%Y-%m-%d',
                                                '%Y/%m/%d %H:%M:%S',
                                                '%Y/%m/%d',
                                                '%m/%d/%Y %H:%M:%S',
                                                '%m/%d/%Y',
                                                '%d/%m/%Y %H:%M:%S',
                                                '%d/%m/%Y',
                                            ]
                                            parsed = False
                                            for fmt in date_formats:
                                                try:
                                                    date_value = datetime.strptime(date_str, fmt)
                                                    parsed = True
                                                    break
                                                except ValueError:
                                                    continue
                                            if not parsed:
                                                # 如果解析失败，使用当前时间
                                                date_value = current_time
                                elif isinstance(date_str, (int, float)):
                                    # 如果是时间戳
                                    date_value = datetime.fromtimestamp(date_str)
                            except Exception as e:
                                # 解析失败，使用当前时间
                                print(f"日期解析错误: {e}, 原始值: {date_str}")
                                date_value = current_time
                        
                        cleaned_item = {
                            'amount': float(item.get('amount', 0)),
                            'title': str(item.get('title', '未命名支出')),
                            'category': str(item.get('category', '其他')),
                            'date': date_value.isoformat()  # 转换为 ISO8601 格式字符串
                        }
                        cleaned_items.append(cleaned_item)
                
                # 确保所有条目都有日期字段（如果没有，使用当前时间）
                for item in cleaned_items:
                    if 'date' not in item:
                        item['date'] = current_time.isoformat()

                return jsonify({
                    'status': 'success',
                    'message': '语音解析成功',
                    'data': cleaned_items,
                    'raw_response': ai_response  # 可选：返回原始响应用于调试
                }), 200

            except json.JSONDecodeError as e:
                # 如果解析失败，尝试提取关键信息
                return jsonify({
                    'status': 'partial_success',
                    'message': '语音识别成功，但数据格式需要调整',
                    'data': [{
                        'amount': 0,
                        'title': '请手动编辑',
                        'category': '其他'
                    }],
                    'raw_response': ai_response
                }), 200

        except Exception as api_error:
            return jsonify({
                'status': 'error',
                'message': f'AI服务调用失败: {str(api_error)}'
            }), 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'语音解析失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    # 从环境变量读取端口,如果没有则使用默认值 5001
    port = int(os.getenv('PORT', '5001'))

    # 开发环境运行
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=port,       # 从环境变量读取的端口
        debug=True       # 调试模式
    )
