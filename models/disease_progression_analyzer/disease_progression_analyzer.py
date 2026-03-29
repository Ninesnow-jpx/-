import json
import numpy as np
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ProgressionAnalyzer")

# ==================== 配置常量 ====================
# DR分级变化阈值（用于判断病情进展/好转）
DR_GRADE_CHANGE_THRESHOLD = 1
# 心率变化阈值（bpm）
HEART_RATE_THRESHOLD = 10
# 风险等级权重（用于综合评估）
RISK_WEIGHTS = {
    "低风险": 1,
    "中风险": 2,
    "高风险": 3,
    "极高风险": 4
}
# 病情状态定义
PROGRESSION_STATUS_MAP = {
    "improved": "好转",
    "stable": "稳定",
    "worsened": "恶化",
    "critical": "危重"
}


# ==================== 病情分析核心类 ====================
class DiseaseProgressionAnalyzer:
    """
    多模态病情进展分析器
    对比两次检查的眼底、ECG、文本数据，自动分析病情变化
    """

    def __init__(self):
        pass

    def analyze_progression(self, start_exam_data, end_exam_data):
        """
        核心分析函数
        :param start_exam_data: 首次检查完整数据（包含fundus/ecg/text/report）
        :param end_exam_data: 末次检查完整数据（包含fundus/ecg/text/report）
        :return: 结构化的病情进展分析结果
        """
        try:
            # 1. 初始化分析结果
            progression_result = {
                "progression_status": "stable",  # 默认稳定
                "key_changes": [],  # 关键变化列表
                "fundus_trend": {},  # 眼底变化趋势
                "ecg_trend": {},  # ECG变化趋势
                "clinical_trend": {},  # 临床/文本变化趋势
                "risk_assessment": {},  # 风险变化评估
                "suggestion": ""  # 医生参考建议
            }

            # 2. 分析眼底图像变化
            fundus_trend = self._analyze_fundus_progression(
                start_exam_data.get("fundus_analysis", {}),
                end_exam_data.get("fundus_analysis", {})
            )
            progression_result["fundus_trend"] = fundus_trend
            if fundus_trend["key_changes"]:
                progression_result["key_changes"].extend(fundus_trend["key_changes"])

            # 3. 分析ECG变化
            ecg_trend = self._analyze_ecg_progression(
                start_exam_data.get("ecg_analysis", {}),
                end_exam_data.get("ecg_analysis", {})
            )
            progression_result["ecg_trend"] = ecg_trend
            if ecg_trend["key_changes"]:
                progression_result["key_changes"].extend(ecg_trend["key_changes"])

            # 4. 分析临床文本变化
            clinical_trend = self._analyze_clinical_progression(
                start_exam_data.get("text_analysis", {}),
                end_exam_data.get("text_analysis", {})
            )
            progression_result["clinical_trend"] = clinical_trend
            if clinical_trend["key_changes"]:
                progression_result["key_changes"].extend(clinical_trend["key_changes"])

            # 5. 综合评估病情状态
            overall_status = self._evaluate_overall_progression(
                fundus_trend, ecg_trend, clinical_trend,
                start_exam_data.get("comprehensive_report", {}),
                end_exam_data.get("comprehensive_report", {})
            )
            progression_result["progression_status"] = overall_status
            progression_result["risk_assessment"] = self._evaluate_risk_change(
                start_exam_data.get("comprehensive_report", {}),
                end_exam_data.get("comprehensive_report", {})
            )

            # 6. 生成参考建议
            progression_result["suggestion"] = self._generate_suggestion(progression_result)

            logger.info(f"病情进展分析完成，状态：{overall_status}")
            return progression_result

        except Exception as e:
            logger.error(f"病情进展分析失败: {str(e)}", exc_info=True)
            # 返回默认稳定状态
            return {
                "progression_status": "stable",
                "key_changes": [f"分析过程出错: {str(e)}"],
                "fundus_trend": {},
                "ecg_trend": {},
                "clinical_trend": {},
                "risk_assessment": {},
                "suggestion": "无法自动分析病情变化，请医生手动评估"
            }

    def _analyze_fundus_progression(self, start_fundus, end_fundus):
        """分析眼底图像病情变化"""
        trend = {
            "dr_grade_change": 0,
            "lesion_count_change": 0,
            "risk_level_change": "",
            "key_changes": [],
            "trend_description": ""
        }

        if not start_fundus or not end_fundus:
            trend["trend_description"] = "缺少眼底检查数据，无法分析"
            return trend

        # DR分级变化
        start_grade = start_fundus.get("dr_grade", 0)
        end_grade = end_fundus.get("dr_grade", 0)
        trend["dr_grade_change"] = end_grade - start_grade

        # 病灶数量变化
        start_lesion = start_fundus.get("lesion_count", 0)
        end_lesion = end_fundus.get("lesion_count", 0)
        trend["lesion_count_change"] = end_lesion - start_lesion

        # 风险等级变化
        start_risk = start_fundus.get("risk_level", "低风险")
        end_risk = end_fundus.get("risk_level", "低风险")
        trend["risk_level_change"] = f"{start_risk} → {end_risk}"

        # 关键变化描述
        if trend["dr_grade_change"] > DR_GRADE_CHANGE_THRESHOLD:
            trend["key_changes"].append(f"DR分级升高{trend['dr_grade_change']}级（{start_grade}→{end_grade}），病情恶化")
        elif trend["dr_grade_change"] < -DR_GRADE_CHANGE_THRESHOLD:
            trend["key_changes"].append(
                f"DR分级降低{abs(trend['dr_grade_change'])}级（{start_grade}→{end_grade}），病情好转")

        if trend["lesion_count_change"] > 3:
            trend["key_changes"].append(f"病灶数量增加{trend['lesion_count_change']}个（{start_lesion}→{end_lesion}）")
        elif trend["lesion_count_change"] < -3:
            trend["key_changes"].append(
                f"病灶数量减少{abs(trend['lesion_count_change'])}个（{start_lesion}→{end_lesion}）")

        # 趋势总结
        if trend["key_changes"]:
            trend["trend_description"] = "; ".join(trend["key_changes"])
        else:
            trend["trend_description"] = "眼底病变无明显变化"

        return trend

    def _analyze_ecg_progression(self, start_ecg, end_ecg):
        """分析ECG病情变化"""
        trend = {
            "heart_rate_change": 0,
            "rhythm_change": "",
            "abnormalities_change": [],
            "risk_level_change": "",
            "key_changes": [],
            "trend_description": ""
        }

        if not start_ecg or not end_ecg:
            trend["trend_description"] = "缺少ECG检查数据，无法分析"
            return trend

        # 心率变化
        start_hr = start_ecg.get("heart_rate", 75)
        end_hr = end_ecg.get("heart_rate", 75)
        trend["heart_rate_change"] = end_hr - start_hr

        # 心律变化
        start_rhythm = start_ecg.get("rhythm_type", "窦性心律")
        end_rhythm = end_ecg.get("rhythm_type", "窦性心律")
        trend["rhythm_change"] = f"{start_rhythm} → {end_rhythm}"

        # 异常情况变化
        start_abn = json.loads(start_ecg.get("abnormalities", "[]")) if start_ecg.get("abnormalities") else []
        end_abn = json.loads(end_ecg.get("abnormalities", "[]")) if end_ecg.get("abnormalities") else []

        new_abn = [a for a in end_abn if a not in start_abn]
        resolved_abn = [a for a in start_abn if a not in end_abn]
        trend["abnormalities_change"] = {
            "new": new_abn,
            "resolved": resolved_abn
        }

        # 风险等级变化
        start_risk = start_ecg.get("risk_level", "低风险")
        end_risk = end_ecg.get("risk_level", "低风险")
        trend["risk_level_change"] = f"{start_risk} → {end_risk}"

        # 关键变化描述
        if abs(trend["heart_rate_change"]) > HEART_RATE_THRESHOLD:
            if trend["heart_rate_change"] > 0:
                trend["key_changes"].append(f"心率升高{trend['heart_rate_change']}bpm（{start_hr}→{end_hr}）")
            else:
                trend["key_changes"].append(f"心率降低{abs(trend['heart_rate_change'])}bpm（{start_hr}→{end_hr}）")

        if start_rhythm != end_rhythm:
            trend["key_changes"].append(f"心律类型变化：{start_rhythm} → {end_rhythm}")

        if new_abn:
            trend["key_changes"].append(f"新增异常：{', '.join(new_abn)}")
        if resolved_abn:
            trend["key_changes"].append(f"异常消失：{', '.join(resolved_abn)}")

        # 趋势总结
        if trend["key_changes"]:
            trend["trend_description"] = "; ".join(trend["key_changes"])
        else:
            trend["trend_description"] = "心电图无明显变化"

        return trend

    def _analyze_clinical_progression(self, start_text, end_text):
        """分析临床文本/病历变化"""
        trend = {
            "symptoms_change": {},
            "risk_factors_change": {},
            "key_changes": [],
            "trend_description": ""
        }

        if not start_text or not end_text:
            trend["trend_description"] = "缺少病历文本数据，无法分析"
            return trend

        # 症状变化
        start_symptoms = json.loads(start_text.get("symptoms", "[]")) if start_text.get("symptoms") else []
        end_symptoms = json.loads(end_text.get("symptoms", "[]")) if end_text.get("symptoms") else []

        new_symptoms = [s for s in end_symptoms if s not in start_symptoms]
        resolved_symptoms = [s for s in start_symptoms if s not in end_symptoms]
        trend["symptoms_change"] = {
            "new": new_symptoms,
            "resolved": resolved_symptoms
        }

        # 风险因素变化
        start_risk = json.loads(start_text.get("risk_factors", "[]")) if start_text.get("risk_factors") else []
        end_risk = json.loads(end_text.get("risk_factors", "[]")) if end_text.get("risk_factors") else []

        new_risk = [r for r in end_risk if r not in start_risk]
        resolved_risk = [r for r in start_risk if r not in end_risk]
        trend["risk_factors_change"] = {
            "new": new_risk,
            "resolved": resolved_risk
        }

        # 关键变化描述
        if new_symptoms:
            trend["key_changes"].append(f"新增症状：{', '.join(new_symptoms)}")
        if resolved_symptoms:
            trend["key_changes"].append(f"症状缓解：{', '.join(resolved_symptoms)}")
        if new_risk:
            trend["key_changes"].append(f"新增风险因素：{', '.join(new_risk)}")
        if resolved_risk:
            trend["key_changes"].append(f"风险因素消除：{', '.join(resolved_risk)}")

        # 趋势总结
        if trend["key_changes"]:
            trend["trend_description"] = "; ".join(trend["key_changes"])
        else:
            trend["trend_description"] = "临床症状和风险因素无明显变化"

        return trend

    def _evaluate_overall_progression(self, fundus_trend, ecg_trend, clinical_trend, start_report, end_report):
        """综合评估整体病情状态"""
        # 初始化评分（负值=好转，正值=恶化）
        score = 0

        # 眼底评分（权重最高）
        score += fundus_trend.get("dr_grade_change", 0) * 3
        score += fundus_trend.get("lesion_count_change", 0) * 0.5

        # ECG评分
        if ecg_trend.get("heart_rate_change", 0) > HEART_RATE_THRESHOLD:
            score += 2
        elif ecg_trend.get("heart_rate_change", 0) < -HEART_RATE_THRESHOLD:
            score -= 2

        if ecg_trend.get("new_abnormalities"):
            score += len(ecg_trend["new_abnormalities"]) * 2
        if ecg_trend.get("resolved_abnormalities"):
            score -= len(ecg_trend["resolved_abnormalities"]) * 2

        # 临床评分
        if clinical_trend.get("new_symptoms"):
            score += len(clinical_trend["new_symptoms"]) * 1
        if clinical_trend.get("resolved_symptoms"):
            score -= len(clinical_trend["resolved_symptoms"]) * 1

        # 风险等级变化评分
        start_risk = start_report.get("overall_risk_level", "低风险")
        end_risk = end_report.get("overall_risk_level", "低风险")
        risk_score_change = RISK_WEIGHTS.get(end_risk, 1) - RISK_WEIGHTS.get(start_risk, 1)
        score += risk_score_change * 4

        # 确定最终状态
        if score <= -5:
            return "improved"  # 好转
        elif score >= 5:
            # 极高风险或关键指标严重恶化则标记为危重
            if end_risk in ["极高风险"] or fundus_trend.get("dr_grade_change", 0) >= 2:
                return "critical"
            return "worsened"  # 恶化
        else:
            return "stable"  # 稳定

    def _evaluate_risk_change(self, start_report, end_report):
        """评估风险等级变化"""
        start_risk = start_report.get("overall_risk_level", "低风险")
        end_risk = end_report.get("overall_risk_level", "低风险")

        start_weight = RISK_WEIGHTS.get(start_risk, 1)
        end_weight = RISK_WEIGHTS.get(end_risk, 1)

        change = end_weight - start_weight

        return {
            "start_risk": start_risk,
            "end_risk": end_risk,
            "change": change,
            "change_description": f"风险等级{('升高' if change > 0 else '降低' if change < 0 else '无变化')}{abs(change) if change != 0 else ''}级"
        }

    def _generate_suggestion(self, progression_result):
        """生成医生参考建议"""
        status = progression_result["progression_status"]
        key_changes = progression_result["key_changes"]
        risk_assessment = progression_result["risk_assessment"]

        base_suggestions = {
            "improved": [
                "继续当前治疗方案，维持现有用药",
                "定期复查（建议3-6个月一次）",
                "保持健康生活方式，控制血糖/血压"
            ],
            "stable": [
                "维持当前治疗方案，无需调整",
                "常规复查（建议1-3个月一次）",
                "继续监测关键指标（血糖、血压、心率）"
            ],
            "worsened": [
                "建议调整治疗方案，加强干预措施",
                "缩短复查周期（建议1个月内复查）",
                "重点关注：" + "; ".join(key_changes[:3]) if key_changes else "重点关注病情变化指标",
                "必要时请多学科会诊"
            ],
            "critical": [
                "立即调整治疗方案，建议住院治疗",
                "紧急复查所有关键指标",
                "密切监测病情变化，防止并发症",
                "组织多学科专家会诊，制定综合治疗方案"
            ]
        }

        # 补充风险相关建议
        if risk_assessment.get("change", 0) > 0:
            base_suggestions[status].append(f"风险等级升高，需加强{risk_assessment.get('end_risk')}相关干预")
        elif risk_assessment.get("change", 0) < 0:
            base_suggestions[status].append(f"风险等级降低，可适当调整监测频率")

        return "\n".join(base_suggestions[status])


# ==================== 便捷调用函数 ====================
def analyze_disease_progression(start_exam_data, end_exam_data):
    """
    便捷调用函数：分析两次检查的病情变化
    :param start_exam_data: 首次检查数据（get_report接口返回的完整数据）
    :param end_exam_data: 末次检查数据（get_report接口返回的完整数据）
    :return: 病情进展分析结果
    """
    analyzer = DiseaseProgressionAnalyzer()
    return analyzer.analyze_progression(start_exam_data, end_exam_data)


# ==================== 测试代码 ====================
if __name__ == "__main__":
    # 测试数据 - 模拟两次检查的结果
    start_exam = {
        "fundus_analysis": {
            "dr_grade": 1,
            "lesion_count": 2,
            "risk_level": "低风险"
        },
        "ecg_analysis": {
            "heart_rate": 75,
            "rhythm_type": "窦性心律",
            "abnormalities": json.dumps(["偶发房性早搏"]),
            "risk_level": "低风险"
        },
        "text_analysis": {
            "symptoms": json.dumps(["视物模糊"]),
            "risk_factors": json.dumps(["糖尿病史"]),
        },
        "comprehensive_report": {
            "overall_risk_level": "低风险"
        }
    }

    end_exam = {
        "fundus_analysis": {
            "dr_grade": 2,
            "lesion_count": 5,
            "risk_level": "中风险"
        },
        "ecg_analysis": {
            "heart_rate": 88,
            "rhythm_type": "异常心律",
            "abnormalities": json.dumps(["频发房性早搏", "ST段压低"]),
            "risk_level": "中风险"
        },
        "text_analysis": {
            "symptoms": json.dumps(["视物模糊", "胸闷", "心悸"]),
            "risk_factors": json.dumps(["糖尿病史", "高血压史"]),
        },
        "comprehensive_report": {
            "overall_risk_level": "中风险"
        }
    }

    # 执行分析
    analyzer = DiseaseProgressionAnalyzer()
    result = analyzer.analyze_progression(start_exam, end_exam)

    # 打印结果
    print("=== 病情进展分析结果 ===")
    print(f"整体状态: {PROGRESSION_STATUS_MAP[result['progression_status']]}")
    print(f"风险变化: {result['risk_assessment']['change_description']}")
    print("\n关键变化:")
    for i, change in enumerate(result['key_changes'], 1):
        print(f"  {i}. {change}")
    print(f"\n参考建议:\n{result['suggestion']}")