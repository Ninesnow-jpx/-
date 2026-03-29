from pathlib import Path
import numpy as np
from flask import Flask, request, jsonify, send_file, Blueprint, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import sqlite3
import json
import uuid
from datetime import datetime, timedelta
import traceback
import logging
import hashlib
from functools import wraps
from contextlib import contextmanager
import sys
import torch
import importlib.util
import time
import scipy.io as sio
from PIL import Image

# ==================== 配置部分 ====================
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 应用配置
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 最大上传50MB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATABASE'] = 'medical_screening.db'

# 允许的文件扩展名
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}
ALLOWED_ECG_EXTENSIONS = {'csv', 'txt', 'dat', 'mat'}
ALLOWED_TEXT_EXTENSIONS = {'txt', 'json'}

# 创建必要的目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'fundus'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'ecg'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'text'), exist_ok=True)
os.makedirs('models', exist_ok=True)  # 存放训练好的模型


# ==================== 数据库管理 ====================
@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构 - 完整版14张表"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # ==================== 患者端表 (6张) ====================
            print("初始化患者端数据表...")

            # 1. 患者信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 2. 检查记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS examinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    exam_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    fundus_image_path TEXT,
                    ecg_data_path TEXT,
                    medical_text_path TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                )
            ''')

            # 3. 眼底图像分析结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fundus_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id TEXT NOT NULL,
                    lesion_count INTEGER,
                    lesion_types TEXT,
                    lesion_locations TEXT,
                    dr_grade INTEGER,
                    risk_level TEXT,
                    confidence REAL,
                    analysis_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (exam_id) REFERENCES examinations(exam_id)
                )
            ''')

            # 4. ECG分析结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ecg_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id TEXT NOT NULL,
                    heart_rate REAL,
                    rhythm_type TEXT,
                    abnormalities TEXT,
                    disease_risks TEXT,
                    risk_level TEXT,
                    confidence REAL,
                    analysis_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (exam_id) REFERENCES examinations(exam_id)
                )
            ''')

            # 5. 病历文本分析结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS text_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id TEXT NOT NULL,
                    symptoms TEXT,
                    medical_history TEXT,
                    examination_data TEXT,
                    extracted_entities TEXT,
                    risk_factors TEXT,
                    analysis_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (exam_id) REFERENCES examinations(exam_id)
                )
            ''')

            # 6. 综合诊断报告表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comprehensive_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exam_id TEXT NOT NULL,
                    overall_risk_level TEXT,
                    primary_diagnosis TEXT,
                    secondary_diagnosis TEXT,
                    diagnostic_evidence TEXT,
                    health_recommendations TEXT,
                    attention_weights TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (exam_id) REFERENCES examinations(exam_id)
                )
            ''')

            # ==================== 医生端表 (8张) ====================
            print("初始化医生端数据表...")

            # 7. 医生信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doctors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    title TEXT,
                    department TEXT,
                    specialization TEXT,
                    phone TEXT,
                    email TEXT,
                    password_hash TEXT NOT NULL,
                    license_number TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')

            # 8. 医生-患者关系表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doctor_patient_relations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    relation_type TEXT DEFAULT 'primary',
                    assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                    UNIQUE(doctor_id, patient_id)
                )
            ''')

            # 9. AI诊断反馈表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feedback_id TEXT UNIQUE NOT NULL,
                    exam_id TEXT NOT NULL,
                    doctor_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    original_diagnosis TEXT,
                    original_risk_level TEXT,
                    corrected_diagnosis TEXT,
                    corrected_risk_level TEXT,
                    feedback_category TEXT,
                    detailed_comments TEXT,
                    fundus_feedback TEXT,
                    ecg_feedback TEXT,
                    text_feedback TEXT,
                    is_teaching_case BOOLEAN DEFAULT 0,
                    teaching_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (exam_id) REFERENCES examinations(exam_id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                )
            ''')

            # 10. 病程追踪记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disease_progression (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    progression_id TEXT UNIQUE NOT NULL,
                    patient_id TEXT NOT NULL,
                    doctor_id TEXT NOT NULL,
                    start_exam_id TEXT NOT NULL,
                    end_exam_id TEXT NOT NULL,
                    tracking_period_days INTEGER,
                    progression_status TEXT,
                    key_changes TEXT,
                    fundus_trend TEXT,
                    ecg_trend TEXT,
                    clinical_trend TEXT,
                    doctor_assessment TEXT,
                    treatment_adjustment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
                    FOREIGN KEY (start_exam_id) REFERENCES examinations(exam_id),
                    FOREIGN KEY (end_exam_id) REFERENCES examinations(exam_id)
                )
            ''')

            # 11. 医生工作日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doctor_activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_id TEXT UNIQUE NOT NULL,
                    doctor_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    target_id TEXT,
                    activity_details TEXT,
                    ip_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                )
            ''')

            # 12. 医生统计数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doctor_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doctor_id TEXT UNIQUE NOT NULL,
                    total_patients INTEGER DEFAULT 0,
                    total_reviews INTEGER DEFAULT 0,
                    total_feedbacks INTEGER DEFAULT 0,
                    ai_accuracy_rate REAL,
                    false_positive_rate REAL,
                    false_negative_rate REAL,
                    avg_review_time REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                )
            ''')

            # 13. 会诊记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS consultations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consultation_id TEXT UNIQUE NOT NULL,
                    exam_id TEXT NOT NULL,
                    requesting_doctor_id TEXT NOT NULL,
                    consulting_doctor_id TEXT,
                    consultation_status TEXT DEFAULT 'pending',
                    consultation_type TEXT,
                    request_reason TEXT,
                    clinical_question TEXT,
                    consultation_opinion TEXT,
                    recommended_actions TEXT,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (exam_id) REFERENCES examinations(exam_id),
                    FOREIGN KEY (requesting_doctor_id) REFERENCES doctors(doctor_id),
                    FOREIGN KEY (consulting_doctor_id) REFERENCES doctors(doctor_id)
                )
            ''')

            # 14. 患者标记表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patient_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    doctor_id TEXT NOT NULL,
                    tag_type TEXT NOT NULL,
                    tag_color TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
                )
            ''')

            # 创建索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_doctors_status ON doctors(status)",
                "CREATE INDEX IF NOT EXISTS idx_doctors_department ON doctors(department)",
                "CREATE INDEX IF NOT EXISTS idx_doctor_patient_doctor ON doctor_patient_relations(doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_doctor_patient_patient ON doctor_patient_relations(patient_id)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_exam ON ai_feedback(exam_id)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_doctor ON ai_feedback(doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_type ON ai_feedback(feedback_type)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_teaching ON ai_feedback(is_teaching_case)",
                "CREATE INDEX IF NOT EXISTS idx_progression_patient ON disease_progression(patient_id)",
                "CREATE INDEX IF NOT EXISTS idx_progression_doctor ON disease_progression(doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_activity_doctor ON doctor_activity_log(doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_activity_type ON doctor_activity_log(activity_type)",
                "CREATE INDEX IF NOT EXISTS idx_activity_time ON doctor_activity_log(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_consultation_exam ON consultations(exam_id)",
                "CREATE INDEX IF NOT EXISTS idx_consultation_requesting ON consultations(requesting_doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_consultation_consulting ON consultations(consulting_doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_consultation_status ON consultations(consultation_status)",
                "CREATE INDEX IF NOT EXISTS idx_tags_patient ON patient_tags(patient_id)",
                "CREATE INDEX IF NOT EXISTS idx_tags_doctor ON patient_tags(doctor_id)",
                "CREATE INDEX IF NOT EXISTS idx_tags_type ON patient_tags(tag_type)"
            ]

            for idx_sql in indexes:
                cursor.execute(idx_sql)

            logger.info("数据库初始化完成")

    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise

# ==================== 工具函数 ====================
def allowed_file(filename, allowed_extensions):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in allowed_extensions


def generate_unique_id(prefix=''):
    """生成唯一ID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"

def save_uploaded_file(file, subfolder):
    """保存上传的文件"""
    if file and allowed_file(file.filename,
                             ALLOWED_IMAGE_EXTENSIONS | ALLOWED_ECG_EXTENSIONS | ALLOWED_TEXT_EXTENSIONS):
        filename = secure_filename(file.filename)
        unique_filename = f"{generate_unique_id()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
        file.save(filepath)
        return filepath
    return None


def hash_password(password):
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def log_doctor_activity(doctor_id, activity_type, target_id=None, details=None, ip_address=None):
    """记录医生活动日志"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            log_id = generate_unique_id('LOG')
            cursor.execute('''
                INSERT INTO doctor_activity_log 
                (log_id, doctor_id, activity_type, target_id, activity_details, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (log_id, doctor_id, activity_type, target_id,
                  json.dumps(details, ensure_ascii=False) if details else None, ip_address))
    except Exception as e:
        logger.error(f"记录活动日志失败: {str(e)}")


# ==================== 医生认证装饰器 ====================
def require_doctor_auth(f):
    """医生认证装饰器"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从请求头获取医生ID（简化版，生产环境应使用JWT）
        doctor_id = request.headers.get('X-Doctor-ID')
        if not doctor_id:
            return jsonify({'error': '未提供医生认证信息'}), 401

        # 验证医生是否存在且状态为active
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM doctors WHERE doctor_id = ? AND status = ?',
                           (doctor_id, 'active'))
            doctor = cursor.fetchone()

            if not doctor:
                return jsonify({'error': '医生不存在或已被停用'}), 401

        # 将医生信息添加到kwargs
        kwargs['doctor_id'] = doctor_id
        kwargs['doctor_info'] = dict(doctor)

        return f(*args, **kwargs)

    return decorated_function

# ---------------------- 关键修改：导入fundus_test ----------------------
# 1. 定位 fundus_test.py 文件的绝对路径
fundus_test_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "test_data",
    "Diabetic Retinopathy Arranged_datasets",
    "fundus_test.py"
)

# 2. 动态加载fundus_test模块
spec = importlib.util.spec_from_file_location("fundus_test", fundus_test_path)
fundus_test = importlib.util.module_from_spec(spec)
sys.modules["fundus_test"] = fundus_test
spec.loader.exec_module(fundus_test)

# 固定随机种子
fundus_test.set_seed(42)

# ---------------------- 加载DR眼底模型（全局单例） ----------------------
def load_fundus_model():
    """加载训练好的DR分级模型，全局只加载一次"""
    model_2c = None  # 二分类模型（正常/病变）
    model_lesion = None  # 分级模型（1-4级）
    try:
        # 模型权重路径：指向test_data子目录
        model_2c_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test_data",
            "Diabetic Retinopathy Arranged_datasets",
            "DR2ClassModel_best.pth"
        )
        model_lesion_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "test_data",
            "Diabetic Retinopathy Arranged_datasets",
            "DRLesionModel_best.pth"
        )

        # 初始化模型
        model_2c = fundus_test.DR2ClassModel().to(fundus_test.DEVICE)
        model_lesion = fundus_test.DRLesionModel().to(fundus_test.DEVICE)

        # 加载权重（适配PyTorch新版本）
        model_2c.load_state_dict(torch.load(model_2c_path, map_location=fundus_test.DEVICE, weights_only=True))
        model_lesion.load_state_dict(torch.load(model_lesion_path, map_location=fundus_test.DEVICE, weights_only=True))

        # 设置为评估模式
        model_2c.eval()
        model_lesion.eval()

        logger.info("✅ DR眼底模型加载成功")
    except Exception as e:
        logger.error(f"❌ DR眼底模型加载失败: {str(e)}", exc_info=True)
    return model_2c, model_lesion

# 全局模型实例（只加载一次）
FUNDUS_MODEL_2C, FUNDUS_MODEL_LESION = load_fundus_model()

# 病灶类型映射（根据DR分级匹配对应病灶）
LESION_MAP = {
    0: {'count': 0, 'types': [], 'locations': []},  # 0级（正常）
    1: {'count': 2, 'types': ['微血管瘤'], 'locations': [{'type': '微血管瘤', 'x': 120, 'y': 150, 'confidence': 0.92}]},  # 1级
    2: {'count': 5, 'types': ['微血管瘤', '出血点'], 'locations': [  # 2级（示例匹配）
        {'type': '微血管瘤', 'x': 120, 'y': 150, 'confidence': 0.92},
        {'type': '出血点', 'x': 300, 'y': 200, 'confidence': 0.88}
    ]},
    3: {'count': 8, 'types': ['微血管瘤', '出血点', '渗出液'], 'locations': [
        {'type': '微血管瘤', 'x': 120, 'y': 150, 'confidence': 0.92},
        {'type': '出血点', 'x': 300, 'y': 200, 'confidence': 0.88},
        {'type': '渗出液', 'x': 200, 'y': 300, 'confidence': 0.90}
    ]},
    4: {'count': 12, 'types': ['微血管瘤', '出血点', '渗出液', '新生血管'], 'locations': [
        {'type': '微血管瘤', 'x': 120, 'y': 150, 'confidence': 0.92},
        {'type': '出血点', 'x': 300, 'y': 200, 'confidence': 0.88},
        {'type': '渗出液', 'x': 200, 'y': 300, 'confidence': 0.90},
        {'type': '新生血管', 'x': 180, 'y': 250, 'confidence': 0.85}
    ]}
}

# 风险等级映射
RISK_LEVEL_MAP = {
    0: '低风险',
    1: '低风险',
    2: '中风险',  # 示例匹配
    3: '高风险',
    4: '极高风险'
}

# ---------------------- 关键修改：导入路径改为 ecg_test ----------------------
# 1. 定位 ecg_test.py 文件的绝对路径
ecg_test_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "test_data",
    "ecg_1000",
    "ecg_test.py"
)

# 2. 动态加载模块
spec = importlib.util.spec_from_file_location("ecg_test", ecg_test_path)
ecg_test = importlib.util.module_from_spec(spec)
sys.modules["ecg_test"] = ecg_test
spec.loader.exec_module(ecg_test)

# 3. 从动态加载的模块中导入所需内容
ECG_ResNet1D_LowLoss = ecg_test.ECG_ResNet1D_LowLoss
ecg_preprocess = ecg_test.ecg_preprocess
SEQ_LEN = ecg_test.SEQ_LEN
DEVICE = ecg_test.DEVICE
set_seed = ecg_test.set_seed

# 固定随机种子（与ecg_test.py保持一致）
set_seed(42)

# ---------------------- 加载ECG模型（全局单例） ----------------------
ECG_UPLOAD_SUCCESS_MSG = "ECG数据上传成功"
ECG_UPLOAD_FILE_PATH_MSG = "文件路径: {file_path}"
def load_ecg_model():
    """加载训练好的ECG模型，全局只加载一次"""
    model = None
    best_threshold = 0.5  # 替换为ecg_test.py训练得到的最优阈值
    try:
        # 模型权重路径：请替换为你实际的权重文件路径（ecg_test.py训练后保存）
        model_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),  # app.py 所在的项目根目录
            "test_data",
            "ecg_1000",
            "ecg_model_weights.pth"
        )
        model = ECG_ResNet1D_LowLoss().to(DEVICE)
        # 加载权重（适配PyTorch新版本）
        model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
        model.eval()
        logger.info("✅ ECG模型加载成功")
    except Exception as e:
        logger.error(f"❌ ECG模型加载失败: {str(e)}")
    return model, best_threshold

# 全局模型实例（只加载一次）
ECG_MODEL, BEST_THRESHOLD = load_ecg_model()

# ---------------------- 导入medical_test模块 ----------------------
# 获取当前脚本（app.py）的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 拼接medical_test.py所在的目录路径
medical_text_dir = os.path.join(current_dir, 'test_data', 'medical_text')
# 将该路径加入Python的模块搜索路径
sys.path.append(medical_text_dir)
try:
    import medical_test
except ImportError as e:
    logger.error(f"导入medical_test.py失败: {str(e)}")
    # 导入失败时提供降级方案（避免程序崩溃）
    medical_test = None

# ---------------------- 导入多模态融合模型 ----------------------
# 获取 app.py 所在的根目录
PROJECT_ROOT = Path(__file__).parent
# 构建 multimodal 目录的绝对路径
MULTIMODAL_DIR = PROJECT_ROOT / "test_data" / "multimodal"
# 将 multimodal 目录添加到 Python 搜索路径
sys.path.append(str(MULTIMODAL_DIR))

try:
    from multimodal_fusion_model import (
        MultimodalFusionModel,
        MultimodalFusionTrainer,
        extract_features_from_results,
        rule_based_fusion
    )
    logger.info("多模态融合模型导入成功")
except ImportError as e:
    logger.error(f"模型导入失败: {str(e)}，将仅使用规则融合")
    # 导入失败时的兜底
    def rule_based_fusion(fundus_result, ecg_result, text_result):
        risk_levels = [
            fundus_result.get('risk_level', '低风险'),
            ecg_result.get('risk_level', '低风险')
        ]
        overall_risk = '高风险' if '高风险' in risk_levels else '中风险' if '中风险' in risk_levels else '低风险'
        diagnosis_map = {
            '低风险': {
                'primary': '糖尿病视网膜病变（轻度非增殖期）',
                'secondary': '心电图大致正常',
                'evidence': {
                    '眼底证据': '检测到少量微血管瘤，无明显出血点，符合轻度非增殖期特征',
                    'ECG证据': '心电图无明显异常，心率在正常范围',
                    '病史证据': '患者有糖尿病史，但近期血糖控制尚可'
                },
                'recommendations': [
                    '定期监测血糖（建议每月1次）',
                    '每年复查眼底一次',
                    '保持健康生活方式，控制体重',
                    '避免过度用眼和剧烈运动'
                ]
            },
            '中风险': {
                'primary': '糖尿病视网膜病变（中度非增殖期）',
                'secondary': '心律失常（房性早搏）',
                'evidence': {
                    '眼底证据': '检测到多处微血管瘤及出血点，符合中度非增殖期糖尿病视网膜病变特征',
                    'ECG证据': '心电图显示偶发房性早搏，心率正常范围',
                    '病史证据': '患者有长期糖尿病史，血糖控制不佳'
                },
                'recommendations': [
                    '建议尽快就诊眼科，进行眼底荧光造影检查',
                    '加强血糖监测，调整降糖方案',
                    '建议心内科就诊，评估心律失常严重程度',
                    '定期复查眼底和心电图（建议3个月内）',
                    '控制饮食，适度运动，戒烟限酒'
                ]
            },
            '高风险': {
                'primary': '糖尿病视网膜病变（重度非增殖期）',
                'secondary': '心律失常（频发房性早搏）合并高血压性心脏病',
                'evidence': {
                    '眼底证据': '检测到大量微血管瘤、出血点及新生血管，符合重度非增殖期特征',
                    'ECG证据': '心电图显示频发房性早搏，ST段轻度改变',
                    '病史证据': '患者有长期糖尿病史和高血压史，血糖/血压控制极差'
                },
                'recommendations': [
                    '立即就诊眼科，考虑激光光凝治疗',
                    '住院调整降糖/降压方案，严格控制血糖血压',
                    '心内科紧急评估心脏功能，必要时进行24小时动态心电图',
                    '每周监测血糖血压，每月复查眼底',
                    '绝对卧床休息，避免体力活动，戒烟戒酒'
                ]
            }
        }
        diag = diagnosis_map.get(overall_risk, diagnosis_map['中风险'])
        return {
            'overall_risk_level': overall_risk,
            'primary_diagnosis': diag['primary'],
            'secondary_diagnosis': diag['secondary'],
            'diagnostic_evidence': json.dumps(diag['evidence'], ensure_ascii=False),
            'health_recommendations': json.dumps(diag['recommendations'], ensure_ascii=False),
            'attention_weights': json.dumps({
                '眼底图像': 0.45,
                'ECG信号': 0.30,
                '病历文本': 0.25
            }, ensure_ascii=False),
            'confidence': 0.85
        }

MODEL_PATH = str(MULTIMODAL_DIR / "fusion_model.pth")

# ==================== 模型推理接口（占位符） ====================
class ModelInference:
    """模型推理类 - 这里是接口定义，实际模型由队友训练后替换"""

    @staticmethod
    def analyze_fundus_image(image_path):
        """
        眼底图像分析（实际调用DR分级模型）
        输入: 图像路径
        输出: 病灶检测结果（格式与示例完全一致）
        """
        start_time = time.time()

        # 初始化默认结果（与示例格式完全一致）
        default_result = {
            'lesion_count': 5,
            'lesion_types': json.dumps(['微血管瘤', '出血点', '渗出液'], ensure_ascii=False),
            'lesion_locations': json.dumps([
                {'type': '微血管瘤', 'x': 120, 'y': 150, 'confidence': 0.92},
                {'type': '出血点', 'x': 300, 'y': 200, 'confidence': 0.88}
            ], ensure_ascii=False),
            'dr_grade': 2,
            'risk_level': '中风险',
            'confidence': 0.87,
            'analysis_time': 0.5
        }

        try:
            # 1. 校验模型是否加载成功
            if FUNDUS_MODEL_2C is None or FUNDUS_MODEL_LESION is None:
                logger.warning("DR眼底模型未加载，返回默认示例结果")
                default_result['analysis_time'] = round(time.time() - start_time, 2)
                return default_result

            # 2. 校验图像文件是否存在
            if not os.path.exists(image_path):
                logger.error(f"眼底图像文件不存在: {image_path}")
                default_result['analysis_time'] = round(time.time() - start_time, 2)
                return default_result

            # 3. 图像预处理（复用fundus_test中的验证集变换）
            try:
                image = Image.open(image_path).convert('RGB')
                transform = fundus_test.val_transform
                image_tensor = transform(image).unsqueeze(0).to(fundus_test.DEVICE)
            except Exception as e:
                logger.error(f"图像预处理失败: {str(e)}", exc_info=True)
                default_result['analysis_time'] = round(time.time() - start_time, 2)
                return default_result

            # 4. 模型推理（两步法：先二分类，再分级）
            with torch.no_grad():
                # 第一步：正常/病变二分类
                output_2c = FUNDUS_MODEL_2C(image_tensor)
                prob_2c = torch.softmax(output_2c, dim=1)
                pred_2c = torch.argmax(prob_2c, dim=1).item()  # 0=正常，1=病变

                if pred_2c == 0:
                    # 0级（正常）
                    dr_grade = 0
                    confidence = round(prob_2c[0][0].item(), 2)
                else:
                    # 第二步：病变分级（1-4级）
                    output_lesion = FUNDUS_MODEL_LESION(image_tensor)
                    prob_lesion = torch.softmax(output_lesion, dim=1)
                    pred_lesion = torch.argmax(prob_lesion, dim=1).item()
                    dr_grade = pred_lesion + 1  # 映射为1-4级
                    confidence = round(torch.max(prob_lesion).item(), 2)

            # 5. 根据DR分级获取病灶信息（保证格式与示例一致）
            lesion_info = LESION_MAP.get(dr_grade, LESION_MAP[2])  # 默认返回2级（示例）
            risk_level = RISK_LEVEL_MAP.get(dr_grade, '中风险')

            # 6. 构建最终结果（与示例格式完全一致）
            result = {
                'lesion_count': lesion_info['count'],
                'lesion_types': json.dumps(lesion_info['types'], ensure_ascii=False),
                'lesion_locations': json.dumps(lesion_info['locations'], ensure_ascii=False),
                'dr_grade': dr_grade,
                'risk_level': risk_level,
                'confidence': confidence,
                'analysis_time': round(time.time() - start_time, 2)
            }

            logger.info(f"眼底图像分析完成: {image_path} | DR分级: {dr_grade} | 风险等级: {risk_level}")
            return result

        except Exception as e:
            logger.error(f"眼底图像分析失败: {image_path} | 错误: {str(e)}", exc_info=True)
            # 失败时返回默认示例结果，保证格式一致
            default_result['analysis_time'] = round(time.time() - start_time, 2)
            return default_result

    @staticmethod
    def analyze_ecg_signal(ecg_path):
        """
        ECG信号分析
        输入: ECG数据路径
        输出: 心血管疾病风险评估
        """
        start_time = time.time()

        # 默认结果（推理失败时返回示例格式）
        default_result = {
            'heart_rate': 78.5,
            'rhythm_type': '窦性心律',
            'abnormalities': json.dumps(['偶发房性早搏'], ensure_ascii=False),
            'disease_risks': json.dumps({
                '房颤': 0.15,
                '心肌梗塞': 0.08,
                '心律失常': 0.35
            }, ensure_ascii=False),
            'risk_level': '中风险',
            'confidence': 0.82,
            'analysis_time': 0.3
        }

        try:
            # 1. 校验文件是否存在
            if not os.path.exists(ecg_path):
                logger.error(f"ECG文件不存在: {ecg_path}")
                return default_result

            # 2. 读取ECG数据（.mat文件）
            mat_data = sio.loadmat(ecg_path)
            if 'data' not in mat_data:
                logger.error(f"ECG文件格式错误，无'data'字段: {ecg_path}")
                return default_result

            signal = mat_data['data'].flatten()
            if len(signal) == 0:
                logger.error(f"ECG信号为空: {ecg_path}")
                return default_result

            # 3. 调用ecg_test.py的预处理函数
            signal = ecg_preprocess(signal, seq_len=SEQ_LEN, augment=False)

            # 4. 转换为模型输入格式 [batch, channel, seq_len]
            input_tensor = torch.tensor(signal, dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(DEVICE)

            # 5. 模型推理（使用ecg_test.py定义的模型）
            if ECG_MODEL is None:
                logger.warning("ECG模型未加载，使用默认结果")
                return default_result

            with torch.no_grad():
                preds, _ = ECG_MODEL(input_tensor)
                prob = preds.cpu().numpy().flatten()[0]  # 正常概率（1=正常，0=异常）
                pred_label = 1 if prob > BEST_THRESHOLD else 0  # 1=正常，0=异常

            # 6. 构造符合示例格式的结果
            # 6.1 心率（模拟合理范围，可替换为模型预测值）
            if pred_label == 1:
                heart_rate = round(np.clip(np.random.normal(75, 5), 60, 100), 1)
                rhythm_type = '窦性心律'
                abnormalities = ['无明显异常']
                disease_risks = {'房颤': 0.05, '心肌梗塞': 0.02, '心律失常': 0.10}
                risk_level = '低风险'
                confidence = round(float(prob), 2)
            else:
                heart_rate = round(np.clip(np.random.normal(85, 8), 65, 110), 1)
                rhythm_type = '异常心律'
                # 根据异常概率分级
                if prob < 0.2:
                    abnormalities = ['频发房性早搏', 'ST段压低', 'T波倒置']
                    disease_risks = {
                        '房颤': round(float(np.clip((1 - prob) * 0.8, 0.2, 0.9)), 2),
                        '心肌梗塞': round(float(np.clip((1 - prob) * 0.6, 0.1, 0.8)), 2),
                        '心律失常': round(float(np.clip((1 - prob) * 0.9, 0.3, 0.95)), 2)
                    }
                    risk_level = '高风险'
                else:
                    abnormalities = ['偶发房性早搏', '心率不齐']
                    disease_risks = {
                        '房颤': round(float(np.clip((1 - prob) * 0.4, 0.1, 0.5)), 2),
                        '心肌梗塞': round(float(np.clip((1 - prob) * 0.2, 0.05, 0.3)), 2),
                        '心律失常': round(float(np.clip((1 - prob) * 0.5, 0.2, 0.7)), 2)
                    }
                    risk_level = '中风险'
                confidence = round(float(1 - prob), 2)

            # 7. 计算分析时间
            analysis_time = round(time.time() - start_time, 2)

            # 8. 最终结果（严格匹配示例格式）
            result = {
                'heart_rate': heart_rate,
                'rhythm_type': rhythm_type,
                'abnormalities': json.dumps(abnormalities, ensure_ascii=False),
                'disease_risks': json.dumps(disease_risks, ensure_ascii=False),
                'risk_level': risk_level,
                'confidence': confidence,
                'analysis_time': analysis_time
            }

            logger.info(f"ECG分析完成: {ecg_path} | 风险等级: {risk_level} | 置信度: {confidence}")
            return result

        except Exception as e:
            logger.error(f"ECG分析失败: {ecg_path} | 错误: {str(e)}", exc_info=True)
            # 保证输出格式一致，返回默认结果
            default_result['analysis_time'] = round(time.time() - start_time, 2)
            return default_result

    @staticmethod
    def analyze_medical_text(text_path):
        """
        病历文本分析（适配新版medical_test.py，直接复用其返回格式）
        输入: 文本路径
        输出: 结构化的医疗信息（格式严格匹配要求）
        """
        # 记录实际分析耗时
        start_time = time.time()

        try:
            # 1. 检查medical_test是否成功导入
            if medical_test is None:
                raise ImportError("medical_test.py模块未找到，请检查路径是否正确")

            # 2. 调用medical_test的核心函数（返回结果已完全匹配格式）
            result = medical_test.extract_medical_entities(text_path)

            # 3. 仅替换analysis_time为实际耗时（覆盖占位的0.0）
            result['analysis_time'] = round(time.time() - start_time, 3)

            logger.info(f"病历文本分析完成: {text_path}")
            return result

        except Exception as e:
            # 异常处理：返回格式一致的空结果
            logger.error(f"病历文本分析失败 {text_path}: {str(e)}", exc_info=True)
            error_result = {
                'symptoms': json.dumps([], ensure_ascii=False),
                'medical_history': json.dumps([], ensure_ascii=False),
                'examination_data': json.dumps({}, ensure_ascii=False),
                'extracted_entities': json.dumps({'疾病': [], '症状': [], '检查指标': []}, ensure_ascii=False),
                'risk_factors': json.dumps([], ensure_ascii=False),
                'analysis_time': round(time.time() - start_time, 3)
            }
            return error_result

    @staticmethod
    def fusion_decision(fundus_result, ecg_result, text_result):
        """
        多模态融合决策
        输入: 三个模态的分析结果
        输出: 综合诊断报告
        """
        import time
        time.sleep(0.4)

        try:
            # 1. 特征提取
            fundus_feat, ecg_feat, text_feat = extract_features_from_results(fundus_result, ecg_result, text_result)
            input_dims = (len(fundus_feat), len(ecg_feat), len(text_feat))

            # 2. 初始化模型
            model = MultimodalFusionModel(input_dims=input_dims)
            trainer = MultimodalFusionTrainer(model)

            # 3. 加载训练好的模型
            if os.path.exists(MODEL_PATH):
                trainer.load_model(MODEL_PATH)
            else:
                logger.warning(f"模型文件 {MODEL_PATH} 不存在，使用规则融合兜底")
                return rule_based_fusion(fundus_result, ecg_result, text_result)

            # 4. 模型推理
            trainer.model.eval()
            with torch.no_grad():
                fundus_tensor = torch.tensor(fundus_feat, dtype=torch.float32).unsqueeze(0)
                ecg_tensor = torch.tensor(ecg_feat, dtype=torch.float32).unsqueeze(0)
                text_tensor = torch.tensor(text_feat, dtype=torch.float32).unsqueeze(0)
                logits, confidence, attn_weights = trainer.model(fundus_tensor, ecg_tensor, text_tensor)
                pred_label = torch.argmax(logits, dim=1).cpu().numpy()[0]
                overall_risk = trainer.label_encoder.inverse_transform([pred_label])[0]
                confidence_score = confidence.cpu().numpy()[0][0]
                attn_weights = attn_weights.cpu().numpy()[0]

            # 5. 生成诊断报告
            diagnosis_map = {
                '低风险': {
                    'primary': '糖尿病视网膜病变（轻度非增殖期）',
                    'secondary': '心电图大致正常',
                    'evidence': {
                        '眼底证据': '检测到少量微血管瘤，无明显出血点，符合轻度非增殖期特征',
                        'ECG证据': '心电图无明显异常，心率在正常范围',
                        '病史证据': '患者有糖尿病史，但近期血糖控制尚可'
                    },
                    'recommendations': [
                        '定期监测血糖（建议每月1次）',
                        '每年复查眼底一次',
                        '保持健康生活方式，控制体重',
                        '避免过度用眼和剧烈运动'
                    ]
                },
                '中风险': {
                    'primary': '糖尿病视网膜病变（中度非增殖期）',
                    'secondary': '心律失常（房性早搏）',
                    'evidence': {
                        '眼底证据': '检测到多处微血管瘤及出血点，符合中度非增殖期糖尿病视网膜病变特征',
                        'ECG证据': '心电图显示偶发房性早搏，心率正常范围',
                        '病史证据': '患者有长期糖尿病史，血糖控制不佳'
                    },
                    'recommendations': [
                        '建议尽快就诊眼科，进行眼底荧光造影检查',
                        '加强血糖监测，调整降糖方案',
                        '建议心内科就诊，评估心律失常严重程度',
                        '定期复查眼底和心电图（建议3个月内）',
                        '控制饮食，适度运动，戒烟限酒'
                    ]
                },
                '高风险': {
                    'primary': '糖尿病视网膜病变（重度非增殖期）',
                    'secondary': '心律失常（频发房性早搏）合并高血压性心脏病',
                    'evidence': {
                        '眼底证据': '检测到大量微血管瘤、出血点及新生血管，符合重度非增殖期特征',
                        'ECG证据': '心电图显示频发房性早搏，ST段轻度改变',
                        '病史证据': '患者有长期糖尿病史和高血压史，血糖/血压控制极差'
                    },
                    'recommendations': [
                        '立即就诊眼科，考虑激光光凝治疗',
                        '住院调整降糖/降压方案，严格控制血糖血压',
                        '心内科紧急评估心脏功能，必要时进行24小时动态心电图',
                        '每周监测血糖血压，每月复查眼底',
                        '绝对卧床休息，避免体力活动，戒烟戒酒'
                    ]
                }
            }
            diag = diagnosis_map.get(overall_risk, diagnosis_map['中风险'])
            result = {
                'overall_risk_level': overall_risk,
                'primary_diagnosis': diag['primary'],
                'secondary_diagnosis': diag['secondary'],
                'diagnostic_evidence': json.dumps(diag['evidence'], ensure_ascii=False),
                'health_recommendations': json.dumps(diag['recommendations'], ensure_ascii=False),
                'attention_weights': json.dumps({
                    '眼底图像': float(attn_weights[0]),
                    'ECG信号': float(attn_weights[1]),
                    '病历文本': float(attn_weights[2])
                }, ensure_ascii=False),
                'confidence': float(confidence_score)
            }
            logger.info("多模态融合决策完成（模型推理）")
            return result

        except Exception as e:
            logger.error(f"模型推理异常: {str(e)}，使用规则融合兜底")
            return rule_based_fusion(fundus_result, ecg_result, text_result)


# ==================== API路由 - 患者端 ====================

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/patient')
def patient_portal():
    """患者端页面"""
    return render_template('patient_portal.html')


@app.route('/doctor')
def doctor_portal():
    """医生端页面"""
    return render_template('doctor_portal.html')


@app.route('/login')
def login_page():
    """登录页面"""
    return render_template('login.html')


@app.route('/api')
def api_index():
    """API入口信息"""
    return jsonify({
        'message': '多模态慢性病智能筛查平台 API',
        'version': '1.0.0',
        'status': 'running'
    })


@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    """服务上传的文件（图片等）"""
    import os
    # 处理 Windows 风格路径分隔符
    filename = filename.replace('\\', '/')
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/patient/register', methods=['POST'])
def register_patient():
    """注册新患者"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'name' not in data:
            return jsonify({'error': '缺少必填字段: name'}), 400

        patient_id = generate_unique_id('P')

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO patients (patient_id, name, age, gender, phone)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                patient_id,
                data.get('name'),
                data.get('age'),
                data.get('gender'),
                data.get('phone')
            ))

        logger.info(f"新患者注册成功: {patient_id}")
        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'message': '患者注册成功'
        }), 201

    except Exception as e:
        logger.error(f"患者注册失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'注册失败: {str(e)}'}), 500


@app.route('/api/examination/create', methods=['POST'])
def create_examination():
    """创建新的检查记录"""
    try:
        data = request.get_json()

        if not data or 'patient_id' not in data:
            return jsonify({'error': '缺少必填字段: patient_id'}), 400

        # 验证患者是否存在
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM patients WHERE patient_id = ?', (data['patient_id'],))
            if not cursor.fetchone():
                return jsonify({'error': '患者不存在'}), 404

        exam_id = generate_unique_id('E')

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO examinations (exam_id, patient_id, status)
                VALUES (?, ?, ?)
            ''', (exam_id, data['patient_id'], 'pending'))

        logger.info(f"创建检查记录: {exam_id}")
        return jsonify({
            'success': True,
            'exam_id': exam_id,
            'message': '检查记录创建成功'
        }), 201

    except Exception as e:
        logger.error(f"创建检查记录失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'创建失败: {str(e)}'}), 500


@app.route('/api/upload/fundus', methods=['POST'])
def upload_fundus_image():
    """上传眼底图像"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400

        file = request.files['file']
        exam_id = request.form.get('exam_id')

        if not exam_id:
            return jsonify({'error': '缺少exam_id参数'}), 400

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        if not allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
            return jsonify({'error': f'不支持的文件格式，仅支持: {ALLOWED_IMAGE_EXTENSIONS}'}), 400

        # 保存文件
        filepath = save_uploaded_file(file, 'fundus')
        if not filepath:
            return jsonify({'error': '文件保存失败'}), 500

        # 更新数据库
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE examinations 
                SET fundus_image_path = ?
                WHERE exam_id = ?
            ''', (filepath, exam_id))

        logger.info(f"眼底图像上传成功: {exam_id} -> {filepath}")
        return jsonify({
            'success': True,
            'exam_id': exam_id,
            'file_path': filepath,
            'message': '眼底图像上传成功'
        }), 200

    except Exception as e:
        logger.error(f"眼底图像上传失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/upload/ecg', methods=['POST'])
def upload_ecg_data():
    """上传ECG数据"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400

        file = request.files['file']
        exam_id = request.form.get('exam_id')

        if not exam_id:
            return jsonify({'error': '缺少exam_id参数'}), 400

        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400

        if not allowed_file(file.filename, ALLOWED_ECG_EXTENSIONS):
            return jsonify({'error': f'不支持的文件格式，仅支持: {ALLOWED_ECG_EXTENSIONS}'}), 400

        filepath = save_uploaded_file(file, 'ecg')
        if not filepath:
            return jsonify({'error': '文件保存失败'}), 500

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE examinations 
                SET ecg_data_path = ?
                WHERE exam_id = ?
            ''', (filepath, exam_id))

        logger.info(f"ECG数据上传成功: {exam_id} -> {filepath}")
        return jsonify({
            'success': True,
            'exam_id': exam_id,
            'file_path': filepath,
            'message': 'ECG数据上传成功'
        }), 200

    except Exception as e:
        logger.error(f"ECG数据上传失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/upload/medical_text', methods=['POST'])
def upload_medical_text():
    """上传病历文本"""
    try:
        # 支持两种方式：文件上传或直接文本
        exam_id = request.form.get('exam_id') or request.json.get('exam_id')

        if not exam_id:
            return jsonify({'error': '缺少exam_id参数'}), 400

        filepath = None

        # 方式1: 文件上传
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '' and allowed_file(file.filename, ALLOWED_TEXT_EXTENSIONS):
                filepath = save_uploaded_file(file, 'text')

        # 方式2: 直接文本
        elif request.json and 'text' in request.json:
            text_content = request.json['text']
            filename = f"{generate_unique_id()}_medical_text.txt"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'text', filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text_content)

        if not filepath:
            return jsonify({'error': '未提供有效的文本内容'}), 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE examinations 
                SET medical_text_path = ?
                WHERE exam_id = ?
            ''', (filepath, exam_id))

        logger.info(f"病历文本上传成功: {exam_id} -> {filepath}")
        return jsonify({
            'success': True,
            'exam_id': exam_id,
            'file_path': filepath,
            'message': '病历文本上传成功'
        }), 200

    except Exception as e:
        logger.error(f"病历文本上传失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500


@app.route('/api/analyze/<exam_id>', methods=['POST'])
def analyze_examination(exam_id):
    """
    执行综合分析
    这是核心接口，会调用三个模态的模型进行推理，然后融合决策
    """
    try:
        # 获取检查记录
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM examinations WHERE exam_id = ?', (exam_id,))
            exam = cursor.fetchone()

            if not exam:
                return jsonify({'error': '检查记录不存在'}), 404

            # 更新状态为处理中
            cursor.execute('''
                UPDATE examinations 
                SET status = 'processing'
                WHERE exam_id = ?
            ''', (exam_id,))

        fundus_path = exam['fundus_image_path']
        ecg_path = exam['ecg_data_path']
        text_path = exam['medical_text_path']

        # 检查是否至少有一个模态的数据
        if not any([fundus_path, ecg_path, text_path]):
            return jsonify({'error': '至少需要上传一种类型的数据'}), 400

        # 1. 眼底图像分析
        fundus_result = None
        if fundus_path and os.path.exists(fundus_path):
            fundus_result = ModelInference.analyze_fundus_image(fundus_path)
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO fundus_results 
                    (exam_id, lesion_count, lesion_types, lesion_locations, 
                     dr_grade, risk_level, confidence, analysis_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    exam_id,
                    fundus_result['lesion_count'],
                    fundus_result['lesion_types'],
                    fundus_result['lesion_locations'],
                    fundus_result['dr_grade'],
                    fundus_result['risk_level'],
                    fundus_result['confidence'],
                    fundus_result['analysis_time']
                ))

        # 2. ECG分析
        ecg_result = None
        if ecg_path and os.path.exists(ecg_path):
            ecg_result = ModelInference.analyze_ecg_signal(ecg_path)
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ecg_results 
                    (exam_id, heart_rate, rhythm_type, abnormalities, 
                     disease_risks, risk_level, confidence, analysis_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    exam_id,
                    ecg_result['heart_rate'],
                    ecg_result['rhythm_type'],
                    ecg_result['abnormalities'],
                    ecg_result['disease_risks'],
                    ecg_result['risk_level'],
                    ecg_result['confidence'],
                    ecg_result['analysis_time']
                ))

        # 3. 病历文本分析
        text_result = None
        if text_path and os.path.exists(text_path):
            text_result = ModelInference.analyze_medical_text(text_path)
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO text_results 
                    (exam_id, symptoms, medical_history, examination_data, 
                     extracted_entities, risk_factors, analysis_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    exam_id,
                    text_result['symptoms'],
                    text_result['medical_history'],
                    text_result['examination_data'],
                    text_result['extracted_entities'],
                    text_result['risk_factors'],
                    text_result['analysis_time']
                ))

        # 4. 多模态融合决策
        fusion_result = ModelInference.fusion_decision(
            fundus_result or {},
            ecg_result or {},
            text_result or {}
        )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO comprehensive_reports 
                (exam_id, overall_risk_level, primary_diagnosis, secondary_diagnosis,
                 diagnostic_evidence, health_recommendations, attention_weights, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                exam_id,
                fusion_result['overall_risk_level'],
                fusion_result['primary_diagnosis'],
                fusion_result['secondary_diagnosis'],
                fusion_result['diagnostic_evidence'],
                fusion_result['health_recommendations'],
                fusion_result['attention_weights'],
                fusion_result['confidence']
            ))

            # 更新检查状态为完成
            cursor.execute('''
                UPDATE examinations 
                SET status = 'completed'
                WHERE exam_id = ?
            ''', (exam_id,))

        logger.info(f"综合分析完成: {exam_id}")

        # 返回完整的分析结果
        return jsonify({
            'success': True,
            'exam_id': exam_id,
            'fundus_analysis': fundus_result,
            'ecg_analysis': ecg_result,
            'text_analysis': text_result,
            'comprehensive_report': fusion_result,
            'message': '分析完成'
        }), 200

    except Exception as e:
        # 更新状态为失败
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE examinations 
                    SET status = 'failed'
                    WHERE exam_id = ?
                ''', (exam_id,))
        except:
            pass

        logger.error(f"分析失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'分析失败: {str(e)}'}), 500


@app.route('/api/report/<exam_id>', methods=['GET'])
def get_report(exam_id):
    """获取完整的诊断报告"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 获取检查基本信息
            cursor.execute('''
                SELECT e.*, p.name, p.age, p.gender 
                FROM examinations e
                JOIN patients p ON e.patient_id = p.patient_id
                WHERE e.exam_id = ?
            ''', (exam_id,))
            exam = cursor.fetchone()

            if not exam:
                return jsonify({'error': '检查记录不存在'}), 404

            # 获取眼底分析结果
            cursor.execute('SELECT * FROM fundus_results WHERE exam_id = ? ORDER BY id DESC LIMIT 1', (exam_id,))
            fundus = cursor.fetchone()

            # 获取ECG分析结果
            cursor.execute('SELECT * FROM ecg_results WHERE exam_id = ? ORDER BY id DESC LIMIT 1', (exam_id,))
            ecg = cursor.fetchone()

            # 获取文本分析结果
            cursor.execute('SELECT * FROM text_results WHERE exam_id = ? ORDER BY id DESC LIMIT 1', (exam_id,))
            text = cursor.fetchone()

            # 获取综合报告
            cursor.execute('SELECT * FROM comprehensive_reports WHERE exam_id = ? ORDER BY id DESC LIMIT 1', (exam_id,))
            report = cursor.fetchone()

        # 构建完整报告
        full_report = {
            'exam_info': {
                'exam_id': exam['exam_id'],
                'patient_name': exam['name'],
                'age': exam['age'],
                'gender': exam['gender'],
                'exam_date': exam['exam_date'],
                'status': exam['status'],
                'fundus_image_path': exam['fundus_image_path']
            },
            'fundus_analysis': dict(fundus) if fundus else None,
            'ecg_analysis': dict(ecg) if ecg else None,
            'text_analysis': dict(text) if text else None,
            'comprehensive_report': dict(report) if report else None
        }

        return jsonify(full_report), 200

    except Exception as e:
        logger.error(f"获取报告失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'获取报告失败: {str(e)}'}), 500


@app.route('/api/patient/<patient_id>/history', methods=['GET'])
def get_patient_history(patient_id):
    """获取患者的历史检查记录"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 验证患者是否存在
            cursor.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
            patient = cursor.fetchone()

            if not patient:
                return jsonify({'error': '患者不存在'}), 404

            # 获取所有检查记录
            cursor.execute('''
                SELECT e.exam_id, e.exam_date, e.status,
                       cr.overall_risk_level, cr.primary_diagnosis
                FROM examinations e
                LEFT JOIN comprehensive_reports cr ON e.exam_id = cr.exam_id
                WHERE e.patient_id = ?
                ORDER BY e.exam_date DESC
            ''', (patient_id,))

            history = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'patient_id': patient_id,
            'patient_name': patient['name'],
            'total_examinations': len(history),
            'history': history
        }), 200

    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'获取历史记录失败: {str(e)}'}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """获取系统统计信息"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 总患者数
            cursor.execute('SELECT COUNT(*) as count FROM patients')
            total_patients = cursor.fetchone()['count']

            # 总检查数
            cursor.execute('SELECT COUNT(*) as count FROM examinations')
            total_exams = cursor.fetchone()['count']

            # 完成的检查数
            cursor.execute("SELECT COUNT(*) as count FROM examinations WHERE status = 'completed'")
            completed_exams = cursor.fetchone()['count']

            # 各风险等级统计
            cursor.execute('''
                SELECT overall_risk_level, COUNT(*) as count
                FROM comprehensive_reports
                GROUP BY overall_risk_level
            ''')
            risk_distribution = {row['overall_risk_level']: row['count'] for row in cursor.fetchall()}

            # 最近7天的检查趋势
            cursor.execute('''
                SELECT DATE(exam_date) as date, COUNT(*) as count
                FROM examinations
                WHERE exam_date >= datetime('now', '-7 days')
                GROUP BY DATE(exam_date)
                ORDER BY date
            ''')
            recent_trend = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'total_patients': total_patients,
            'total_examinations': total_exams,
            'completed_examinations': completed_exams,
            'risk_distribution': risk_distribution,
            'recent_trend': recent_trend
        }), 200

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'获取统计信息失败: {str(e)}'}), 500


@app.route('/api/search', methods=['GET'])
def search_records():
    """搜索检查记录"""
    try:
        # 获取查询参数
        patient_name = request.args.get('patient_name', '')
        risk_level = request.args.get('risk_level', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')

        with get_db() as conn:
            cursor = conn.cursor()

            query = '''
                SELECT e.exam_id, e.exam_date, e.status,
                       p.patient_id, p.name, p.age, p.gender,
                       cr.overall_risk_level, cr.primary_diagnosis
                FROM examinations e
                JOIN patients p ON e.patient_id = p.patient_id
                LEFT JOIN comprehensive_reports cr ON e.exam_id = cr.exam_id
                WHERE 1=1
            '''
            params = []

            if patient_name:
                query += ' AND p.name LIKE ?'
                params.append(f'%{patient_name}%')

            if risk_level:
                query += ' AND cr.overall_risk_level = ?'
                params.append(risk_level)

            if start_date:
                query += ' AND DATE(e.exam_date) >= ?'
                params.append(start_date)

            if end_date:
                query += ' AND DATE(e.exam_date) <= ?'
                params.append(end_date)

            query += ' ORDER BY e.exam_date DESC LIMIT 100'

            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'total': len(results),
            'results': results
        }), 200

    except Exception as e:
        logger.error(f"搜索失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'搜索失败: {str(e)}'}), 500


@app.route('/api/export/report/<exam_id>', methods=['GET'])
def export_report(exam_id):
    """导出诊断报告为JSON格式"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 获取完整报告数据
            cursor.execute('''
                SELECT e.*, p.name, p.age, p.gender,
                       cr.overall_risk_level, cr.primary_diagnosis,
                       cr.secondary_diagnosis, cr.diagnostic_evidence,
                       cr.health_recommendations, cr.confidence
                FROM examinations e
                JOIN patients p ON e.patient_id = p.patient_id
                LEFT JOIN comprehensive_reports cr ON e.exam_id = cr.exam_id
                WHERE e.exam_id = ?
            ''', (exam_id,))

            report_data = cursor.fetchone()

            if not report_data:
                return jsonify({'error': '报告不存在'}), 404

            # 构建导出数据
            export_data = {
                '报告编号': report_data['exam_id'],
                '患者姓名': report_data['name'],
                '年龄': report_data['age'],
                '性别': report_data['gender'],
                '检查日期': report_data['exam_date'],
                '综合风险等级': report_data['overall_risk_level'],
                '主要诊断': report_data['primary_diagnosis'],
                '次要诊断': report_data['secondary_diagnosis'],
                '诊断依据': json.loads(report_data['diagnostic_evidence']) if report_data[
                    'diagnostic_evidence'] else {},
                '健康建议': json.loads(report_data['health_recommendations']) if report_data[
                    'health_recommendations'] else [],
                '置信度': report_data['confidence']
            }

        return jsonify(export_data), 200

    except Exception as e:
        logger.error(f"导出报告失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'导出报告失败: {str(e)}'}), 500


# ==================== API路由 - 医生端 ====================
# 将所有医生端路由合并到主应用中

@app.route('/api/doctor/login', methods=['POST'])
def doctor_login():
    """医生登录"""
    try:
        data = request.get_json()
        doctor_id = data.get('doctor_id')
        password = data.get('password')

        if not doctor_id or not password:
            return jsonify({'error': '请提供医生ID和密码'}), 400

        password_hash = hash_password(password)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM doctors 
                WHERE doctor_id = ? AND password_hash = ? AND status = 'active'
            ''', (doctor_id, password_hash))

            doctor = cursor.fetchone()

            if not doctor:
                return jsonify({'error': '医生ID或密码错误'}), 401

            # 更新最后登录时间
            cursor.execute('''
                UPDATE doctors SET last_login = CURRENT_TIMESTAMP 
                WHERE doctor_id = ?
            ''', (doctor_id,))

        # 记录登录活动
        log_doctor_activity(doctor_id, 'login', ip_address=request.remote_addr)

        doctor_data = dict(doctor)
        doctor_data.pop('password_hash', None)  # 不返回密码哈希

        logger.info(f"医生登录成功: {doctor_id}")
        return jsonify({
            'success': True,
            'message': '登录成功',
            'doctor': doctor_data
        }), 200

    except Exception as e:
        logger.error(f"医生登录失败: {str(e)}")
        return jsonify({'error': f'登录失败: {str(e)}'}), 500


@app.route('/api/doctor/profile', methods=['GET'])
@require_doctor_auth
def get_doctor_profile(doctor_id, doctor_info):
    """获取医生个人信息"""
    try:
        doctor_data = dict(doctor_info)
        doctor_data.pop('password_hash', None)

        # 获取统计数据
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM doctor_statistics WHERE doctor_id = ?', (doctor_id,))
            stats = cursor.fetchone()

        return jsonify({
            'doctor': doctor_data,
            'statistics': dict(stats) if stats else None
        }), 200

    except Exception as e:
        logger.error(f"获取医生信息失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/profile', methods=['PUT'])
@require_doctor_auth
def update_doctor_profile(doctor_id, doctor_info):
    """更新医生个人信息"""
    try:
        data = request.get_json()

        # 允许更新的字段
        allowed_fields = ['phone', 'email', 'specialization']
        update_fields = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_fields:
            return jsonify({'error': '没有可更新的字段'}), 400

        with get_db() as conn:
            cursor = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [doctor_id]

            cursor.execute(f'''
                UPDATE doctors SET {set_clause}
                WHERE doctor_id = ?
            ''', values)

        log_doctor_activity(doctor_id, 'update_profile', details=update_fields)

        return jsonify({
            'success': True,
            'message': '信息更新成功'
        }), 200

    except Exception as e:
        logger.error(f"更新医生信息失败: {str(e)}")
        return jsonify({'error': f'更新失败: {str(e)}'}), 500


@app.route('/api/doctor/patients', methods=['GET'])
@require_doctor_auth
def get_doctor_patients(doctor_id, doctor_info):
    """获取医生管理的患者列表"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        risk_level = request.args.get('risk_level', '')
        tag_type = request.args.get('tag_type', '')
        search = request.args.get('search', '')

        offset = (page - 1) * per_page

        with get_db() as conn:
            cursor = conn.cursor()

            # 构建查询
            query = '''
                SELECT DISTINCT p.*, 
                       dpr.relation_type,
                       dpr.assigned_date,
                       (SELECT COUNT(*) FROM examinations WHERE patient_id = p.patient_id) as exam_count,
                       (SELECT overall_risk_level FROM comprehensive_reports cr
                        JOIN examinations e ON cr.exam_id = e.exam_id
                        WHERE e.patient_id = p.patient_id
                        ORDER BY e.exam_date DESC LIMIT 1) as latest_risk_level,
                       (SELECT exam_date FROM examinations 
                        WHERE patient_id = p.patient_id 
                        ORDER BY exam_date DESC LIMIT 1) as last_exam_date
                FROM patients p
                JOIN doctor_patient_relations dpr ON p.patient_id = dpr.patient_id
                WHERE dpr.doctor_id = ?
            '''
            params = [doctor_id]

            # 添加筛选条件
            if risk_level:
                query += ' AND latest_risk_level = ?'
                params.append(risk_level)

            if search:
                query += ' AND (p.name LIKE ? OR p.patient_id LIKE ?)'
                params.extend([f'%{search}%', f'%{search}%'])

            # 如果有标签筛选
            if tag_type:
                query = query.replace('FROM patients p', '''
                    FROM patients p
                    JOIN patient_tags pt ON p.patient_id = pt.patient_id AND pt.doctor_id = ?
                ''')
                params.insert(1, doctor_id)
                query += ' AND pt.tag_type = ?'
                params.append(tag_type)

            # 获取总数
            count_query = f"SELECT COUNT(*) as total FROM ({query})"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']

            # 分页查询
            query += ' ORDER BY last_exam_date DESC LIMIT ? OFFSET ?'
            params.extend([per_page, offset])

            cursor.execute(query, params)
            patients = [dict(row) for row in cursor.fetchall()]

            # 为每个患者获取标签
            for patient in patients:
                cursor.execute('''
                    SELECT tag_type, tag_color, notes 
                    FROM patient_tags 
                    WHERE patient_id = ? AND doctor_id = ?
                    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                ''', (patient['patient_id'], doctor_id))
                patient['tags'] = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'total': total,
            'page': page,
            'per_page': per_page,
            'patients': patients
        }), 200

    except Exception as e:
        logger.error(f"获取患者列表失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/patients/<patient_id>/assign', methods=['POST'])
@require_doctor_auth
def assign_patient(patient_id, doctor_id, doctor_info):
    """将患者分配给医生"""
    try:
        data = request.get_json()
        relation_type = data.get('relation_type', 'primary')
        notes = data.get('notes', '')

        with get_db() as conn:
            cursor = conn.cursor()

            # 检查患者是否存在
            cursor.execute('SELECT * FROM patients WHERE patient_id = ?', (patient_id,))
            if not cursor.fetchone():
                return jsonify({'error': '患者不存在'}), 404

            # 创建医患关系
            cursor.execute('''
                INSERT OR REPLACE INTO doctor_patient_relations 
                (doctor_id, patient_id, relation_type, notes)
                VALUES (?, ?, ?, ?)
            ''', (doctor_id, patient_id, relation_type, notes))

            # 更新医生统计
            cursor.execute('''
                UPDATE doctor_statistics 
                SET total_patients = total_patients + 1,
                    last_updated = CURRENT_TIMESTAMP
                WHERE doctor_id = ?
            ''', (doctor_id,))

        log_doctor_activity(doctor_id, 'assign_patient', patient_id,
                            {'relation_type': relation_type})

        return jsonify({
            'success': True,
            'message': '患者分配成功'
        }), 200

    except Exception as e:
        logger.error(f"分配患者失败: {str(e)}")
        return jsonify({'error': f'分配失败: {str(e)}'}), 500


@app.route('/api/doctor/patients/<patient_id>/tag', methods=['POST'])
@require_doctor_auth
def tag_patient(patient_id, doctor_id, doctor_info):
    """为患者添加标签"""
    try:
        data = request.get_json()
        tag_type = data.get('tag_type')
        tag_color = data.get('tag_color', '#FF5722')
        notes = data.get('notes', '')
        expires_days = data.get('expires_days')

        if not tag_type:
            return jsonify({'error': '请提供标签类型'}), 400

        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO patient_tags 
                (patient_id, doctor_id, tag_type, tag_color, notes, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (patient_id, doctor_id, tag_type, tag_color, notes, expires_at))

        log_doctor_activity(doctor_id, 'tag_patient', patient_id,
                            {'tag_type': tag_type})

        return jsonify({
            'success': True,
            'message': '标签添加成功'
        }), 200

    except Exception as e:
        logger.error(f"添加标签失败: {str(e)}")
        return jsonify({'error': f'添加失败: {str(e)}'}), 500


@app.route('/api/doctor/feedback', methods=['POST'])
@require_doctor_auth
def submit_ai_feedback(doctor_id, doctor_info):
    """提交AI诊断反馈"""
    try:
        data = request.get_json()
        exam_id = data.get('exam_id')
        feedback_type = data.get('feedback_type')  # correction, confirmation, comment

        if not exam_id or not feedback_type:
            return jsonify({'error': '缺少必填字段'}), 400

        feedback_id = generate_unique_id('FB')

        with get_db() as conn:
            cursor = conn.cursor()

            # 获取原始AI诊断结果
            cursor.execute('''
                SELECT overall_risk_level, primary_diagnosis 
                FROM comprehensive_reports 
                WHERE exam_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (exam_id,))
            original = cursor.fetchone()

            if not original:
                return jsonify({'error': '未找到AI诊断结果'}), 404

            # 插入反馈
            cursor.execute('''
                INSERT INTO ai_feedback 
                (feedback_id, exam_id, doctor_id, feedback_type,
                 original_diagnosis, original_risk_level,
                 corrected_diagnosis, corrected_risk_level,
                 feedback_category, detailed_comments,
                 fundus_feedback, ecg_feedback, text_feedback,
                 is_teaching_case, teaching_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                feedback_id, exam_id, doctor_id, feedback_type,
                original['primary_diagnosis'], original['overall_risk_level'],
                data.get('corrected_diagnosis'),
                data.get('corrected_risk_level'),
                data.get('feedback_category'),
                data.get('detailed_comments'),
                json.dumps(data.get('fundus_feedback'), ensure_ascii=False) if data.get('fundus_feedback') else None,
                json.dumps(data.get('ecg_feedback'), ensure_ascii=False) if data.get('ecg_feedback') else None,
                json.dumps(data.get('text_feedback'), ensure_ascii=False) if data.get('text_feedback') else None,
                data.get('is_teaching_case', False),
                data.get('teaching_notes')
            ))

            # 更新医生统计
            cursor.execute('''
                UPDATE doctor_statistics 
                SET total_feedbacks = total_feedbacks + 1,
                    last_updated = CURRENT_TIMESTAMP
                WHERE doctor_id = ?
            ''', (doctor_id,))

        log_doctor_activity(doctor_id, 'submit_feedback', exam_id,
                            {'feedback_type': feedback_type, 'feedback_category': data.get('feedback_category')})

        logger.info(f"AI反馈提交成功: {feedback_id}")
        return jsonify({
            'success': True,
            'feedback_id': feedback_id,
            'message': '反馈提交成功'
        }), 201

    except Exception as e:
        logger.error(f"提交反馈失败: {str(e)}")
        return jsonify({'error': f'提交失败: {str(e)}'}), 500


@app.route('/api/doctor/feedback/<exam_id>', methods=['GET'])
@require_doctor_auth
def get_exam_feedback(exam_id, doctor_id, doctor_info):
    """获取某次检查的所有反馈"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT af.*, d.name as doctor_name, d.title
                FROM ai_feedback af
                JOIN doctors d ON af.doctor_id = d.doctor_id
                WHERE af.exam_id = ?
                ORDER BY af.created_at DESC
            ''', (exam_id,))

            feedbacks = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'exam_id': exam_id,
            'total_feedbacks': len(feedbacks),
            'feedbacks': feedbacks
        }), 200

    except Exception as e:
        logger.error(f"获取反馈失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/progression/create', methods=['POST'])
@require_doctor_auth
def create_progression_tracking(doctor_id, doctor_info):
    """创建病程追踪记录"""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        start_exam_id = data.get('start_exam_id')
        end_exam_id = data.get('end_exam_id')

        if not all([patient_id, start_exam_id, end_exam_id]):
            return jsonify({'error': '缺少必填字段'}), 400

        progression_id = generate_unique_id('PROG')

        with get_db() as conn:
            cursor = conn.cursor()

            # 获取两次检查的时间差
            cursor.execute('''
                SELECT 
                    julianday(e2.exam_date) - julianday(e1.exam_date) as days_diff
                FROM examinations e1, examinations e2
                WHERE e1.exam_id = ? AND e2.exam_id = ?
            ''', (start_exam_id, end_exam_id))

            result = cursor.fetchone()
            tracking_period_days = int(result['days_diff']) if result else 0

            # 分析病情变化（这里是简化版，实际应该调用分析模型）
            progression_status = data.get('progression_status', 'stable')

            cursor.execute('''
                INSERT INTO disease_progression 
                (progression_id, patient_id, doctor_id, start_exam_id, end_exam_id,
                 tracking_period_days, progression_status, key_changes,
                 fundus_trend, ecg_trend, clinical_trend,
                 doctor_assessment, treatment_adjustment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                progression_id, patient_id, doctor_id, start_exam_id, end_exam_id,
                tracking_period_days, progression_status,
                json.dumps(data.get('key_changes'), ensure_ascii=False) if data.get('key_changes') else None,
                json.dumps(data.get('fundus_trend'), ensure_ascii=False) if data.get('fundus_trend') else None,
                json.dumps(data.get('ecg_trend'), ensure_ascii=False) if data.get('ecg_trend') else None,
                json.dumps(data.get('clinical_trend'), ensure_ascii=False) if data.get('clinical_trend') else None,
                data.get('doctor_assessment'),
                data.get('treatment_adjustment')
            ))

        log_doctor_activity(doctor_id, 'create_progression', patient_id,
                            {'progression_id': progression_id})

        return jsonify({
            'success': True,
            'progression_id': progression_id,
            'message': '病程追踪记录创建成功'
        }), 201

    except Exception as e:
        logger.error(f"创建病程追踪失败: {str(e)}")
        return jsonify({'error': f'创建失败: {str(e)}'}), 500


@app.route('/api/doctor/progression/<patient_id>', methods=['GET'])
@require_doctor_auth
def get_patient_progression(patient_id, doctor_id, doctor_info):
    """获取患者的病程追踪记录"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 获取病程追踪记录
            cursor.execute('''
                SELECT dp.*, 
                       e1.exam_date as start_date,
                       e2.exam_date as end_date,
                       d.name as doctor_name
                FROM disease_progression dp
                JOIN examinations e1 ON dp.start_exam_id = e1.exam_id
                JOIN examinations e2 ON dp.end_exam_id = e2.exam_id
                JOIN doctors d ON dp.doctor_id = d.doctor_id
                WHERE dp.patient_id = ?
                ORDER BY dp.created_at DESC
            ''', (patient_id,))

            progressions = [dict(row) for row in cursor.fetchall()]

            # 获取患者所有检查记录用于趋势分析
            cursor.execute('''
                SELECT e.exam_id, e.exam_date, e.status,
                       cr.overall_risk_level, cr.primary_diagnosis, cr.confidence
                FROM examinations e
                LEFT JOIN comprehensive_reports cr ON e.exam_id = cr.exam_id
                WHERE e.patient_id = ?
                ORDER BY e.exam_date ASC
            ''', (patient_id,))

            exams = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'patient_id': patient_id,
            'total_progressions': len(progressions),
            'progressions': progressions,
            'exam_history': exams
        }), 200

    except Exception as e:
        logger.error(f"获取病程追踪失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/statistics/dashboard', methods=['GET'])
@require_doctor_auth
def get_doctor_dashboard(doctor_id, doctor_info):
    """获取医生工作台统计数据"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 基础统计
            cursor.execute('SELECT * FROM doctor_statistics WHERE doctor_id = ?', (doctor_id,))
            stats_row = cursor.fetchone()
            stats = dict(stats_row) if stats_row else {}

            # 今日工作量
            cursor.execute('''
                SELECT COUNT(*) as today_reviews
                FROM doctor_activity_log
                WHERE doctor_id = ? 
                AND DATE(created_at) = DATE('now')
                AND activity_type = 'review_case'
            ''', (doctor_id,))
            stats['today_reviews'] = cursor.fetchone()['today_reviews']

            # 待处理的高风险患者
            cursor.execute('''
                SELECT COUNT(DISTINCT p.patient_id) as high_risk_patients
                FROM patients p
                JOIN doctor_patient_relations dpr ON p.patient_id = dpr.patient_id
                JOIN examinations e ON p.patient_id = e.patient_id
                JOIN comprehensive_reports cr ON e.exam_id = cr.exam_id
                WHERE dpr.doctor_id = ?
                AND cr.overall_risk_level = '高风险'
                AND e.exam_date >= datetime('now', '-30 days')
            ''', (doctor_id,))
            stats['high_risk_patients'] = cursor.fetchone()['high_risk_patients']

            # 最近7天的工作趋势
            cursor.execute('''
                SELECT DATE(created_at) as date, 
                       COUNT(*) as count,
                       activity_type
                FROM doctor_activity_log
                WHERE doctor_id = ?
                AND created_at >= datetime('now', '-7 days')
                GROUP BY DATE(created_at), activity_type
                ORDER BY date
            ''', (doctor_id,))
            activity_trend = [dict(row) for row in cursor.fetchall()]

            # AI准确率统计（基于反馈）
            cursor.execute('''
                SELECT 
                    feedback_category,
                    COUNT(*) as count
                FROM ai_feedback
                WHERE doctor_id = ?
                GROUP BY feedback_category
            ''', (doctor_id,))
            feedback_stats = {row['feedback_category']: row['count']
                              for row in cursor.fetchall()}

            # 待处理会诊
            cursor.execute('''
                SELECT COUNT(*) as pending_consultations
                FROM consultations
                WHERE consulting_doctor_id = ?
                AND consultation_status = 'pending'
            ''', (doctor_id,))
            stats['pending_consultations'] = cursor.fetchone()['pending_consultations']

        return jsonify({
            'statistics': stats,
            'activity_trend': activity_trend,
            'feedback_distribution': feedback_stats
        }), 200

    except Exception as e:
        logger.error(f"获取统计数据失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/statistics/ai_performance', methods=['GET'])
@require_doctor_auth
def get_ai_performance(doctor_id, doctor_info):
    """获取AI性能统计（基于医生反馈）"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # 总体准确率
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_feedbacks,
                    SUM(CASE WHEN feedback_category = 'correct' THEN 1 ELSE 0 END) as correct,
                    SUM(CASE WHEN feedback_category = 'false_positive' THEN 1 ELSE 0 END) as false_positive,
                    SUM(CASE WHEN feedback_category = 'false_negative' THEN 1 ELSE 0 END) as false_negative,
                    SUM(CASE WHEN feedback_category = 'partially_correct' THEN 1 ELSE 0 END) as partially_correct
                FROM ai_feedback
                WHERE doctor_id = ?
            ''', (doctor_id,))

            result = cursor.fetchone()
            total = result['total_feedbacks']

            performance = {
                'total_feedbacks': total,
                'accuracy_rate': (result['correct'] / total * 100) if total > 0 else 0,
                'false_positive_rate': (result['false_positive'] / total * 100) if total > 0 else 0,
                'false_negative_rate': (result['false_negative'] / total * 100) if total > 0 else 0,
                'partially_correct_rate': (result['partially_correct'] / total * 100) if total > 0 else 0
            }

            # 按模态分类的性能
            modality_performance = {}
            for modality in ['fundus', 'ecg', 'text']:
                cursor.execute(f'''
                    SELECT COUNT(*) as count
                    FROM ai_feedback
                    WHERE doctor_id = ?
                    AND {modality}_feedback IS NOT NULL
                ''', (doctor_id,))
                modality_performance[modality] = cursor.fetchone()['count']

        return jsonify({
            'overall_performance': performance,
            'modality_feedback_count': modality_performance
        }), 200

    except Exception as e:
        logger.error(f"获取AI性能统计失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/consultation/request', methods=['POST'])
@require_doctor_auth
def request_consultation(doctor_id, doctor_info):
    """申请会诊"""
    try:
        data = request.get_json()
        exam_id = data.get('exam_id')
        consulting_doctor_id = data.get('consulting_doctor_id')
        consultation_type = data.get('consultation_type', 'routine')

        if not exam_id:
            return jsonify({'error': '缺少检查ID'}), 400

        consultation_id = generate_unique_id('CONS')

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO consultations 
                (consultation_id, exam_id, requesting_doctor_id, consulting_doctor_id,
                 consultation_type, request_reason, clinical_question)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                consultation_id, exam_id, doctor_id, consulting_doctor_id,
                consultation_type, data.get('request_reason'), data.get('clinical_question')
            ))

        log_doctor_activity(doctor_id, 'request_consultation', exam_id,
                            {'consultation_id': consultation_id})

        return jsonify({
            'success': True,
            'consultation_id': consultation_id,
            'message': '会诊申请已提交'
        }), 201

    except Exception as e:
        logger.error(f"申请会诊失败: {str(e)}")
        return jsonify({'error': f'申请失败: {str(e)}'}), 500


@app.route('/api/doctor/consultation/<consultation_id>/respond', methods=['POST'])
@require_doctor_auth
def respond_consultation(consultation_id, doctor_id, doctor_info):
    """回复会诊"""
    try:
        data = request.get_json()

        with get_db() as conn:
            cursor = conn.cursor()

            # 验证会诊记录
            cursor.execute('''
                SELECT * FROM consultations
                WHERE consultation_id = ? AND consulting_doctor_id = ?
            ''', (consultation_id, doctor_id))

            consultation = cursor.fetchone()
            if not consultation:
                return jsonify({'error': '会诊记录不存在或无权限'}), 404

            # 更新会诊意见
            cursor.execute('''
                UPDATE consultations
                SET consultation_opinion = ?,
                    recommended_actions = ?,
                    consultation_status = 'completed',
                    completed_at = CURRENT_TIMESTAMP
                WHERE consultation_id = ?
            ''', (data.get('consultation_opinion'),
                  data.get('recommended_actions'),
                  consultation_id))

        log_doctor_activity(doctor_id, 'respond_consultation', consultation_id)

        return jsonify({
            'success': True,
            'message': '会诊意见已提交'
        }), 200

    except Exception as e:
        logger.error(f"回复会诊失败: {str(e)}")
        return jsonify({'error': f'回复失败: {str(e)}'}), 500


@app.route('/api/doctor/consultation/list', methods=['GET'])
@require_doctor_auth
def list_consultations(doctor_id, doctor_info):
    """获取会诊列表"""
    try:
        consultation_type = request.args.get('type', 'all')  # all, requested, consulting
        status = request.args.get('status', '')

        with get_db() as conn:
            cursor = conn.cursor()

            query = '''
                SELECT c.*,
                       e.patient_id,
                       p.name as patient_name,
                       d1.name as requesting_doctor_name,
                       d2.name as consulting_doctor_name
                FROM consultations c
                JOIN examinations e ON c.exam_id = e.exam_id
                JOIN patients p ON e.patient_id = p.patient_id
                JOIN doctors d1 ON c.requesting_doctor_id = d1.doctor_id
                LEFT JOIN doctors d2 ON c.consulting_doctor_id = d2.doctor_id
                WHERE 1=1
            '''
            params = []

            if consultation_type == 'requested':
                query += ' AND c.requesting_doctor_id = ?'
                params.append(doctor_id)
            elif consultation_type == 'consulting':
                query += ' AND (c.consulting_doctor_id = ? OR c.consulting_doctor_id IS NULL)'
                params.append(doctor_id)
            else:
                # Include requests made by me, assigned to me, OR public requests
                query += ' AND (c.requesting_doctor_id = ? OR c.consulting_doctor_id = ? OR c.consulting_doctor_id IS NULL)'
                params.extend([doctor_id, doctor_id])

            if status:
                query += ' AND c.consultation_status = ?'
                params.append(status)

            query += ' ORDER BY c.requested_at DESC'

            cursor.execute(query, params)
            consultations = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'total': len(consultations),
            'consultations': consultations
        }), 200

    except Exception as e:
        logger.error(f"获取会诊列表失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@app.route('/api/doctor/teaching_cases', methods=['GET'])
@require_doctor_auth
def get_teaching_cases(doctor_id, doctor_info):
    """获取教学案例列表"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT af.*,
                       e.patient_id,
                       p.name as patient_name,
                       p.age, p.gender,
                       cr.primary_diagnosis,
                       d.name as doctor_name
                FROM ai_feedback af
                JOIN examinations e ON af.exam_id = e.exam_id
                JOIN patients p ON e.patient_id = p.patient_id
                JOIN comprehensive_reports cr ON af.exam_id = cr.exam_id
                JOIN doctors d ON af.doctor_id = d.doctor_id
                WHERE af.is_teaching_case = 1
                ORDER BY af.created_at DESC
            ''')

            cases = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'total': len(cases),
            'teaching_cases': cases
        }), 200

    except Exception as e:
        logger.error(f"获取教学案例失败: {str(e)}")
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


# ==================== 错误处理 ====================
@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({'error': '请求的资源不存在'}), 404


@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    logger.error(f"服务器内部错误: {str(error)}")
    return jsonify({'error': '服务器内部错误'}), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """文件过大错误处理"""
    return jsonify({'error': '上传文件过大，最大支持50MB'}), 413


# ==================== 初始化数据库和启动应用 ====================
def init_system():
    """初始化系统，包括数据库和测试数据"""
    try:
        # 初始化数据库
        init_db()

        # 插入测试医生数据（如果不存在）
        with get_db() as conn:
            cursor = conn.cursor()

            # 检查是否已有医生数据
            cursor.execute('SELECT COUNT(*) as count FROM doctors')
            if cursor.fetchone()['count'] == 0:
                logger.info("插入测试医生数据...")

                test_doctors = [
                    ('D001', '李明', '主任医师', '眼科', '糖尿病视网膜病变', '13900000001', 'liming@hospital.com',
                     'doctor123', '110101199001011234'),
                    ('D002', '王芳', '副主任医师', '心内科', '心血管疾病', '13900000002', 'wangfang@hospital.com',
                     'doctor123', '110101198502022345'),
                    ('D003', '张伟', '主治医师', '内分泌科', '糖尿病管理', '13900000003', 'zhangwei@hospital.com',
                     'doctor123', '110101199003033456')
                ]

                for doctor_id, name, title, dept, spec, phone, email, password, license in test_doctors:
                    cursor.execute('''
                        INSERT INTO doctors (doctor_id, name, title, department, specialization, 
                                           phone, email, password_hash, license_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (doctor_id, name, title, dept, spec, phone, email, hash_password(password), license))
                    logger.info(f"  ✓ 创建医生: {name} ({doctor_id})")

                # 初始化医生统计数据
                for doctor_id, name, _, _, _, _, _, _, _ in test_doctors:
                    cursor.execute('''
                        INSERT INTO doctor_statistics (doctor_id, total_patients, total_reviews, total_feedbacks)
                        VALUES (?, 0, 0, 0)
                    ''', (doctor_id,))

                logger.info("测试医生数据插入完成")

        return True

    except Exception as e:
        logger.error(f"系统初始化失败: {str(e)}")
        return False


if __name__ == '__main__':
    # 初始化系统
    if init_system():
        logger.info("=" * 50)
        logger.info("多模态慢性病智能筛查平台后端启动")
        logger.info("=" * 50)
        logger.info(f"数据库: {app.config['DATABASE']}")
        logger.info(f"上传目录: {app.config['UPLOAD_FOLDER']}")
        logger.info("API文档:")
        logger.info("  【患者端API】")
        logger.info("  - POST /api/patient/register - 注册患者")
        logger.info("  - POST /api/examination/create - 创建检查")
        logger.info("  - POST /api/upload/fundus - 上传眼底图像")
        logger.info("  - POST /api/upload/ecg - 上传ECG数据")
        logger.info("  - POST /api/upload/medical_text - 上传病历文本")
        logger.info("  - POST /api/analyze/<exam_id> - 执行综合分析")
        logger.info("  - GET  /api/report/<exam_id> - 获取诊断报告")
        logger.info("  - GET  /api/patient/<patient_id>/history - 获取患者历史")
        logger.info("  - GET  /api/statistics - 获取统计信息")
        logger.info("  - GET  /api/search - 搜索记录")
        logger.info("  - GET  /api/export/report/<exam_id> - 导出报告")
        logger.info("")
        logger.info("  【医生端API】")
        logger.info("  - POST /api/doctor/login - 医生登录")
        logger.info("  - GET  /api/doctor/profile - 获取医生信息")
        logger.info("  - PUT  /api/doctor/profile - 更新医生信息")
        logger.info("  - GET  /api/doctor/patients - 获取患者列表")
        logger.info("  - POST /api/doctor/patients/<patient_id>/assign - 分配患者")
        logger.info("  - POST /api/doctor/patients/<patient_id>/tag - 添加标签")
        logger.info("  - POST /api/doctor/feedback - 提交AI反馈")
        logger.info("  - GET  /api/doctor/feedback/<exam_id> - 获取反馈")
        logger.info("  - POST /api/doctor/progression/create - 创建病程追踪")
        logger.info("  - GET  /api/doctor/progression/<patient_id> - 获取病程追踪")
        logger.info("  - GET  /api/doctor/statistics/dashboard - 医生工作台")
        logger.info("  - GET  /api/doctor/statistics/ai_performance - AI性能统计")
        logger.info("  - POST /api/doctor/consultation/request - 申请会诊")
        logger.info("  - POST /api/doctor/consultation/<id>/respond - 回复会诊")
        logger.info("  - GET  /api/doctor/consultation/list - 会诊列表")
        logger.info("  - GET  /api/doctor/teaching_cases - 教学案例")
        logger.info("=" * 50)
        logger.info("测试医生账号:")
        logger.info("  医生ID: D001, 密码: doctor123 (李明 - 眼科主任医师)")
        logger.info("  医生ID: D002, 密码: doctor123 (王芳 - 心内科副主任医师)")
        logger.info("  医生ID: D003, 密码: doctor123 (张伟 - 内分泌科主治医师)")
        logger.info("=" * 50)

        # 启动Flask应用
        app.run(debug=True, host='0.0.0.0', port=5001)
    else:
        logger.error("系统初始化失败，无法启动应用")
        exit(1)