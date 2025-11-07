import { API_BASE_URL } from "./config.js";

function handleResponse(response, fallbackMessage) {
  if (!response.ok) {
    throw new Error(fallbackMessage || `Request failed with status ${response.status}`);
  }
  return response.json();
}

export async function registerInteraction(payload) {
  const response = await fetch(`${API_BASE_URL}/crm/interactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response, "Не удалось создать сделку в amoCRM");
}

export async function ensureDocumentTasks(leadId, documents, responsibleUserId) {
  const body = {
    documents,
  };
  if (responsibleUserId) {
    body.responsible_user_id = responsibleUserId;
  }

  const response = await fetch(`${API_BASE_URL}/crm/leads/${leadId}/documents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(body),
  });

  return handleResponse(response, "Не удалось обновить задачи по документам");
}


