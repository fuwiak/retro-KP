"use strict";

import { getApiBaseUrl } from "./config.js";
import * as emailInbox from "./emailInbox.js";
import * as crmClient from "./crmClient.js";
import * as onecClient from "./onecClient.js";

const els = {
  colorPicker: document.getElementById("colorPicker"),
  statusLine: document.getElementById("statusLine"),
  logToggle: document.getElementById("logToggle"),
  logDrawer: document.getElementById("logDrawer"),
  logArea: document.getElementById("logArea"),
  logClose: document.getElementById("logClose"),
  onecToggle: document.getElementById("onecToggle"),
  onecDrawer: document.getElementById("onecDrawer"),
  onecClose: document.getElementById("onecClose"),
  crmRefreshBtn: document.getElementById("crmRefreshBtn"),
  crmMockToggleBtn: document.getElementById("crmMockToggleBtn"),
  crmRelevantOnly: document.getElementById("crmRelevantOnly"),
  crmEmailLimit: document.getElementById("crmEmailLimit"),
  crmChannel: document.getElementById("crmChannel"),
  crmResponsibleId: document.getElementById("crmResponsibleId"),
  crmFollowUpHours: document.getElementById("crmFollowUpHours"),
  crmStatus: document.getElementById("crmStatus"),
  crmEmailList: document.getElementById("crmEmailList"),
  crmSubject: document.getElementById("crmSubject"),
  crmSender: document.getElementById("crmSender"),
  crmDate: document.getElementById("crmDate"),
  crmEmailBody: document.getElementById("crmEmailBody"),
  crmClassifyBtn: document.getElementById("crmClassifyBtn"),
  crmProposalBtn: document.getElementById("crmProposalBtn"),
  crmCopyProposalBtn: document.getElementById("crmCopyProposalBtn"),
  crmClassification: document.getElementById("crmClassification"),
  crmProposalText: document.getElementById("crmProposalText"),
  crmContactName: document.getElementById("crmContactName"),
  crmContactEmail: document.getElementById("crmContactEmail"),
  crmContactPhone: document.getElementById("crmContactPhone"),
  crmContactCompany: document.getElementById("crmContactCompany"),
  crmDocProposal: document.getElementById("crmDocProposal"),
  crmDocInvoice: document.getElementById("crmDocInvoice"),
  crmDocContract: document.getElementById("crmDocContract"),
  crmDocClosing: document.getElementById("crmDocClosing"),
  crmSendBtn: document.getElementById("crmSendToCrm"),
  // 1C Integration elements
  onecLeadId: document.getElementById("onecLeadId"),
  onecContactId: document.getElementById("onecContactId"),
  onecCustomerName: document.getElementById("onecCustomerName"),
  onecCustomerBin: document.getElementById("onecCustomerBin"),
  onecInvoiceCurrency: document.getElementById("onecInvoiceCurrency"),
  onecInvoiceDueDate: document.getElementById("onecInvoiceDueDate"),
  onecInvoiceItems: document.getElementById("onecInvoiceItems"),
  onecCreateInvoiceBtn: document.getElementById("onecCreateInvoiceBtn"),
  onecInvoiceStatus: document.getElementById("onecInvoiceStatus"),
  onecDeliveryAddress: document.getElementById("onecDeliveryAddress"),
  onecFulfillmentItems: document.getElementById("onecFulfillmentItems"),
  onecCreateFulfillmentBtn: document.getElementById("onecCreateFulfillmentBtn"),
  onecFulfillmentStatus: document.getElementById("onecFulfillmentStatus"),
};

function log(message, ...args) {
  const time = new Date().toLocaleTimeString();
  if (els.logArea) {
    const line = document.createElement("div");
    line.innerHTML = `[${time}] ${message}`;
    els.logArea.appendChild(line);
    els.logArea.scrollTop = els.logArea.scrollHeight;
  }
  console.log(message, ...args);
}

let humAudio = null;

function playClick(pitch = 440) {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "square";
  osc.frequency.value = pitch;
  gain.gain.value = 0.05;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.1);
}

function startHum() {
  if (humAudio) return;
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = 55;
  gain.gain.value = 0.02;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  humAudio = { ctx, osc, gain };
}

function attachRetroSoundEffects(root = document) {
  const buttons = [];
  if (root instanceof HTMLButtonElement) {
    buttons.push(root);
  }
  if (typeof root.querySelectorAll === "function") {
    root.querySelectorAll("button").forEach((button) => buttons.push(button));
  }
  buttons.forEach((button) => {
    if (button.dataset.retroSoundAttached === "true") {
    return;
  }
    button.dataset.retroSoundAttached = "true";
    button.addEventListener("pointerdown", () => {
      const basePitch = 320 + Math.random() * 220;
      playClick(basePitch);
    });
  });
}

function setThemeColor(color) {
  if (!color) return;
  document.documentElement.style.setProperty("--ui-color", color);
  log(`🎨 Theme color changed to ${color}`);
}

function setCrmStatus(message = "", tone = "info") {
  const palette = {
    info: "var(--ui-color)",
    success: "rgb(0, 255, 128)",
    error: "rgb(255, 120, 120)",
  };
  const color = palette[tone] || palette.info;
  if (els.crmStatus) {
    els.crmStatus.textContent = message;
    els.crmStatus.style.color = color;
  }
  if (els.statusLine) {
    els.statusLine.textContent = message ? `ℹ ${message}` : "";
    els.statusLine.style.color = color;
  }
}

const crmState = {
  emails: [],
  selectedIndex: null,
  relevantOnly: els.crmRelevantOnly ? els.crmRelevantOnly.checked : true,
  limit: els.crmEmailLimit ? Number(els.crmEmailLimit.value) || 20 : 20,
  loading: false,
  classification: new Map(),
  proposals: new Map(),
  drafts: new Map(),
  completed: new Set(),
  mockMode: false,
};

function getSelectedEmail() {
  if (crmState.selectedIndex === null) return null;
  return crmState.emails[crmState.selectedIndex] || null;
}

function formatEmailDate(input) {
  if (!input) return "—";
  try {
    const value = new Date(input);
    if (Number.isNaN(value.getTime())) return input;
    return value.toLocaleString();
  } catch (error) {
    return input;
  }
}

function parseSender(sender = "") {
  const result = { name: "", email: "", phone: "" };
  if (!sender) return result;

  const emailMatch = sender.match(/<([^>]+)>/);
  if (emailMatch) {
    result.email = emailMatch[1].trim();
    result.name = sender.replace(emailMatch[0], "").replace(/"/g, "").trim();
  } else if (sender.includes("@")) {
    const segments = sender.split(/[\s,]/);
    const emailCandidate = segments.find((segment) => segment.includes("@"));
    if (emailCandidate) {
      result.email = emailCandidate.replace(/["<>]/g, "").trim();
    }
    result.name = sender.replace(result.email, "").replace(/"/g, "").trim();
    } else {
    result.name = sender.trim();
  }

  if (!result.name && result.email) {
    result.name = result.email.split("@")[0];
  }

  const phoneMatch = sender.match(/\+?[\d\s().-]{7,}/);
  if (phoneMatch) {
    result.phone = phoneMatch[0].trim();
  }

  return result;
}

async function populateOnecFields(email, contactDefaults) {
  if (!email) return;
  
  // Fill customer name from company or contact name
  if (els.onecCustomerName) {
    const company = email.extractedCompany || contactDefaults?.company || els.crmContactCompany?.value || "";
    const contactName = contactDefaults?.name || els.crmContactName?.value || "";
    els.onecCustomerName.value = company || contactName || "";
  }
  
  // Fill customer BIN if available (could be extracted from email in future)
  // For now, leave empty as it's usually not in emails
  
  // Note: lead_id and contact_id will be filled after sending to CRM
}

function populateDefaultContact(email) {
  const defaults = { name: "", email: "", phone: "", company: "" };
  if (!email) return defaults;

  const parsed = parseSender(email.sender || "");
  defaults.name = parsed.name || email.subject || "Клиент";
  defaults.email = parsed.email || "";
  defaults.phone = parsed.phone || "";
  defaults.company = "";

  // Try to extract phone and company from email body
  const emailText = (email.fullBody || email.bodyPreview || "").trim();
  if (emailText) {
    // Extract phone using regex
    const phonePatterns = [
      /\+?7\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}/g, // +7 (XXX) XXX-XX-XX
      /\+?7\s?\d{10}/g, // +7XXXXXXXXXX
      /\+?\d{1,3}[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}/g, // International
    ];
    
    for (const pattern of phonePatterns) {
      const matches = emailText.match(pattern);
      if (matches && matches.length > 0) {
        defaults.phone = matches[0].replace(/\s/g, "").trim();
        break;
      }
    }

    // Extract company name using regex patterns
    const companyPatterns = [
      /(?:ООО|ТОО|ИП|АО|ЗАО|ПАО)\s*["«]?([^"»\n,]+)["»]?/i,
      /(?:компания|фирма|организация)\s*["«]?([^"»\n,]+)["»]?/i,
      /["«]([^"»\n,]{3,30})["»]/,
    ];

    for (const pattern of companyPatterns) {
      const match = emailText.match(pattern);
      if (match && match[1]) {
        defaults.company = match[1].trim();
        break;
      }
    }
  }

  return defaults;
}

function renderCrmClassification(emailId) {
  if (!els.crmClassification) return;
  if (!emailId) {
    els.crmClassification.textContent = "AI-анализ будет показан здесь.";
    return;
  }
  const cls = crmState.classification.get(emailId);
  if (!cls) {
    els.crmClassification.textContent = "AI-анализ еще не выполнен.";
    return;
  }
  const lines = [];
  lines.push(`<strong>Категория:</strong> ${cls.category || "—"}`);
  if (typeof cls.confidence === "number") {
    lines.push(`<strong>Уверенность:</strong> ${(cls.confidence * 100).toFixed(1)}%`);
  }
  lines.push(`<strong>Готово для КП:</strong> ${cls.suitable_for_proposal ? "✅ Да" : "⚠️ Проверить вручную"}`);
  if (cls.reason) {
    lines.push(`<strong>Пояснение:</strong> ${cls.reason}`);
  }
  if (Array.isArray(cls.potential_services) && cls.potential_services.length) {
    lines.push(`<strong>Услуги:</strong> ${cls.potential_services.join(", ")}`);
  }
  els.crmClassification.innerHTML = lines.join("\n");
}

function applyDraftOrDefaults(email) {
  if (!els.crmContactName) return;
  if (!email) {
    els.crmContactName.value = "";
    if (els.crmContactEmail) els.crmContactEmail.value = "";
    if (els.crmContactPhone) els.crmContactPhone.value = "";
    if (els.crmContactCompany) els.crmContactCompany.value = "";
    if (els.crmChannel) els.crmChannel.value = "email";
    if (els.crmFollowUpHours) els.crmFollowUpHours.value = "4";
    if (els.crmResponsibleId) els.crmResponsibleId.value = "";
    if (els.crmDocProposal) els.crmDocProposal.checked = false;
    if (els.crmDocInvoice) els.crmDocInvoice.checked = false;
    if (els.crmDocContract) els.crmDocContract.checked = false;
    if (els.crmDocClosing) els.crmDocClosing.checked = false;
    if (els.crmProposalText) els.crmProposalText.value = "";
      return;
    }

  const draft = crmState.drafts.get(email.id);
  if (draft) {
    els.crmContactName.value = draft.contactName || "";
    if (els.crmContactEmail) els.crmContactEmail.value = draft.contactEmail || "";
    if (els.crmContactPhone) els.crmContactPhone.value = draft.contactPhone || "";
    if (els.crmContactCompany) els.crmContactCompany.value = draft.contactCompany || "";
    if (els.crmChannel && draft.channel) els.crmChannel.value = draft.channel;
    if (els.crmFollowUpHours && draft.followUpHours) els.crmFollowUpHours.value = draft.followUpHours;
    if (els.crmResponsibleId) els.crmResponsibleId.value = draft.responsibleId || "";
    if (els.crmDocProposal) els.crmDocProposal.checked = !!draft.documents?.proposal_sent;
    if (els.crmDocInvoice) els.crmDocInvoice.checked = !!draft.documents?.invoice_sent;
    if (els.crmDocContract) els.crmDocContract.checked = !!draft.documents?.contract_signed;
    if (els.crmDocClosing) els.crmDocClosing.checked = !!draft.documents?.closing_documents_ready;
    if (els.crmProposalText) {
      const proposal = draft.proposalText ?? crmState.proposals.get(email.id) ?? "";
      els.crmProposalText.value = proposal;
    }
    return;
  }

  // Use async populateDefaultContact
  populateDefaultContact(email).then((defaults) => {
    els.crmContactName.value = defaults.name;
    if (els.crmContactEmail) els.crmContactEmail.value = defaults.email;
    if (els.crmContactPhone) els.crmContactPhone.value = defaults.phone;
    if (els.crmContactCompany) els.crmContactCompany.value = defaults.company;
  });
  if (els.crmChannel) els.crmChannel.value = "email";
  if (els.crmFollowUpHours) els.crmFollowUpHours.value = els.crmFollowUpHours.value || "4";
  if (els.crmResponsibleId) els.crmResponsibleId.value = "";
  if (els.crmDocProposal) els.crmDocProposal.checked = false;
  if (els.crmDocInvoice) els.crmDocInvoice.checked = false;
  if (els.crmDocContract) els.crmDocContract.checked = false;
  if (els.crmDocClosing) els.crmDocClosing.checked = false;
  if (els.crmProposalText) {
    const proposal = crmState.proposals.get(email.id) || "";
    els.crmProposalText.value = proposal;
  }
}

function renderCrmDetail() {
  const email = getSelectedEmail();
  const hasEmail = !!email;

  if (els.crmClassifyBtn) els.crmClassifyBtn.disabled = !hasEmail;
  if (els.crmProposalBtn) els.crmProposalBtn.disabled = !hasEmail;
  if (els.crmCopyProposalBtn) els.crmCopyProposalBtn.disabled = !hasEmail;
  if (els.crmSendBtn) els.crmSendBtn.disabled = !hasEmail;

  if (!email) {
    if (els.crmSubject) els.crmSubject.textContent = "—";
    if (els.crmSender) els.crmSender.textContent = "—";
    if (els.crmDate) els.crmDate.textContent = "—";
    if (els.crmEmailBody) els.crmEmailBody.value = "";
    renderCrmClassification(null);
    applyDraftOrDefaults(null);
    return;
  }
  
  if (els.crmSubject) els.crmSubject.textContent = email.subject || "(без темы)";
  if (els.crmSender) els.crmSender.textContent = email.sender || "—";
  if (els.crmDate) els.crmDate.textContent = formatEmailDate(email.date);
  if (els.crmEmailBody) els.crmEmailBody.value = email.fullBody || email.bodyPreview || "";

  applyDraftOrDefaults(email);
  renderCrmClassification(email.id);
}

function renderCrmEmailList() {
  if (!els.crmEmailList) return;
  if (!crmState.emails.length) {
    els.crmEmailList.innerHTML = `<p style="opacity: 0.6; text-align: center;">Нет писем для отображения</p>`;
    return;
  }
  
  const items = crmState.emails.map((email, index) => {
    const cls = crmState.classification.get(email.id);
    const classes = ["crm-email-item"];
    if (index === crmState.selectedIndex) classes.push("active");
    if (crmState.completed.has(email.id)) classes.push("processed");
    const tag = cls?.category || email.nlpCategory;
    return `
      <div class="${classes.join(" ")}" data-crm-index="${index}">
        <div class="crm-email-subject">${email.subject || "(без темы)"}</div>
        <div class="crm-email-meta">${email.sender || "Неизвестно"}</div>
        <div class="crm-email-meta">${formatEmailDate(email.date)}</div>
        <div class="crm-email-tag">${tag || "не классифицировано"}</div>
      </div>
    `;
  });

  els.crmEmailList.innerHTML = items.join("");
}

function saveCurrentDraft() {
  const email = getSelectedEmail();
  if (!email || !els.crmContactName) return;

  const draft = {
    contactName: els.crmContactName.value || "",
    contactEmail: els.crmContactEmail ? els.crmContactEmail.value : "",
    contactPhone: els.crmContactPhone ? els.crmContactPhone.value : "",
    contactCompany: els.crmContactCompany ? els.crmContactCompany.value : "",
    channel: els.crmChannel ? els.crmChannel.value : "email",
    followUpHours: els.crmFollowUpHours ? els.crmFollowUpHours.value : "4",
    responsibleId: els.crmResponsibleId ? els.crmResponsibleId.value : "",
    documents: {
      proposal_sent: !!(els.crmDocProposal && els.crmDocProposal.checked),
      invoice_sent: !!(els.crmDocInvoice && els.crmDocInvoice.checked),
      contract_signed: !!(els.crmDocContract && els.crmDocContract.checked),
      closing_documents_ready: !!(els.crmDocClosing && els.crmDocClosing.checked),
    },
    proposalText: els.crmProposalText ? els.crmProposalText.value : "",
  };

  crmState.drafts.set(email.id, draft);
  if (els.crmProposalText) {
    crmState.proposals.set(email.id, els.crmProposalText.value);
  }
}

function selectCrmEmail(index) {
  if (!Number.isInteger(index) || index < 0 || index >= crmState.emails.length) return;
  const previous = getSelectedEmail();
  if (previous) {
    saveCurrentDraft();
  }
  crmState.selectedIndex = index;
  renderCrmEmailList();
  renderCrmDetail();
}

function attachCrmDraftListeners() {
  const draftInputs = [
    els.crmContactName,
    els.crmContactEmail,
    els.crmContactPhone,
    els.crmContactCompany,
    els.crmResponsibleId,
  ].filter(Boolean);
  draftInputs.forEach((input) => {
    input.addEventListener("input", saveCurrentDraft);
  });

  if (els.crmFollowUpHours) {
    els.crmFollowUpHours.addEventListener("change", saveCurrentDraft);
    els.crmFollowUpHours.addEventListener("input", saveCurrentDraft);
  }

  if (els.crmChannel) {
    els.crmChannel.addEventListener("change", saveCurrentDraft);
  }

  [els.crmDocProposal, els.crmDocInvoice, els.crmDocContract, els.crmDocClosing]
    .filter(Boolean)
    .forEach((checkbox) => checkbox.addEventListener("change", saveCurrentDraft));

  if (els.crmProposalText) {
    els.crmProposalText.addEventListener("input", () => {
      const email = getSelectedEmail();
      if (email) {
        crmState.proposals.set(email.id, els.crmProposalText.value);
      }
      saveCurrentDraft();
    });
  }
}

async function refreshCrmInbox() {
  if (!els.crmEmailList) return;
  if (crmState.loading) return;
  crmState.loading = true;

  setCrmStatus("Загрузка писем...");
  try {
    const previous = getSelectedEmail();
    const previousId = previous ? previous.id : null;
    const emails = await emailInbox.fetchEmails({
      limit: crmState.limit,
      relevantOnly: crmState.relevantOnly,
    });

    if (!Array.isArray(emails)) {
      throw new Error("Сервер вернул неверный формат данных");
    }

    crmState.emails = emails;
    let newIndex = null;
    if (previousId) {
      const found = emails.findIndex((email) => email.id === previousId);
      if (found !== -1) {
        newIndex = found;
      }
    }
    if (newIndex === null && emails.length) {
      newIndex = 0;
    }

    crmState.selectedIndex = newIndex;
    renderCrmEmailList();
    renderCrmDetail();

    if (emails.length) {
      setCrmStatus(`Загружено ${emails.length} писем`, "success");
      log(`📬 Загружено ${emails.length} писем из IMAP (API ${getApiBaseUrl()})`);
    } else {
      setCrmStatus("Нет писем для отображения", "info");
      log("ℹ️ Писем не найдено (возможно, все отфильтрованы или IMAP пуст)");
    }
  } catch (error) {
    console.error("Email fetch error:", error);
    const errorMsg = error.message || "Не удалось загрузить письма";
    setCrmStatus(errorMsg, "error");
    log(`❌ Ошибка загрузки писем: ${errorMsg}`);
    
    // Clear email list on error
    crmState.emails = [];
    crmState.selectedIndex = null;
    renderCrmEmailList();
    renderCrmDetail();
  } finally {
    crmState.loading = false;
    if (els.crmRefreshBtn) {
      els.crmRefreshBtn.disabled = false;
    }
  }
}

async function handleCrmClassification() {
  const email = getSelectedEmail();
  if (!email || !els.crmClassifyBtn) {
    setCrmStatus("Выберите письмо для анализа", "error");
    return;
  }
  els.crmClassifyBtn.disabled = true;
  setCrmStatus("AI анализирует письмо...");
  try {
    const result = await emailInbox.classifyEmail({
      subject: email.subject || "",
      sender: email.sender || "",
      body: email.fullBody || email.bodyPreview || "",
    });
    crmState.classification.set(email.id, result);
    renderCrmClassification(email.id);
    renderCrmEmailList();
    setCrmStatus("Готово: письмо классифицировано", "success");
    log(`🤖 Письмо классифицировано (${result.category || "unknown"})`);
  } catch (error) {
    console.error(error);
    setCrmStatus(error.message || "Ошибка классификации", "error");
    log(`❌ Ошибка классификации письма: ${error.message || error}`);
  } finally {
    els.crmClassifyBtn.disabled = false;
  }
}

async function handleCrmProposal() {
  const email = getSelectedEmail();
  if (!email || !els.crmProposalBtn) {
    setCrmStatus("Выберите письмо для генерации КП", "error");
    return;
  }
  els.crmProposalBtn.disabled = true;
  setCrmStatus("Генерируем КП...");
  try {
    const proposal = await emailInbox.generateProposal({
      subject: email.subject || "",
      body: email.fullBody || email.bodyPreview || "",
    });
    crmState.proposals.set(email.id, proposal);
    if (els.crmProposalText) {
      els.crmProposalText.value = proposal;
    }
    saveCurrentDraft();
    setCrmStatus("КП готово", "success");
    log("📝 КП сгенерировано автоматически");
    if (els.crmCopyProposalBtn) {
      els.crmCopyProposalBtn.disabled = false;
    }
  } catch (error) {
    console.error(error);
    setCrmStatus(error.message || "Ошибка генерации КП", "error");
    log(`❌ Ошибка генерации КП: ${error.message || error}`);
  } finally {
    els.crmProposalBtn.disabled = false;
  }
}

async function handleCrmCopyProposal() {
  if (!els.crmProposalText) return;
  const text = (els.crmProposalText.value || "").trim();
  if (!text) {
    setCrmStatus("Нет текста КП для копирования", "error");
    return;
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const tempArea = document.createElement("textarea");
      tempArea.value = text;
      tempArea.style.position = "fixed";
      tempArea.style.opacity = "0";
      document.body.appendChild(tempArea);
      tempArea.select();
      document.execCommand("copy");
      document.body.removeChild(tempArea);
    }
    setCrmStatus("КП скопировано в буфер", "success");
  } catch (error) {
    console.error(error);
    setCrmStatus("Не удалось скопировать КП", "error");
  }
}

async function handleCrmSend() {
  const email = getSelectedEmail();
  if (!email || !els.crmSendBtn) {
    setCrmStatus("Выберите письмо для отправки", "error");
    return;
  }
  
  const contactName = (els.crmContactName?.value || "").trim() || "Клиент";
  
  const contactEmail = (els.crmContactEmail?.value || "").trim();
  const contactPhone = (els.crmContactPhone?.value || "").trim();
  const contactCompany = (els.crmContactCompany?.value || "").trim();
  const channel = els.crmChannel ? els.crmChannel.value : "email";
  const followUp = els.crmFollowUpHours ? parseInt(els.crmFollowUpHours.value, 10) : 4;
  const responsibleId = els.crmResponsibleId && els.crmResponsibleId.value ? Number(els.crmResponsibleId.value) : undefined;
  const proposalText = (els.crmProposalText?.value || "").trim();

  const documents = {
    proposal_sent: !!(els.crmDocProposal && els.crmDocProposal.checked),
    invoice_sent: !!(els.crmDocInvoice && els.crmDocInvoice.checked),
    contract_signed: !!(els.crmDocContract && els.crmDocContract.checked),
    closing_documents_ready: !!(els.crmDocClosing && els.crmDocClosing.checked),
  };

  const classification = crmState.classification.get(email.id);
  const metadata = {
    nlp_category: email.nlpCategory,
    sender: email.sender,
  };
  if (classification) {
    metadata.category = classification.category;
    metadata.confidence = classification.confidence;
    metadata.suitable_for_proposal = classification.suitable_for_proposal;
    if (classification.potential_services?.length) {
      metadata.potential_services = classification.potential_services;
    }
  }
  if (proposalText) {
    metadata.proposal_preview = proposalText.slice(0, 500);
  }

  els.crmSendBtn.disabled = true;
  setCrmStatus("Отправляем данные в amoCRM...");

  try {
    const payload = {
      channel,
      subject: email.subject || "(без темы)",
      message: email.fullBody || email.bodyPreview || "",
      contact: {
        name: contactName,
        email: contactEmail || undefined,
        phone: contactPhone || undefined,
        company: contactCompany || undefined,
      },
      source_id: String(email.id),
      direction: "incoming",
      metadata,
      documents,
      responsible_user_id: responsibleId,
      follow_up_hours: Number.isFinite(followUp) && followUp > 0 ? followUp : 4,
    };

    const result = await crmClient.registerInteraction(payload);
    crmState.completed.add(email.id);
    
    // Save CRM IDs for 1C integration
    if (result.contact_id && els.onecContactId) {
      els.onecContactId.value = result.contact_id;
    }
    if (result.lead_id && els.onecLeadId) {
      els.onecLeadId.value = result.lead_id;
    }
    
    saveCurrentDraft();
    renderCrmEmailList();
    setCrmStatus(`amoCRM: контакт ${result.contact_id}, сделка ${result.lead_id}`, "success");
    log(`✅ amoCRM обновлено: контакт ${result.contact_id}, сделка ${result.lead_id}`);
  } catch (error) {
    console.error(error);
    setCrmStatus(error.message || "Не удалось создать сделку", "error");
    log(`❌ Ошибка amoCRM: ${error.message || error}`);
  } finally {
    els.crmSendBtn.disabled = false;
  }
}

// ========== EVENT WIRING ==========

if (els.colorPicker) {
  els.colorPicker.addEventListener("input", (event) => setThemeColor(event.target.value));
}

if (els.logToggle && els.logDrawer) {
  els.logToggle.addEventListener("click", () => {
    els.logDrawer.style.bottom = els.logDrawer.style.bottom === "40px" ? "-320px" : "40px";
  });
}

if (els.logClose && els.logDrawer) {
  els.logClose.addEventListener("click", () => {
    els.logDrawer.style.bottom = "-320px";
  });
}

// 1C Integration drawer toggle
if (els.onecToggle && els.onecDrawer) {
  els.onecToggle.addEventListener("click", () => {
    els.onecDrawer.style.bottom = els.onecDrawer.style.bottom === "40px" ? "-500px" : "40px";
  });
}

if (els.onecClose && els.onecDrawer) {
  els.onecClose.addEventListener("click", () => {
    els.onecDrawer.style.bottom = "-500px";
  });
}

if (els.crmEmailList) {
  els.crmEmailList.addEventListener("click", (event) => {
    const item = event.target.closest("[data-crm-index]");
    if (!item) return;
    const index = Number(item.dataset.crmIndex);
    if (!Number.isNaN(index)) {
      selectCrmEmail(index);
    }
  });
}

if (els.crmRefreshBtn) {
  els.crmRefreshBtn.addEventListener("click", () => refreshCrmInbox());
}

async function toggleMockMode() {
  if (!els.crmMockToggleBtn) return;
  
  const newState = !crmState.mockMode;
  els.crmMockToggleBtn.disabled = true;
  setCrmStatus(newState ? "Включаем тестовые данные..." : "Выключаем тестовые данные...");
  
  try {
    const response = await fetch(`${getApiBaseUrl()}/emails/mock-mode`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({ enabled: newState }),
    });
    
    if (!response.ok) {
      throw new Error("Не удалось переключить режим тестовых данных");
    }
    
    const data = await response.json();
    crmState.mockMode = data.mock_mode;
    
    // Update button appearance
    if (els.crmMockToggleBtn) {
      els.crmMockToggleBtn.textContent = crmState.mockMode ? "✅ Тестовые данные ВКЛ" : "🧪 Тестовые данные";
      els.crmMockToggleBtn.style.background = crmState.mockMode 
        ? "rgba(0, 255, 128, 0.2)" 
        : "rgba(0, 0, 0, 0.8)";
    }
    
    setCrmStatus(data.message || (crmState.mockMode ? "Тестовые данные включены" : "Тестовые данные выключены"), "success");
    log(`🧪 ${data.message || (crmState.mockMode ? "Mock mode включен" : "Mock mode выключен")}`);
    
    // Refresh inbox to show mock or real emails
    await refreshCrmInbox();
  } catch (error) {
    console.error(error);
    setCrmStatus(error.message || "Ошибка переключения режима", "error");
    log(`❌ Ошибка mock mode: ${error.message || error}`);
  } finally {
    if (els.crmMockToggleBtn) {
      els.crmMockToggleBtn.disabled = false;
    }
  }
}

async function checkMockModeStatus() {
  try {
    const response = await fetch(`${getApiBaseUrl()}/emails/mock-mode`);
    if (response.ok) {
      const data = await response.json();
      crmState.mockMode = data.mock_mode;
      
      if (els.crmMockToggleBtn) {
        els.crmMockToggleBtn.textContent = crmState.mockMode ? "✅ Тестовые данные ВКЛ" : "🧪 Тестовые данные";
        els.crmMockToggleBtn.style.background = crmState.mockMode 
          ? "rgba(0, 255, 128, 0.2)" 
          : "rgba(0, 0, 0, 0.8)";
      }
    }
  } catch (error) {
    console.warn("Failed to check mock mode status:", error);
  }
}

if (els.crmMockToggleBtn) {
  els.crmMockToggleBtn.addEventListener("click", toggleMockMode);
  // Check initial status on load
  checkMockModeStatus();
}

if (els.crmRelevantOnly) {
  els.crmRelevantOnly.addEventListener("change", () => {
    crmState.relevantOnly = !!els.crmRelevantOnly.checked;
    refreshCrmInbox();
  });
}

if (els.crmEmailLimit) {
  els.crmEmailLimit.addEventListener("change", () => {
    const value = parseInt(els.crmEmailLimit.value, 10);
    if (!Number.isNaN(value) && value >= 5) {
      crmState.limit = Math.min(Math.max(value, 5), 50);
      refreshCrmInbox();
    }
  });
}

if (els.crmClassifyBtn) {
  els.crmClassifyBtn.addEventListener("click", handleCrmClassification);
}

if (els.crmProposalBtn) {
  els.crmProposalBtn.addEventListener("click", handleCrmProposal);
}

if (els.crmCopyProposalBtn) {
  els.crmCopyProposalBtn.addEventListener("click", handleCrmCopyProposal);
}

if (els.crmSendBtn) {
  els.crmSendBtn.addEventListener("click", handleCrmSend);
}

attachCrmDraftListeners();

if (typeof MutationObserver !== "undefined") {
  const retroObserver = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach((node) => {
        if (!(node instanceof HTMLElement)) return;
        attachRetroSoundEffects(node);
      });
    }
  });

  const startRetroObserver = () => {
    if (!document.body) return;
    retroObserver.observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      attachRetroSoundEffects();
      startRetroObserver();
    });
  } else {
    attachRetroSoundEffects();
    startRetroObserver();
  }
} else {
  attachRetroSoundEffects();
}

try {
  if (typeof AudioContext !== "undefined") {
  startHum();
  }
} catch (error) {
  console.warn("Browser does not support AudioContext", error);
}

setCrmStatus("Бот готов к работе", "info");
refreshCrmInbox();

// ========== 1C INTEGRATION FUNCTIONS ==========

function addOnecItem(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const itemDiv = document.createElement("div");
  itemDiv.style.cssText = "display: flex; gap: 6px; margin-bottom: 4px; align-items: center;";
  itemDiv.innerHTML = `
    <input type="text" placeholder="Артикул" style="width: 100px; font-size: 0.7rem;" class="onec-item-sku" />
    <input type="text" placeholder="Описание" style="flex: 1; font-size: 0.7rem;" class="onec-item-desc" required />
    <input type="number" placeholder="Кол-во" step="0.01" style="width: 80px; font-size: 0.7rem;" class="onec-item-qty" required />
    <input type="text" placeholder="Ед." style="width: 60px; font-size: 0.7rem;" class="onec-item-unit" />
    <input type="number" placeholder="Цена" step="0.01" style="width: 100px; font-size: 0.7rem;" class="onec-item-price" required />
    <button onclick="removeOnecItem(this)" style="font-size: 0.7rem; padding: 2px 6px;">✖</button>
  `;
  container.appendChild(itemDiv);
}

function removeOnecItem(button) {
  button.parentElement.remove();
}

function collectOnecItems(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return [];

  const items = [];
  const rows = container.querySelectorAll("div");
  
  rows.forEach((row) => {
    const desc = row.querySelector(".onec-item-desc")?.value?.trim();
    const qty = parseFloat(row.querySelector(".onec-item-qty")?.value);
    const price = parseFloat(row.querySelector(".onec-item-price")?.value);
    
    if (!desc || !qty || !price) return;

    items.push({
      article: row.querySelector(".onec-item-sku")?.value?.trim() || undefined,
      description: desc,
      quantity: qty,
      unit: row.querySelector(".onec-item-unit")?.value?.trim() || undefined,
      price: price,
    });
  });

  return items;
}

async function handleCreateInvoice() {
  if (!els.onecCreateInvoiceBtn) return;

  const leadId = els.onecLeadId?.value;
  const customerName = els.onecCustomerName?.value?.trim();
  const items = collectOnecItems("onecInvoiceItems");

  if (!leadId || !customerName) {
    if (els.onecInvoiceStatus) {
      els.onecInvoiceStatus.textContent = "❌ Заполните ID сделки и название клиента";
      els.onecInvoiceStatus.style.color = "rgb(255, 0, 0)";
    }
    return;
  }

  if (items.length === 0) {
    if (els.onecInvoiceStatus) {
      els.onecInvoiceStatus.textContent = "❌ Добавьте хотя бы один товар";
      els.onecInvoiceStatus.style.color = "rgb(255, 0, 0)";
    }
    return;
  }

  els.onecCreateInvoiceBtn.disabled = true;
  if (els.onecInvoiceStatus) {
    els.onecInvoiceStatus.textContent = "Создаём счёт...";
    els.onecInvoiceStatus.style.color = "var(--ui-color)";
  }

  try {
    const payload = {
      lead_id: parseInt(leadId, 10),
      crm_contact_id: els.onecContactId?.value ? parseInt(els.onecContactId.value, 10) : undefined,
      customer_name: customerName,
      customer_bin: els.onecCustomerBin?.value?.trim() || undefined,
      currency: els.onecInvoiceCurrency?.value || "KZT",
      due_date: els.onecInvoiceDueDate?.value || undefined,
      items: items,
    };

    const result = await onecClient.createInvoice(payload);
    const invoiceNumber = result.invoice?.invoiceNumber || result.invoice?.docNumber || "N/A";

    if (els.onecInvoiceStatus) {
      els.onecInvoiceStatus.textContent = `✅ Счёт создан: ${invoiceNumber}`;
      els.onecInvoiceStatus.style.color = "rgb(0, 255, 128)";
    }

    log(`✅ Счёт создан в 1С: ${invoiceNumber} (сделка ${leadId})`);

    const pdfRef = result.invoice?.pdfRef || result.invoice?.uuid;
    if (pdfRef) {
      const downloadBtn = document.createElement("button");
      downloadBtn.textContent = "📥 Скачать PDF";
      downloadBtn.style.cssText = "font-size: 0.7rem; padding: 2px 6px; margin-left: 8px;";
      downloadBtn.onclick = async () => {
        try {
          const blob = await onecClient.getInvoicePdf(pdfRef);
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `invoice_${invoiceNumber}.pdf`;
          a.click();
          window.URL.revokeObjectURL(url);
        } catch (error) {
          log(`❌ Ошибка скачивания PDF: ${error.message}`);
        }
      };
      if (els.onecInvoiceStatus) {
        els.onecInvoiceStatus.appendChild(downloadBtn);
      }
    }
  } catch (error) {
    console.error(error);
    if (els.onecInvoiceStatus) {
      els.onecInvoiceStatus.textContent = `❌ Ошибка: ${error.message}`;
      els.onecInvoiceStatus.style.color = "rgb(255, 0, 0)";
    }
    log(`❌ Ошибка создания счёта: ${error.message || error}`);
  } finally {
    if (els.onecCreateInvoiceBtn) {
      els.onecCreateInvoiceBtn.disabled = false;
    }
  }
}

async function handleCreateFulfillment() {
  if (!els.onecCreateFulfillmentBtn) return;

  const leadId = els.onecLeadId?.value;
  const customerName = els.onecCustomerName?.value?.trim();
  const items = collectOnecItems("onecFulfillmentItems");

  if (!leadId || !customerName) {
    if (els.onecFulfillmentStatus) {
      els.onecFulfillmentStatus.textContent = "❌ Заполните ID сделки и название клиента";
      els.onecFulfillmentStatus.style.color = "rgb(255, 0, 0)";
    }
    return;
  }

  if (items.length === 0) {
    if (els.onecFulfillmentStatus) {
      els.onecFulfillmentStatus.textContent = "❌ Добавьте хотя бы один товар";
      els.onecFulfillmentStatus.style.color = "rgb(255, 0, 0)";
    }
    return;
  }

  els.onecCreateFulfillmentBtn.disabled = true;
  if (els.onecFulfillmentStatus) {
    els.onecFulfillmentStatus.textContent = "Создаём накладную и акт...";
    els.onecFulfillmentStatus.style.color = "var(--ui-color)";
  }

  try {
    const payload = {
      lead_id: parseInt(leadId, 10),
      crm_contact_id: els.onecContactId?.value ? parseInt(els.onecContactId.value, 10) : undefined,
      customer_name: customerName,
      customer_bin: els.onecCustomerBin?.value?.trim() || undefined,
      delivery_address: els.onecDeliveryAddress?.value?.trim() || undefined,
      items: items,
    };

    const result = await onecClient.createFulfillment(payload);
    const waybillNumber = result.documents?.waybillNumber || "N/A";
    const actNumber = result.documents?.actNumber || "N/A";

    if (els.onecFulfillmentStatus) {
      els.onecFulfillmentStatus.textContent = `✅ Накладная: ${waybillNumber}, Акт: ${actNumber}`;
      els.onecFulfillmentStatus.style.color = "rgb(0, 255, 128)";
    }

    log(`✅ Накладная и акт созданы в 1С: ${waybillNumber} / ${actNumber} (сделка ${leadId})`);

    const pdfRef = result.documents?.pdfRef || result.documents?.uuid;
    if (pdfRef) {
      const downloadBtn = document.createElement("button");
      downloadBtn.textContent = "📥 Скачать PDF";
      downloadBtn.style.cssText = "font-size: 0.7rem; padding: 2px 6px; margin-left: 8px;";
      downloadBtn.onclick = async () => {
        try {
          const blob = await onecClient.getRealizationPdf(pdfRef);
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `fulfillment_${waybillNumber}.pdf`;
          a.click();
          window.URL.revokeObjectURL(url);
        } catch (error) {
          log(`❌ Ошибка скачивания PDF: ${error.message}`);
        }
      };
      if (els.onecFulfillmentStatus) {
        els.onecFulfillmentStatus.appendChild(downloadBtn);
      }
    }
  } catch (error) {
    console.error(error);
    if (els.onecFulfillmentStatus) {
      els.onecFulfillmentStatus.textContent = `❌ Ошибка: ${error.message}`;
      els.onecFulfillmentStatus.style.color = "rgb(255, 0, 0)";
    }
    log(`❌ Ошибка создания накладной/акта: ${error.message || error}`);
  } finally {
    if (els.onecCreateFulfillmentBtn) {
      els.onecCreateFulfillmentBtn.disabled = false;
    }
  }
}

// Make functions global for onclick handlers
window.addOnecItem = addOnecItem;
window.removeOnecItem = removeOnecItem;

// Event listeners for 1C buttons
if (els.onecCreateInvoiceBtn) {
  els.onecCreateInvoiceBtn.addEventListener("click", handleCreateInvoice);
}

if (els.onecCreateFulfillmentBtn) {
  els.onecCreateFulfillmentBtn.addEventListener("click", handleCreateFulfillment);
}

if (document.getElementById("onecAddInvoiceItem")) {
  document.getElementById("onecAddInvoiceItem").addEventListener("click", () => addOnecItem("onecInvoiceItems"));
}

if (document.getElementById("onecAddFulfillmentItem")) {
  document.getElementById("onecAddFulfillmentItem").addEventListener("click", () => addOnecItem("onecFulfillmentItems"));
}
