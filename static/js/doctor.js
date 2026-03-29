(() => {
  const STORAGE = {
    doctor: "mcds_doctor_id"
  };

  const state = {
    doctorId: localStorage.getItem(STORAGE.doctor) || ""
  };

  const doctorIdFields = document.querySelectorAll("[data-doctor-id]");
  const doctorDisplay = document.getElementById("doctor-id-display");

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

  const syncDoctor = () => {
    doctorIdFields.forEach((field) => {
      field.value = state.doctorId;
    });
    if (doctorDisplay) {
      doctorDisplay.textContent = state.doctorId || "未设置";
    }
  };

  const updateDoctor = (id) => {
    state.doctorId = id || "";
    localStorage.setItem(STORAGE.doctor, state.doctorId);
    syncDoctor();
  };

  const renderOutput = (el, data, status = "success") => {
    window.App.renderJson(el, data, status);
  };

  const formToJson = (form) => {
    const data = {};
    new FormData(form).forEach((value, key) => {
      if (value === "") {
        return;
      }
      data[key] = value;
    });
    return data;
  };

  const withAuth = (options = {}) => {
    if (!state.doctorId) {
      throw new Error("请先登录医生账号");
    }
    return {
      ...options,
      headers: {
        ...(options.headers || {}),
        "X-Doctor-ID": state.doctorId
      }
    };
  };

  const parseOptionalJson = (value, label) => {
    if (!value || !value.trim()) {
      return null;
    }
    try {
      return JSON.parse(value);
    } catch (error) {
      throw new Error(`${label} 需要是有效的 JSON`);
    }
  };

  const buildQuery = (params) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      searchParams.set(key, value);
    });
    const query = searchParams.toString();
    return query ? `?${query}` : "";
  };

  const attachLogin = () => {
    const form = document.getElementById("doctor-login-form");
    const output = document.getElementById("doctor-login-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        if (payload.doctor_id) {
          const rawId = payload.doctor_id.trim();
          if (rawId) {
            const prefix = rawId.charAt(0).toUpperCase();
            payload.doctor_id = prefix === "D" ? `D${rawId.slice(1)}` : rawId;
          }
        }
        const data = await window.App.requestJson("/api/doctor/login", {
          method: "POST",
          body: payload
        });
        renderOutput(output, data);
        if (payload.doctor_id) {
          updateDoctor(payload.doctor_id);
        }
        window.App.toast("医生登录成功");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachProfile = () => {
    const fetchBtn = document.getElementById("doctor-profile-fetch");
    const form = document.getElementById("doctor-profile-form");
    const output = document.getElementById("doctor-profile-output");
    const phoneField = document.getElementById("doctor-phone");
    const emailField = document.getElementById("doctor-email");
    const specializationField = document.getElementById("doctor-specialization");

    if (fetchBtn) {
      fetchBtn.addEventListener("click", async () => {
        window.App.setLoading(fetchBtn, true);
        try {
          const data = await window.App.requestJson("/api/doctor/profile", withAuth());
          renderOutput(output, data);
          if (data.doctor) {
            if (phoneField) {
              phoneField.value = data.doctor.phone || "";
            }
            if (emailField) {
              emailField.value = data.doctor.email || "";
            }
            if (specializationField) {
              specializationField.value = data.doctor.specialization || "";
            }
          }
        } catch (error) {
          renderOutput(output, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(fetchBtn, false);
        }
      });
    }

    if (form) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button[type=submit]");
        window.App.setLoading(button, true);
        try {
          const payload = formToJson(form);
          if (Object.keys(payload).length === 0) {
            throw new Error("请至少填写一项更新内容");
          }
          const data = await window.App.requestJson("/api/doctor/profile", withAuth({
            method: "PUT",
            body: payload
          }));
          renderOutput(output, data);
          window.App.toast("资料已更新");
        } catch (error) {
          renderOutput(output, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }
  };

  const attachDashboard = () => {
    const output = document.getElementById("doctor-dashboard-output");
    const quickOutput = document.getElementById("doctor-quick-output");
    const button = document.getElementById("doctor-dashboard-btn");
    const quickBtn = document.getElementById("dashboard-refresh-btn");

    const loadDashboard = async () => {
      const data = await window.App.requestJson("/api/doctor/statistics/dashboard", withAuth());
      renderOutput(output, data);
      renderOutput(quickOutput, data);
      return data;
    };

    if (button) {
      button.addEventListener("click", async () => {
        window.App.setLoading(button, true);
        try {
          await loadDashboard();
        } catch (error) {
          renderOutput(output, { error: error.message }, "error");
          renderOutput(quickOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }

    if (quickBtn) {
      quickBtn.addEventListener("click", async () => {
        window.App.setLoading(quickBtn, true);
        try {
          await loadDashboard();
        } catch (error) {
          renderOutput(quickOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(quickBtn, false);
        }
      });
    }
  };

  const attachAiPerformance = () => {
    const output = document.getElementById("doctor-ai-performance-output");
    const quickOutput = document.getElementById("doctor-quick-output");
    const button = document.getElementById("doctor-ai-performance-btn");
    const quickBtn = document.getElementById("ai-performance-btn");

    const loadPerformance = async () => {
      const data = await window.App.requestJson("/api/doctor/statistics/ai_performance", withAuth());
      renderOutput(output, data);
      renderOutput(quickOutput, data);
      return data;
    };

    if (button) {
      button.addEventListener("click", async () => {
        window.App.setLoading(button, true);
        try {
          await loadPerformance();
        } catch (error) {
          renderOutput(output, { error: error.message }, "error");
          renderOutput(quickOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }

    if (quickBtn) {
      quickBtn.addEventListener("click", async () => {
        window.App.setLoading(quickBtn, true);
        try {
          await loadPerformance();
        } catch (error) {
          renderOutput(quickOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(quickBtn, false);
        }
      });
    }
  };

  const attachPatients = () => {
    const form = document.getElementById("doctor-patients-form");
    const output = document.getElementById("doctor-patients-output");
    const tableBody = document.getElementById("doctor-patients-table");

    if (!form) {
      return;
    }

    const renderPatients = (data) => {
      if (!tableBody) {
        return;
      }
      tableBody.innerHTML = "";
      if (!data || !Array.isArray(data.patients)) {
        return;
      }
      data.patients.forEach((patient) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${patient.patient_id || "-"}</td>
          <td>${patient.name || "-"}</td>
          <td>${patient.latest_risk_level || "-"}</td>
          <td>${patient.last_exam_date || "-"}</td>
        `;
        tableBody.appendChild(row);
      });
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const query = buildQuery(payload);
        const data = await window.App.requestJson(`/api/doctor/patients${query}`, withAuth());
        renderOutput(output, data);
        renderPatients(data);
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachAssign = () => {
    const form = document.getElementById("doctor-assign-form");
    const output = document.getElementById("doctor-assign-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const patientId = payload.patient_id;
        delete payload.patient_id;
        const data = await window.App.requestJson(`/api/doctor/patients/${patientId}/assign`, withAuth({
          method: "POST",
          body: payload
        }));
        renderOutput(output, data);
        window.App.toast("患者已分配");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachTag = () => {
    const form = document.getElementById("doctor-tag-form");
    const output = document.getElementById("doctor-tag-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const patientId = payload.patient_id;
        delete payload.patient_id;
        if (payload.expires_days) {
          payload.expires_days = Number(payload.expires_days);
        }
        const data = await window.App.requestJson(`/api/doctor/patients/${patientId}/tag`, withAuth({
          method: "POST",
          body: payload
        }));
        renderOutput(output, data);
        window.App.toast("标签已添加");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachSearch = () => {
    const form = document.getElementById("doctor-search-form");
    const output = document.getElementById("doctor-search-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const query = buildQuery(payload);
        const data = await window.App.requestJson(`/api/search${query}`);
        renderOutput(output, data);
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachReport = () => {
    const form = document.getElementById("doctor-report-form");
    const output = document.getElementById("doctor-report-output");
    const exportBtn = document.getElementById("doctor-export-btn");
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
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });

    if (exportBtn) {
      exportBtn.addEventListener("click", async () => {
        const examInput = form.querySelector("input[name=exam_id]");
        if (!examInput || !examInput.value) {
          window.App.toast("请填写检查 ID", "error");
          return;
        }
        window.App.setLoading(exportBtn, true);
        try {
          const data = await window.App.requestJson(`/api/export/report/${examInput.value}`);
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

  const attachFeedback = () => {
    const form = document.getElementById("doctor-feedback-form");
    const output = document.getElementById("doctor-feedback-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        payload.is_teaching_case = payload.is_teaching_case === "true";
        if (!payload.feedback_category) {
          delete payload.feedback_category;
        }
        const data = await window.App.requestJson("/api/doctor/feedback", withAuth({
          method: "POST",
          body: payload
        }));
        renderOutput(output, data);
        window.App.toast("反馈已提交");
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachFeedbackList = () => {
    const form = document.getElementById("doctor-feedback-list-form");
    const output = document.getElementById("doctor-feedback-list-output");
    if (!form) {
      return;
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type=submit]");
      window.App.setLoading(button, true);
      try {
        const payload = formToJson(form);
        const data = await window.App.requestJson(`/api/doctor/feedback/${payload.exam_id}`, withAuth());
        renderOutput(output, data);
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachProgression = () => {
    const form = document.getElementById("doctor-progression-form");
    const output = document.getElementById("doctor-progression-output");
    if (form) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button[type=submit]");
        window.App.setLoading(button, true);
        try {
          const payload = formToJson(form);
          const keyChanges = parseOptionalJson(payload.key_changes || "", "关键变化");
          const fundusTrend = parseOptionalJson(payload.fundus_trend || "", "眼底趋势");
          const ecgTrend = parseOptionalJson(payload.ecg_trend || "", "ECG 趋势");
          const clinicalTrend = parseOptionalJson(payload.clinical_trend || "", "临床趋势");
          if (keyChanges) {
            payload.key_changes = keyChanges;
          } else {
            delete payload.key_changes;
          }
          if (fundusTrend) {
            payload.fundus_trend = fundusTrend;
          } else {
            delete payload.fundus_trend;
          }
          if (ecgTrend) {
            payload.ecg_trend = ecgTrend;
          } else {
            delete payload.ecg_trend;
          }
          if (clinicalTrend) {
            payload.clinical_trend = clinicalTrend;
          } else {
            delete payload.clinical_trend;
          }
          const data = await window.App.requestJson("/api/doctor/progression/create", withAuth({
            method: "POST",
            body: payload
          }));
          renderOutput(output, data);
          window.App.toast("病程记录已创建");
        } catch (error) {
          renderOutput(output, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }

    const listForm = document.getElementById("doctor-progression-list-form");
    const listOutput = document.getElementById("doctor-progression-list-output");
    if (listForm) {
      listForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = listForm.querySelector("button[type=submit]");
        window.App.setLoading(button, true);
        try {
          const payload = formToJson(listForm);
          const data = await window.App.requestJson(`/api/doctor/progression/${payload.patient_id}`, withAuth());
          renderOutput(listOutput, data);
        } catch (error) {
          renderOutput(listOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }
  };

  const attachConsultation = () => {
    const requestForm = document.getElementById("doctor-consult-request-form");
    const requestOutput = document.getElementById("doctor-consult-request-output");
    if (requestForm) {
      requestForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = requestForm.querySelector("button[type=submit]");
        window.App.setLoading(button, true);
        try {
          const payload = formToJson(requestForm);
          const data = await window.App.requestJson("/api/doctor/consultation/request", withAuth({
            method: "POST",
            body: payload
          }));
          renderOutput(requestOutput, data);
          window.App.toast("会诊申请已提交");
        } catch (error) {
          renderOutput(requestOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }

    const respondForm = document.getElementById("doctor-consult-respond-form");
    const respondOutput = document.getElementById("doctor-consult-respond-output");
    if (respondForm) {
      respondForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = respondForm.querySelector("button[type=submit]");
        window.App.setLoading(button, true);
        try {
          const payload = formToJson(respondForm);
          const consultId = payload.consultation_id;
          delete payload.consultation_id;
          const data = await window.App.requestJson(`/api/doctor/consultation/${consultId}/respond`, withAuth({
            method: "POST",
            body: payload
          }));
          renderOutput(respondOutput, data);
          window.App.toast("会诊回应已提交");
        } catch (error) {
          renderOutput(respondOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }

    const listForm = document.getElementById("doctor-consult-list-form");
    const listOutput = document.getElementById("doctor-consult-list-output");
    if (listForm) {
      listForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = listForm.querySelector("button[type=submit]");
        window.App.setLoading(button, true);
        try {
          const payload = formToJson(listForm);
          const query = buildQuery(payload);
          const data = await window.App.requestJson(`/api/doctor/consultation/list${query}`, withAuth());
          renderOutput(listOutput, data);
        } catch (error) {
          renderOutput(listOutput, { error: error.message }, "error");
          window.App.toast(error.message, "error");
        } finally {
          window.App.setLoading(button, false);
        }
      });
    }
  };

  const attachTeachingCases = () => {
    const button = document.getElementById("doctor-teaching-btn");
    const output = document.getElementById("doctor-teaching-output");
    if (!button) {
      return;
    }
    button.addEventListener("click", async () => {
      window.App.setLoading(button, true);
      try {
        const data = await window.App.requestJson("/api/doctor/teaching_cases", withAuth());
        renderOutput(output, data);
      } catch (error) {
        renderOutput(output, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  const attachSessionReset = () => {
    const button = document.getElementById("doctor-session-reset");
    if (!button) {
      return;
    }
    button.addEventListener("click", () => {
      localStorage.removeItem(STORAGE.doctor);
      updateDoctor("");
      window.App.toast("医生会话已清除");
    });
  };

  const attachSwitchAccount = () => {
    const link = document.getElementById("switch-account");
    if (!link) {
      return;
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      localStorage.removeItem("mcds_doctor_id");
      localStorage.removeItem("mcds_patient_id");
      localStorage.removeItem("mcds_exam_id");
      window.location.href = "/";
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    initPanelNav();
    syncDoctor();
    attachLogin();
    attachProfile();
    attachDashboard();
    attachAiPerformance();
    attachPatients();
    attachAssign();
    attachTag();
    attachSearch();
    attachReport();
    attachFeedback();
    attachFeedbackList();
    attachProgression();
    attachConsultation();
    attachTeachingCases();
    attachSessionReset();
    attachSwitchAccount();
  });
})();
