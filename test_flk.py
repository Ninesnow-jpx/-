import sqlite3
import os

import json

BASE_URL = 'http://localhost:5000'


def test_fk_constraint():
    # 模拟登录一个已存在的医生（假设 doc001 存在，或者我先注册一个）
    # 其实我不需要登录，我直接操作数据库文件试试，或者通过 API。
    # 为了准确模拟生产环境，我应该通过 API 测。
    # 但我不知道任何医生的密码...
    # 所以我只能操作数据库文件来验证 "PRAGMA foreign_keys" 的状态。

    db_path = 'medical_screening.db'
    if not os.path.exists(db_path):
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查外键开关状态
    cursor.execute('PRAGMA foreign_keys')
    fk_status = cursor.fetchone()
    print(f"Direct DB: PRAGMA foreign_keys = {fk_status[0]}")

    # 尝试在数据库层插入坏数据
    # 先找一个 valid exam_id 和 requesting_doctor_id
    cursor.execute("SELECT exam_id FROM examinations LIMIT 1")
    exam = cursor.fetchone()
    cursor.execute("SELECT doctor_id FROM doctors LIMIT 1")
    doc = cursor.fetchone()

    if not exam or not doc:
        print("Not enough data to test FK")
        return

    exam_id = exam[0]
    doc_id = doc[0]

    print(f"Using exam_id={exam_id}, doc_id={doc_id}")

    try:
        cursor.execute('''
            INSERT INTO consultations 
            (consultation_id, exam_id, requesting_doctor_id, consulting_doctor_id)
            VALUES (?, ?, ?, ?)
        ''', ('TEST_CONS_FK', exam_id, doc_id, 'NON_EXISTENT_DOC'))
        print("Direct DB: Inserted invalid doctor_id successfully! (FK disabled)")
        # Clean up
        cursor.execute("DELETE FROM consultations WHERE consultation_id = 'TEST_CONS_FK'")
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"Direct DB: IntegrityError expected: {e} (FK enabled)")

    conn.close()


if __name__ == '__main__':
    test_fk_constraint()
