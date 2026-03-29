(() => {
  const loginForm = document.querySelector("#gateway-login-form");
  const loginOutput = document.querySelector("#gateway-login-output");

  const STORAGE = {
    patient: "mcds_patient_id",
    doctor: "mcds_doctor_id"
  };

  const renderOutput = (el, data, status = "success") => {
    window.App.renderJson(el, data, status);
  };

  const handleLogin = () => {
    if (!loginForm) {
      return;
    }

    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = loginForm.querySelector("button[type=submit]");
      window.App.setLoading(button, true);

      try {
        const formData = new FormData(loginForm);
        let account = String(formData.get("account") || "").trim();
        const password = String(formData.get("password") || "").trim();

        if (!account) {
          throw new Error("请输入账号");
        }

        const prefix = account.charAt(0).toUpperCase();
        if (prefix === "D" || prefix === "P") {
          account = `${prefix}${account.slice(1)}`;
        }
        if (prefix === "D") {
          if (!password) {
            throw new Error("此账号需要密码");
          }
          const data = await window.App.requestJson("/api/doctor/login", {
            method: "POST",
            body: {
              doctor_id: account,
              password
            }
          });
          localStorage.setItem(STORAGE.doctor, account);
          localStorage.removeItem(STORAGE.patient);
          renderOutput(loginOutput, data);
          window.App.toast("登录成功，正在进入平台");
          window.setTimeout(() => {
            window.location.href = "/doctor";
          }, 600);
          return;
        }

        const data = await window.App.requestJson(`/api/patient/${account}/history`);
        localStorage.setItem(STORAGE.patient, account);
        localStorage.removeItem(STORAGE.doctor);
        renderOutput(loginOutput, data);
        window.App.toast("登录成功，正在进入平台");
        window.setTimeout(() => {
          window.location.href = "/patient";
        }, 600);
      } catch (error) {
        renderOutput(loginOutput, { error: error.message }, "error");
        window.App.toast(error.message, "error");
      } finally {
        window.App.setLoading(button, false);
      }
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    handleLogin();
  });
})();
