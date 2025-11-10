#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask 服务端
用于语音记账应用的后端服务
"""

import os
import uuid
from datetime import datetime
from flask import Flask, jsonify, request
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# 加载环境变量
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
    raise ValueError("请在 .env 文件中配置 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY")

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


@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    """
    接收录音文件并上传到 Supabase Storage
    
    请求参数:
        - file: 音频文件 (multipart/form-data)
        - user_id: 用户ID (可选)
        
    返回:
        - success: 上传成功，返回文件 URL
        - error: 上传失败，返回错误信息
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
                'message': f'不支持的文件类型，仅支持: {", ".join(ALLOWED_EXTENSIONS)}'
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
        response = supabase.storage.from_('user-audio').upload(
            path=storage_path,
            file=file_content,
            file_options={
                'content-type': f'audio/{file_ext}',
                'cache-control': '3600',
                'upsert': 'false'
            }
        )
        
        # 获取公开 URL
        public_url = supabase.storage.from_('user-audio').get_public_url(storage_path)
        
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
    # 开发环境运行
    app.run(
        host='0.0.0.0',  # 允许外部访问
        port=5000,        # 端口
        debug=True        # 调试模式
    )

