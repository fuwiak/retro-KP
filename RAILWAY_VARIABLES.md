# Railway Variables Mapping

## ❌ Problem: Nazwy zmiennych w Railway nie pasują do kodu

### Railway używa: `AMOCRM_*`
### Kod oczekuje: `AMO_*`

## ✅ Rozwiązanie: Dodaj te zmienne w Railway

### Wymagane zmienne (muszą być w Railway):

#### IMAP (Email)
- ✅ `IMAP_SERVER` - masz
- ✅ `IMAP_PORT` - masz  
- ✅ `IMAP_USER` - masz (kod obsługuje też `IMAP_USERNAME`)
- ✅ `IMAP_PASSWORD` - masz
- ⚠️ `IMAP_FOLDER` - opcjonalne (domyślnie "INBOX")

#### amoCRM
- ❌ `AMO_BASE_URL` - **BRAKUJE!** (Railway ma `AMOCRM_SUBDOMAIN`, ale kod potrzebuje pełnego URL)
- ❌ `AMO_ACCESS_TOKEN` - **BRAKUJE!** (Railway ma `AMOCRM_ACCESS_TOKEN`)
- ❌ `AMO_CLIENT_ID` - **BRAKUJE!** (Railway ma `AMOCRM_CLIENT_ID`)
- ❌ `AMO_CLIENT_SECRET` - **BRAKUJE!** (Railway ma `AMOCRM_CLIENT_SECRET`)
- ❌ `AMO_REDIRECT_URI` - **BRAKUJE!** (Railway ma `AMOCRM_REDIRECT_URI`)
- ❌ `AMO_REFRESH_TOKEN` - **BRAKUJE!**
- ❌ `AMO_PIPELINE_ID` - **BRAKUJE!**
- ❌ `AMO_LEAD_STATUS_ID` - **BRAKUJE!**
- ❌ `AMO_RESPONSIBLE_USER_ID` - **BRAKUJE!**
- ⚠️ `AMO_PIPELINE_SALES_ID` - opcjonalne
- ⚠️ `AMO_PIPELINE_NKU_ID` - opcjonalne
- ⚠️ `AMO_PIPELINE_SERVICES_ID` - opcjonalne
- ⚠️ `AMO_CP_SENT_STATUS_ID` - opcjonalne

#### Groq
- ✅ `GROQ_API_KEY` - masz

#### 1C Integration (opcjonalne)
- ⚠️ `ONEC_BASE_URL`
- ⚠️ `ONEC_API_KEY`
- ⚠️ `ONEC_AUTH_HEADER`

#### WhatsApp (opcjonalne)
- ⚠️ `WHATSAPP_360DIALOG_API_KEY`
- ⚠️ `WHATSAPP_CLOUD_API_TOKEN`
- ⚠️ `WHATSAPP_MANAGER_PHONES`

## 🔧 Co zrobić:

### Opcja 1: Dodaj zmienne z prefiksem `AMO_` (zalecane)
Dodaj w Railway te same wartości, ale z nazwami `AMO_*`:

```
AMO_BASE_URL=https://{AMOCRM_SUBDOMAIN}.amocrm.ru
AMO_ACCESS_TOKEN={wartość z AMOCRM_ACCESS_TOKEN}
AMO_CLIENT_ID={wartość z AMOCRM_CLIENT_ID}
AMO_CLIENT_SECRET={wartość z AMOCRM_CLIENT_SECRET}
AMO_REDIRECT_URI={wartość z AMOCRM_REDIRECT_URI}
AMO_REFRESH_TOKEN={wartość z AMOCRM_REFRESH_TOKEN lub pusta}
AMO_PIPELINE_ID={ID воронки}
AMO_LEAD_STATUS_ID={ID статуса}
AMO_RESPONSIBLE_USER_ID={ID ответственного}
```

### Opcja 2: Zmień kod, aby obsługiwał oba prefiksy
Mogę zmodyfikować kod, aby automatycznie mapował `AMOCRM_*` na `AMO_*`.

