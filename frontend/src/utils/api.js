const BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

async function request(endpoint, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  const data = await response.json();

  if (!response.ok) {
    throw {
      status: response.status,
      ...data,
    };
  }

  return data;
}

export const api = {
  get: (endpoint) => request(endpoint, { method: "GET" }),
  post: (endpoint, body) =>
    request(endpoint, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  put: (endpoint, body) =>
    request(endpoint, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  patch: (endpoint, body) =>
    request(endpoint, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: (endpoint) =>
    request(endpoint, {
      method: "DELETE",
    }),
};

export const authApi = {
  register: (data) => api.post("/users/register/", data),
  login: (data) => api.post("/users/login/", data),
};

export const brokerApi = {
  getAngelOneCredentials: () => api.get("/users/angelone/credentials/get/"),
  saveAngelOneCredentials: (data) => api.post("/users/angelone/credentials/", data),
};

export const botApi = {
  getSectorMomentumConfig: () =>
    api.get("/users/sector-momentum/config/"),

  saveSectorMomentumConfig: (data) =>
    api.post("/users/sector-momentum/config/save/", data),

  toggleSectorMomentumBot: (is_bot_running) =>
    api.post("/users/sector-momentum/toggle/", {
      is_bot_running,
    }),
};