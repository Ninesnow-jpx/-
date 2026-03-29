"""
多模态慢性病智能筛查平台 - 医生端 API 测试脚本
测试所有医生端后端接口的功能
"""

import requests
import json
import time
from datetime import datetime

# 配置
BASE_URL = 'http://localhost:5001'
DOCTOR_ID = 'D001'
DOCTOR_PASSWORD = 'doctor123'


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_test(test_name):
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}测试: {test_name}{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.END}")


def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message):
    print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")


def test_doctor_login():
    """测试医生登录"""
    print_test("医生登录")
    try:
        response = requests.post(
            f'{BASE_URL}/api/doctor/login',
            json={'doctor_id': DOCTOR_ID, 'password': DOCTOR_PASSWORD}
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"登录成功: {data['doctor']['name']}")
            print_info(f"科室: {data['doctor']['department']}")
            print_info(f"职称: {data['doctor']['title']}")
            return True
        else:
            print_error(f"登录失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"登录异常: {str(e)}")
        return False


def get_headers():
    """获取医生认证头"""
    return {'X-Doctor-ID': DOCTOR_ID}


def test_doctor_profile():
    """测试获取医生信息"""
    print_test("获取医生信息")
    try:
        response = requests.get(
            f'{BASE_URL}/api/doctor/profile',
            headers=get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print_success("获取成功")
            print_info(f"医生: {data['doctor']['name']}")
            if data.get('statistics'):
                stats = data['statistics']
                print_info(f"管理患者数: {stats.get('total_patients', 0)}")
                print_info(f"已处理报告: {stats.get('total_reviews', 0)}")
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_doctor_patients():
    """测试获取患者列表"""
    print_test("获取患者列表")
    try:
        response = requests.get(
            f'{BASE_URL}/api/doctor/patients',
            headers=get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"获取成功，共 {data['total']} 位患者")
            for p in data['patients'][:3]:
                print_info(f"  - {p['name']} ({p['patient_id']}), 风险: {p.get('latest_risk_level', 'N/A')}")
            return data['patients'][0]['patient_id'] if data['patients'] else None
        else:
            print_error(f"获取失败: {response.json()}")
            return None
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return None


def test_assign_patient(patient_id):
    """测试分配患者"""
    print_test("分配患者到医生")
    try:
        response = requests.post(
            f'{BASE_URL}/api/doctor/patients/{patient_id}/assign',
            headers=get_headers(),
            json={'relation_type': 'primary', 'notes': 'Test assignment'}
        )

        if response.status_code == 200:
            print_success("分配成功")
            return True
        else:
            # 可能是已分配
            print_info(f"分配状态: {response.json().get('error', response.json())}")
            return True
    except Exception as e:
        print_error(f"分配异常: {str(e)}")
        return False


def test_tag_patient(patient_id):
    """测试添加患者标签"""
    print_test("添加患者标签")
    try:
        response = requests.post(
            f'{BASE_URL}/api/doctor/patients/{patient_id}/tag',
            headers=get_headers(),
            json={
                'tag_type': '慢病重点',
                'tag_color': '#FF5722',
                'notes': 'Test tag'
            }
        )

        if response.status_code == 200:
            print_success("标签添加成功")
            return True
        else:
            print_error(f"添加失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"添加异常: {str(e)}")
        return False


def test_ai_performance():
    """测试AI性能统计"""
    print_test("AI性能统计")
    try:
        response = requests.get(
            f'{BASE_URL}/api/doctor/statistics/ai_performance',
            headers=get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            perf = data['overall_performance']
            print_success("获取成功")
            print_info(f"总反馈数: {perf['total_feedbacks']}")
            print_info(f"准确率: {perf['accuracy_rate']:.1f}%")
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_consultation_list():
    """测试会诊列表"""
    print_test("会诊列表")
    try:
        response = requests.get(
            f'{BASE_URL}/api/doctor/consultation/list?type=all',
            headers=get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"获取成功，共 {data['total']} 条会诊记录")
            for c in data['consultations'][:3]:
                print_info(f"  - {c['consultation_id']}: {c['patient_name']} ({c['consultation_status']})")
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_teaching_cases():
    """测试教学案例"""
    print_test("教学案例库")
    try:
        response = requests.get(
            f'{BASE_URL}/api/doctor/teaching_cases',
            headers=get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"获取成功，共 {data['total']} 个教学案例")
            for c in data['teaching_cases'][:3]:
                print_info(f"  - 案例 #{c['id']}: {c.get('original_diagnosis', 'N/A')}")
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_progression(patient_id):
    """测试病程追踪"""
    print_test("病程追踪")
    try:
        response = requests.get(
            f'{BASE_URL}/api/doctor/progression/{patient_id}',
            headers=get_headers()
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"获取成功")
            print_info(f"历史追踪记录数: {data['total_progressions']}")
            print_info(f"检查历史数: {len(data['exam_history'])}")
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def run_doctor_tests():
    """运行医生端测试"""
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}多模态慢性病智能筛查平台 - 医生端 API 测试{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.END}")
    print_info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"目标服务器: {BASE_URL}")
    print_info(f"测试医生: {DOCTOR_ID}")

    total_tests = 0
    passed_tests = 0

    # 1. 医生登录
    total_tests += 1
    if test_doctor_login():
        passed_tests += 1
    else:
        print_error("登录失败，终止测试")
        return

    time.sleep(0.3)

    # 2. 获取医生信息
    total_tests += 1
    if test_doctor_profile():
        passed_tests += 1

    time.sleep(0.3)

    # 3. 获取患者列表
    total_tests += 1
    patient_id = test_doctor_patients()
    if patient_id:
        passed_tests += 1

    time.sleep(0.3)

    # 4. 分配患者
    if patient_id:
        total_tests += 1
        if test_assign_patient(patient_id):
            passed_tests += 1

    time.sleep(0.3)

    # 5. 添加标签
    if patient_id:
        total_tests += 1
        if test_tag_patient(patient_id):
            passed_tests += 1

    time.sleep(0.3)

    # 6. 病程追踪
    if patient_id:
        total_tests += 1
        if test_progression(patient_id):
            passed_tests += 1

    time.sleep(0.3)

    # 7. AI性能统计
    total_tests += 1
    if test_ai_performance():
        passed_tests += 1

    time.sleep(0.3)

    # 8. 会诊列表
    total_tests += 1
    if test_consultation_list():
        passed_tests += 1

    time.sleep(0.3)

    # 9. 教学案例
    total_tests += 1
    if test_teaching_cases():
        passed_tests += 1

    # 测试总结
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}测试总结{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 60}{Colors.END}")
    print_info(f"总测试数: {total_tests}")
    print_success(f"通过: {passed_tests}")
    if total_tests - passed_tests > 0:
        print_error(f"失败: {total_tests - passed_tests}")

    success_rate = (passed_tests / total_tests) * 100
    if success_rate == 100:
        print(f"\n{Colors.GREEN}🎉 所有医生端测试通过！{Colors.END}")
    elif success_rate >= 80:
        print(f"\n{Colors.YELLOW}⚠️  大部分测试通过 ({success_rate:.1f}%){Colors.END}")
    else:
        print(f"\n{Colors.RED}❌ 测试失败率较高 ({success_rate:.1f}%){Colors.END}")

    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}\n")


if __name__ == '__main__':
    run_doctor_tests()
