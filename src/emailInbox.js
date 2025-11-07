import { API_BASE_URL } from "./config.js";

function handleResponse(response, fallbackMessage) {
  if (!response.ok) {
    throw new Error(fallbackMessage || `Request failed with status ${response.status}`);
  }
  return response.json();
}

export async function fetchEmails({ limit = 20, relevantOnly = true } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  if (relevantOnly !== undefined) params.set("relevant_only", relevantOnly ? "true" : "false");

  const response = await fetch(`${API_BASE_URL}/emails?${params.toString()}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  return handleResponse(response, "Не удалось загрузить письма");
}

export async function classifyEmail({ subject, sender, body }) {
  const response = await fetch(`${API_BASE_URL}/emails/classify`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({ subject, sender, body }),
  });

  const data = await handleResponse(response, "Классификация письма не удалась");
  return data.classification;
}

export async function generateProposal({ subject, body }) {
  const response = await fetch(`${API_BASE_URL}/emails/proposal`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({ subject, body }),
  });

  const data = await handleResponse(response, "Не удалось сгенерировать КП");
  return data.proposal;
}


