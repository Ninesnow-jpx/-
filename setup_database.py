"""
完整数据库初始化脚本
包含患者端(6张表) + 医生端(8张表)
"""

import sqlite3
import os
import hashlib

DATABASE = 'medical_screening.db'

def hash_password(password):
    """简单的密码哈希（生产环境应使用bcrypt或argon2）"""
    return hashlib.sha256(password.encode()).hexdigest()

print("=" * 60)
print("开始初始化完整数据库...")
print("=" * 60)

# 如果数据库已存在，删除它
if os.path.exists(DATABASE):
    print(f"\n发现旧数据库文件，正在删除...")
    os.remove(DATABASE)
    print("✓ 旧数据库已删除")

# 创建新数据库
print(f"\n正在创建数据库: {DATABASE}")
conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

try:
    # ==================== 患者端表 (6张) ====================
    
    print("\n【患者端表】")
    
    # 1. 患者信息表
    print("创建表: patients...")
    cursor.execute('''
        CREATE TABLE patients (
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
    print("创建表: examinations...")
    cursor.execute('''
        CREATE TABLE examinations (
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
    print("创建表: fundus_results...")
    cursor.execute('''
        CREATE TABLE fundus_results (
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
    print("创建表: ecg_results...")
    cursor.execute('''
        CREATE TABLE ecg_results (
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
    print("创建表: text_results...")
    cursor.execute('''
        CREATE TABLE text_results (
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
    print("创建表: comprehensive_reports...")
    cursor.execute('''
        CREATE TABLE comprehensive_reports (
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
    
    print("\n【医生端表】")
    
    # 7. 医生信息表
    print("创建表: doctors...")
    cursor.execute('''
        CREATE TABLE doctors (
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
    print("创建表: doctor_patient_relations...")
    cursor.execute('''
        CREATE TABLE doctor_patient_relations (
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
    print("创建表: ai_feedback...")
    cursor.execute('''
        CREATE TABLE ai_feedback (
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
    print("创建表: disease_progression...")
    cursor.execute('''
        CREATE TABLE disease_progression (
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
    print("创建表: doctor_activity_log...")
    cursor.execute('''
        CREATE TABLE doctor_activity_log (
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
    print("创建表: doctor_statistics...")
    cursor.execute('''
        CREATE TABLE doctor_statistics (
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
    print("创建表: consultations...")
    cursor.execute('''
        CREATE TABLE consultations (
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
    print("创建表: patient_tags...")
    cursor.execute('''
        CREATE TABLE patient_tags (
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
    print("\n创建索引...")
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
    
    # 插入测试医生数据
    print("\n插入测试医生数据...")
    test_doctors = [
        ('D001', '李明', '主任医师', '眼科', '糖尿病视网膜病变', '13900000001', 'liming@hospital.com', 'doctor123', '110101199001011234'),
        ('D002', '王芳', '副主任医师', '心内科', '心血管疾病', '13900000002', 'wangfang@hospital.com', 'doctor123', '110101198502022345'),
        ('D003', '张伟', '主治医师', '内分泌科', '糖尿病管理', '13900000003', 'zhangwei@hospital.com', 'doctor123', '110101199003033456')
    ]
    
    for doctor_id, name, title, dept, spec, phone, email, password, license in test_doctors:
        cursor.execute('''
            INSERT INTO doctors (doctor_id, name, title, department, specialization, 
                               phone, email, password_hash, license_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (doctor_id, name, title, dept, spec, phone, email, hash_password(password), license))
        print(f"  ✓ 创建医生: {name} ({doctor_id})")
    
    # 初始化医生统计数据
    print("\n初始化医生统计数据...")
    for doctor_id, name, _, _, _, _, _, _, _ in test_doctors:
        cursor.execute('''
            INSERT INTO doctor_statistics (doctor_id, total_patients, total_reviews, total_feedbacks)
            VALUES (?, 0, 0, 0)
        ''', (doctor_id,))
    
    conn.commit()
    
    print("\n" + "=" * 60)
    print("✓ 完整数据库初始化成功！")
    print("=" * 60)
    print(f"数据库文件: {DATABASE}")
    print("\n已创建 14 张表:")
    print("\n【患者端 - 6张表】")
    print("  1. patients - 患者信息")
    print("  2. examinations - 检查记录")
    print("  3. fundus_results - 眼底分析结果")
    print("  4. ecg_results - ECG分析结果")
    print("  5. text_results - 文本分析结果")
    print("  6. comprehensive_reports - 综合诊断报告")
    print("\n【医生端 - 8张表】")
    print("  7. doctors - 医生信息")
    print("  8. doctor_patient_relations - 医患关系")
    print("  9. ai_feedback - AI反馈记录")
    print("  10. disease_progression - 病程追踪")
    print("  11. doctor_activity_log - 医生活动日志")
    print("  12. doctor_statistics - 医生统计数据")
    print("  13. consultations - 会诊记录")
    print("  14. patient_tags - 患者标记")
    
    print("\n测试医生账号:")
    print("  医生ID: D001, 密码: doctor123 (李明 - 眼科主任医师)")
    print("  医生ID: D002, 密码: doctor123 (王芳 - 心内科副主任医师)")
    print("  医生ID: D003, 密码: doctor123 (张伟 - 内分泌科主治医师)")
    
    print("\n现在可以启动后端了:")
    print("  python app.py")
    print("\n然后运行测试:")
    print("  python test_api.py")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 错误: {str(e)}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    conn.close()