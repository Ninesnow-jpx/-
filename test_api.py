"""
多模态慢性病智能筛查平台 - API测试脚本
测试所有后端接口的功能
"""

import requests
import json
import os
import time
from datetime import datetime
from app import ECG_UPLOAD_SUCCESS_MSG, ECG_UPLOAD_FILE_PATH_MSG

# 配置
BASE_URL = 'http://localhost:5000'
TEST_DATA_DIR = 'test_data'

# 创建测试数据目录
os.makedirs(TEST_DATA_DIR, exist_ok=True)


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_test(test_name):
    """打印测试名称"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}测试: {test_name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")


def print_success(message):
    """打印成功信息"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_error(message):
    """打印错误信息"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def print_info(message):
    """打印信息"""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")


def create_test_files():
    """创建测试用的文件"""
    # 创建测试眼底图像
    # 路径完全匹配你的项目结构
    fundus_path = os.path.join(
        TEST_DATA_DIR,
        "Diabetic Retinopathy Arranged_datasets",
        "1",
        "15_left.jpeg"
    )
    # 检查真实眼底图像文件是否存在
    if not os.path.exists(fundus_path):
        print_error(f"真实眼底图像文件不存在: {fundus_path}")
        # 如果不存在，降级使用test_fundus.jpg
        fallback_fundus_path = os.path.join(TEST_DATA_DIR, 'test_fundus.jpg')
        if os.path.exists(fallback_fundus_path):
            fundus_path = fallback_fundus_path
            print_info(f"使用备用测试图像: {fundus_path}")
        else:
            # 如果备用文件也不存在，创建模拟文件
            with open(fallback_fundus_path, 'wb') as f:
                f.write(b'fake image data for testing')
            fundus_path = fallback_fundus_path
            print_info(f"已创建模拟眼底图像文件: {fundus_path}")
    else:
        print_success(f"找到真实眼底图像文件: {fundus_path}")
    
    # 创建测试ECG数据
    ecg_path = os.path.join(TEST_DATA_DIR, "ecg_1000", "TRAIN", "TRAIN101.mat")
    # 检查文件是否存在
    if not os.path.exists(ecg_path):
        print(f"❌ 文件不存在: {ecg_path}")
    else:
        # 加载 .mat 文件（与你的训练模型逻辑一致）
        import scipy.io as sio
        mat_data = sio.loadmat(ecg_path)
        ecg_signal = mat_data['data'].flatten()  # 假设数据存在 'data' 字段中
        print(f"✅ 成功加载 {ecg_path}，信号长度: {len(ecg_signal)}")
    
    # 创建测试病历文本
        text_path = os.path.join(TEST_DATA_DIR, 'test_medical_text.txt')
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write('''【主诉】视力模糊2个月，伴多饮、多尿
    【既往史】糖尿病史5年，血糖控制不佳；高血压史3年，未规律服药
    【体格检查】空腹血糖7.8 mmol/L，糖化血红蛋白8.2%，血压145/90 mmHg，心率75次/分
            ''')

        return fundus_path, ecg_path, text_path


def test_health_check():
    """测试健康检查接口"""
    print_test("健康检查")
    try:
        response = requests.get(f'{BASE_URL}/api/health')
        if response.status_code == 200:
            data = response.json()
            print_success(f"服务器状态: {data['status']}")
            print_info(f"时间戳: {data['timestamp']}")
            return True
        else:
            print_error(f"健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"连接失败: {str(e)}")
        print_info("请确保后端服务已启动 (python app.py)")
        return False


def test_patient_registration():
    """测试患者注册"""
    print_test("患者注册")
    try:
        patient_data = {
            'name': '张三',
            'age': 55,
            'gender': '男',
            'phone': '13800138000'
        }
        
        response = requests.post(
            f'{BASE_URL}/api/patient/register',
            json=patient_data
        )
        
        if response.status_code == 201:
            data = response.json()
            patient_id = data['patient_id']
            print_success(f"患者注册成功")
            print_info(f"患者ID: {patient_id}")
            return patient_id
        else:
            print_error(f"注册失败: {response.json()}")
            return None
    except Exception as e:
        print_error(f"注册异常: {str(e)}")
        return None


def test_create_examination(patient_id):
    """测试创建检查记录"""
    print_test("创建检查记录")
    try:
        response = requests.post(
            f'{BASE_URL}/api/examination/create',
            json={'patient_id': patient_id}
        )
        
        if response.status_code == 201:
            data = response.json()
            exam_id = data['exam_id']
            print_success(f"检查记录创建成功")
            print_info(f"检查ID: {exam_id}")
            return exam_id
        else:
            print_error(f"创建失败: {response.json()}")
            return None
    except Exception as e:
        print_error(f"创建异常: {str(e)}")
        return None


def test_upload_fundus(exam_id, file_path):
    """测试上传眼底图像"""
    print_test("上传眼底图像")
    try:
        # 获取真实的文件名（如15_left.jpeg或test_fundus.jpg）
        file_name = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f, 'image/jpeg')}
            data = {'exam_id': exam_id}

            response = requests.post(
                f'{BASE_URL}/api/upload/fundus',
                files=files,
                data=data
            )

        if response.status_code == 200:
            result = response.json()
            print_success("眼底图像上传成功")
            print_info(f"文件路径: {result['file_path']}")
            return True
        else:
            print_error(f"上传失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"上传异常: {str(e)}")
        return False


def test_upload_ecg(exam_id, file_path):
    """测试上传ECG数据（适配.mat文件）"""
    print_test("上传ECG数据")
    try:
        # 从文件路径提取真实文件名（如 TRAIN101.mat）
        file_name = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            # 关键修改：适配.mat文件的文件名和MIME类型
            files = {'file': (file_name, f, 'application/octet-stream')}
            data = {'exam_id': exam_id}

            response = requests.post(
                f'{BASE_URL}/api/upload/ecg',
                files=files,
                data=data
            )

        if response.status_code == 200:
            result = response.json()
            # 引用app.py中的输出文案，保证格式统一
            print_success(ECG_UPLOAD_SUCCESS_MSG)
            print_info(ECG_UPLOAD_FILE_PATH_MSG.format(file_path=result['file_path']))
            return True
        else:
            print_error(f"上传失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"上传异常: {str(e)}")
        return False


def test_upload_medical_text(exam_id, file_path):
    """测试上传病历文本"""
    print_test("上传病历文本")
    try:
        with open(file_path, 'rb') as f:
            files = {'file': ('test_medical_text.txt', f, 'text/plain')}
            data = {'exam_id': exam_id}
            
            response = requests.post(
                f'{BASE_URL}/api/upload/medical_text',
                files=files,
                data=data
            )
        
        if response.status_code == 200:
            result = response.json()
            print_success("病历文本上传成功")
            print_info(f"文件路径: {result['file_path']}")
            return True
        else:
            print_error(f"上传失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"上传异常: {str(e)}")
        return False


def test_analyze(exam_id):
    """测试综合分析"""
    print_test("执行综合分析")
    try:
        print_info("正在分析，请稍候...")
        response = requests.post(f'{BASE_URL}/api/analyze/{exam_id}')
        
        if response.status_code == 200:
            result = response.json()
            print_success("分析完成")
            
            # 显示眼底分析结果
            if result.get('fundus_analysis'):
                fundus = result['fundus_analysis']
                print_info(f"眼底分析 - 病灶数量: {fundus['lesion_count']}, "
                          f"风险等级: {fundus['risk_level']}, "
                          f"置信度: {fundus['confidence']:.2%}")
            
            # 显示ECG分析结果
            if result.get('ecg_analysis'):
                ecg = result['ecg_analysis']
                print_info(f"ECG分析 - 心率: {ecg['heart_rate']} bpm, "
                          f"节律: {ecg['rhythm_type']}, "
                          f"风险等级: {ecg['risk_level']}")
            
            # 显示综合报告
            if result.get('comprehensive_report'):
                report = result['comprehensive_report']
                print_info(f"综合诊断 - 总体风险: {report['overall_risk_level']}")
                print_info(f"主要诊断: {report['primary_diagnosis']}")
                print_info(f"次要诊断: {report['secondary_diagnosis']}")
            
            return True
        else:
            print_error(f"分析失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"分析异常: {str(e)}")
        return False


def test_get_report(exam_id):
    """测试获取报告"""
    print_test("获取诊断报告")
    try:
        response = requests.get(f'{BASE_URL}/api/report/{exam_id}')
        
        if response.status_code == 200:
            report = response.json()
            print_success("报告获取成功")
            
            # 显示报告摘要
            exam_info = report['exam_info']
            print_info(f"患者: {exam_info['patient_name']}, "
                      f"年龄: {exam_info['age']}, "
                      f"性别: {exam_info['gender']}")
            print_info(f"检查日期: {exam_info['exam_date']}")
            print_info(f"状态: {exam_info['status']}")
            
            if report.get('comprehensive_report'):
                comp_report = report['comprehensive_report']
                print_info(f"综合风险: {comp_report['overall_risk_level']}")
                print_info(f"置信度: {comp_report['confidence']:.2%}")
            
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_patient_history(patient_id):
    """测试获取患者历史"""
    print_test("获取患者历史记录")
    try:
        response = requests.get(f'{BASE_URL}/api/patient/{patient_id}/history')
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"历史记录获取成功")
            print_info(f"患者: {data['patient_name']}")
            print_info(f"总检查次数: {data['total_examinations']}")
            
            for i, exam in enumerate(data['history'][:3], 1):
                print_info(f"  检查{i}: {exam['exam_date']} - "
                          f"状态: {exam['status']}, "
                          f"风险: {exam.get('overall_risk_level', 'N/A')}")
            
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_statistics():
    """测试统计信息"""
    print_test("获取系统统计")
    try:
        response = requests.get(f'{BASE_URL}/api/statistics')
        
        if response.status_code == 200:
            stats = response.json()
            print_success("统计信息获取成功")
            print_info(f"总患者数: {stats['total_patients']}")
            print_info(f"总检查数: {stats['total_examinations']}")
            print_info(f"已完成检查: {stats['completed_examinations']}")
            
            if stats.get('risk_distribution'):
                print_info("风险分布:")
                for risk, count in stats['risk_distribution'].items():
                    print_info(f"  {risk}: {count}")
            
            return True
        else:
            print_error(f"获取失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"获取异常: {str(e)}")
        return False


def test_search():
    """测试搜索功能"""
    print_test("搜索检查记录")
    try:
        # 测试按患者姓名搜索
        response = requests.get(
            f'{BASE_URL}/api/search',
            params={'patient_name': '张'}
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"搜索成功，找到 {data['total']} 条记录")
            
            for i, result in enumerate(data['results'][:3], 1):
                print_info(f"  记录{i}: {result['name']} - "
                          f"{result['exam_date']} - "
                          f"{result.get('primary_diagnosis', 'N/A')}")
            
            return True
        else:
            print_error(f"搜索失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"搜索异常: {str(e)}")
        return False


def test_export_report(exam_id):
    """测试导出报告"""
    print_test("导出诊断报告")
    try:
        response = requests.get(f'{BASE_URL}/api/export/report/{exam_id}')
        
        if response.status_code == 200:
            export_data = response.json()
            print_success("报告导出成功")
            print_info(f"报告编号: {export_data['报告编号']}")
            print_info(f"患者: {export_data['患者姓名']}")
            print_info(f"综合风险: {export_data['综合风险等级']}")
            
            # 保存到文件
            export_file = os.path.join(TEST_DATA_DIR, f'report_{exam_id}.json')
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            print_info(f"报告已保存到: {export_file}")
            
            return True
        else:
            print_error(f"导出失败: {response.json()}")
            return False
    except Exception as e:
        print_error(f"导出异常: {str(e)}")
        return False


def run_all_tests():
    """运行所有测试"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}多模态慢性病智能筛查平台 - API测试套件{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print_info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"目标服务器: {BASE_URL}")
    
    # 创建测试文件
    print_info("准备测试数据...")
    fundus_path, ecg_path, text_path = create_test_files()
    print_success("测试数据准备完成")
    
    # 测试计数
    total_tests = 0
    passed_tests = 0
    
    # 1. 健康检查
    total_tests += 1
    if test_health_check():
        passed_tests += 1
    else:
        print_error("服务器未响应，终止测试")
        return
    
    time.sleep(0.5)
    
    # 2. 患者注册
    total_tests += 1
    patient_id = test_patient_registration()
    if patient_id:
        passed_tests += 1
    else:
        print_error("患者注册失败，终止测试")
        return
    
    time.sleep(0.5)
    
    # 3. 创建检查
    total_tests += 1
    exam_id = test_create_examination(patient_id)
    if exam_id:
        passed_tests += 1
    else:
        print_error("创建检查失败，终止测试")
        return
    
    time.sleep(0.5)
    
    # 4. 上传眼底图像
    total_tests += 1
    if test_upload_fundus(exam_id, fundus_path):
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 5. 上传ECG数据
    total_tests += 1
    if test_upload_ecg(exam_id, ecg_path):
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 6. 上传病历文本
    total_tests += 1
    if test_upload_medical_text(exam_id, text_path):
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 7. 执行分析
    total_tests += 1
    if test_analyze(exam_id):
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 8. 获取报告
    total_tests += 1
    if test_get_report(exam_id):
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 9. 患者历史
    total_tests += 1
    if test_patient_history(patient_id):
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 10. 统计信息
    total_tests += 1
    if test_statistics():
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 11. 搜索功能
    total_tests += 1
    if test_search():
        passed_tests += 1
    
    time.sleep(0.5)
    
    # 12. 导出报告
    total_tests += 1
    if test_export_report(exam_id):
        passed_tests += 1
    
    # 测试总结
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}测试总结{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print_info(f"总测试数: {total_tests}")
    print_success(f"通过: {passed_tests}")
    if total_tests - passed_tests > 0:
        print_error(f"失败: {total_tests - passed_tests}")
    
    success_rate = (passed_tests / total_tests) * 100
    if success_rate == 100:
        print(f"\n{Colors.GREEN}🎉 所有测试通过！{Colors.END}")
    elif success_rate >= 80:
        print(f"\n{Colors.YELLOW}⚠️  大部分测试通过 ({success_rate:.1f}%){Colors.END}")
    else:
        print(f"\n{Colors.RED}❌ 测试失败率较高 ({success_rate:.1f}%){Colors.END}")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}\n")


if __name__ == '__main__':
    run_all_tests()