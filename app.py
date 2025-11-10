#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 服务端
用于语音记账应用的后端服务
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

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


if __name__ == '__main__':
    # 从环境变量读取端口,如果没有则使用默认值 5001
    port = int(os.getenv('PORT', '5001'))

    # 开发环境运行
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=port,       # 从环境变量读取的端口
        debug=True       # 调试模式
    )
