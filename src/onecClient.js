import { getApiBaseUrl } from "./config.js";

function handleResponse(response, fallbackMessage) {
  if (!response.ok) {
    throw new Error(fallbackMessage || `Request failed with status ${response.status}`);
  }
  return response.json();
}

export async function createInvoice(payload) {
  const response = await fetch(`${getApiBaseUrl()}/integrations/1c/invoices`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response, "Не удалось создать счёт в 1С");
}

export async function createFulfillment(payload) {
  const response = await fetch(`${getApiBaseUrl()}/integrations/1c/fulfillment`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response, "Не удалось создать накладную и акт в 1С");
}

export async function getInvoicePdf(ref) {
  const response = await fetch(`${getApiBaseUrl()}/integrations/1c/invoices/${ref}/pdf`, {
    method: "GET",
  });

  if (!response.ok) {
    throw new Error("Не удалось получить PDF счёта");
  }

  const blob = await response.blob();
  return blob;
}

export async function getRealizationPdf(ref) {
  const response = await fetch(`${getApiBaseUrl()}/integrations/1c/realizations/${ref}/pdf`, {
    method: "GET",
  });

  if (!response.ok) {
    throw new Error("Не удалось получить PDF накладной/акта");
  }

  const blob = await response.blob();
  return blob;
}

