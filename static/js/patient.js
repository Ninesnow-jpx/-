(() => {
  const STORAGE = {
    patient: "mcds_patient_id",
    exam: "mcds_exam_id"
  };

  const state = {
    patient: localStorage.getItem(STORAGE.patient) || "",
    exam: localStorage.getItem(STORAGE.exam) || ""
  };

  const patientIdFields = document.querySelectorAll("[data-patient-id]");
  const examIdFields = document.querySelectorAll("[data-exam-id]");
  const patientDisplay = document.getElementById("patient-id-display");
  const examDisplay = document.getElementById("exam-id-display");
  const summaryEl = document.getElementById("analysis-summary");
  const historyList = document.getElementById("history-list");
  const resetBtn = document.getElementById("session-reset");

  const initPanelNav = () => {
    const navItems = Array.from(document.querySelectorAll("[data-panel-target]"));
    const panels = Array.from(document.querySelectorAll("[data-panel]"));
    if (!navItems.length || !panels.length) {
      return;
    }

    const activate = (target) => {
      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.panel === target);
      });
      navItems.forEach((item) => {
        item.classList.toggle("is-active", item.dataset.panelTarget === target);
      });
    };

    navItems.forEach((item) => {
      item.addEventListener("click", () => {
        activate(item.dataset.panelTarget);
      });
    });

    const jumpItems = document.querySelectorAll("[data-panel-jump]");
    jumpItems.forEach((item) => {
      item.addEventListener("click", (event) => {
        event.preventDefault();
        const target = item.dataset.panelJump;
        if (target) {
          activate(target);
        }
      });
    });

    const hash = window.location.hash.replace("#", "");
    const initial =
      navItems.find((item) => item.dataset.panelTarget === hash) ||
      navItems.find((item) => item.classList.contains("is-active")) ||
      navItems[0];
    if (initial) {
      activate(initial.dataset.panelTarget);
    }
  };

  const syncFields = () => {
    patientIdFields.forEach((field) => {
      field.value = state.patient;
    });
    examIdFields.forEach((field) => {
      field.value = state.exam;
    });
    if (patientDisplay) {
      patientDisplay.textContent = state.patient || "未设置";
    }
    if (examDisplay) {
      examDisplay.textContent = state.exam || "未设置";
    }
  };

  const updateState = (key, value) => {
    state[key] = value || "";
    localStorage.setItem(STORAGE[key], state[key]);
    syncFields();
  };

  const formToJson = (form) => {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (value === "") {
        return;
      }
      data[key] = value;
    });
    if (data.age) {
      data.age = Number(data.age);
    }
    return data;
  };

  const renderOutput = (el, data, status = "success") => {
    window.App.renderJson(el, data, status);
  };

  const renderSummary = (payload) => {
    if (!summaryEl) {
      return;
    }
    const report = payload?.comprehensive_report || payload?.report || payload;
    if (!report || typeof report !== "object") {
      summaryEl.textContent = "暂无分析结果。";
      return;
    }
    const risk = report.overall_risk_level || "-";
    const primary = report.primary_diagnosis || "-";
    const secondary = report.secondary_diagnosis || "-";
    const confidence = report.confidence ?? "-";
    summaryEl.textContent = `风险: ${risk} | 主要诊断: ${primary} | 次要诊断: ${secondary} | 置信度: ${confidence}`;
  };

  const renderHistory = (data) => {
    if (!historyList) {
      return;
    }
    historyList.innerHTML = "";
    if (!data || !Array.isArray(data.history)) {
      return;
    }
    data.history.forEach((item) => {
      const li = document.createElement("li");
      const date = item.exam_date ? new Date(item.exam_date).toLocaleString() : "-";
      li.innerHTML = `<span>${item.exam_id || "-"} | ${date}</span><span>${item.status || "-"}</span>`;
      historyList.appendChild(li);
    });
  };

  const handleRegister = () => {
    const form = document.getElementById("patient-register-form");
    const output = document.getElementById("patient-register-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson("/api/patient/register", {
          method: "POST",
          body: payload
        });
        renderOutput(output, data);
        if (data.patient_id) {
          updateState("patient", data.patient_id);
          window.App.toast("患者注册成功");
        }
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const handleLogin = () => {
    const form = document.getElementById("patient-login-form");
    const output = document.getElementById("patient-login-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson(`/api/patient/${payload.patient_id}/history`);
        renderOutput(output, data);
        updateState("patient", payload.patient_id);
        window.App.toast("患者验证成功");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const handleExamCreate = () => {
    const form = document.getElementById("create-exam-form");
    const output = document.getElementById("create-exam-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson("/api/examination/create", {
          method: "POST",
          body: payload
        });
        renderOutput(output, data);
        if (data.exam_id) {
          updateState("exam", data.exam_id);
          window.App.toast("检查记录已创建");
        }
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const handleUpload = (formId, endpoint, outputId) => {
    const form = document.getElementById(formId);
    const output = document.getElementById(outputId);
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const formData = new FormData(form);
        const data = await window.App.requestJson(endpoint, {
          method: "POST",
          body: formData
        });
        renderOutput(output, data);
        window.App.toast("上传完成");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const handleAnalysis = () => {
    const form = document.getElementById("analysis-form");
    const output = document.getElementById("analysis-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson(`/api/analyze/${payload.exam_id}`, {
          method: "POST"
        });
        renderOutput(output, data);
        renderSummary(data.comprehensive_report || data);
        window.App.toast("分析完成");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const handleReport = () => {
    const form = document.getElementById("report-form");
    const output = document.getElementById("report-output");
    const exportBtn = document.getElementById("report-export-btn");
    if (!form) {
      return;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson(`/api/report/${payload.exam_id}`);
        renderOutput(output, data);
        renderSummary(data.comprehensive_report || data);
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });

    if (exportBtn) {
      exportBtn.addEventListener("click", async () => {
        const examIdInput = form.querySelector("input[name=exam_id]");
        if (!examIdInput || !examIdInput.value) {
          window.App.toast("请填写检查 ID", "error");
          return;
        }
        window.App.setLoading(exportBtn, true);
        try {
          const data = await window.App.requestJson(`/api/export/report/${examIdInput.value}`);
          renderOutput(output, data);
          window.App.toast("报告已导出");
        } catch (error) {
          renderOutput(output, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(exportBtn, false);
        }
      });
    }
  };

  const handleHistory = () => {
    const form = document.getElementById("history-form");
    const output = document.getElementById("history-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson(`/api/patient/${payload.patient_id}/history`);
        renderOutput(output, data);
        renderHistory(data);
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const handleReset = () => {
    if (!resetBtn) {
      return;
    }
    resetBtn.addEventListener("click", () => {
      localStorage.removeItem(STORAGE.patient);
      localStorage.removeItem(STORAGE.exam);
      state.patient = "";
      state.exam = "";
      syncFields();
      if (summaryEl) {
        summaryEl.textContent = "暂无分析结果。";
      }
      if (historyList) {
        historyList.innerHTML = "";
      }
      window.App.toast("会话已清除");
    });
  };

  const handleSwitchAccount = () => {
    const link = document.getElementById("switch-account");
    if (!link) {
      return;
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      localStorage.removeItem(STORAGE.patient);
      localStorage.removeItem(STORAGE.exam);
      localStorage.removeItem("mcds_doctor_id");
      window.location.href = "/";
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    initPanelNav();
    syncFields();
    handleRegister();
    handleLogin();
    handleExamCreate();
    handleUpload("fundus-upload-form", "/api/upload/fundus", "fundus-upload-output");
    handleUpload("ecg-upload-form", "/api/upload/ecg", "ecg-upload-output");
    handleUpload("text-upload-form", "/api/upload/medical_text", "text-upload-output");
    handleAnalysis();
    handleReport();
    handleHistory();
    handleReset();
    handleSwitchAccount();
  });
})();
