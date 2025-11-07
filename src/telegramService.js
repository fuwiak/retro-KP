// Telegram Notification Service
// Sends notifications and drafts for review with approval buttons

/**
 * Send notification to Telegram
 */
export async function sendTelegramNotification(botToken, chatId, message, options = {}) {
  try {
    const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
    
    // Create inline keyboard with approval buttons
    const keyboard = options.showApproval ? {
      inline_keyboard: [
        [
          { text: '✅ Approve', callback_data: `approve_${options.messageId || Date.now()}` },
          { text: '❌ Reject', callback_data: `reject_${options.messageId || Date.now()}` }
        ]
      ]
    } : null;
    
    const payload = {
      chat_id: chatId,
      text: message,
      parse_mode: 'HTML',
      ...(keyboard && { reply_markup: keyboard })
    };
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.description || `Telegram API error: ${response.statusText}`);
    }
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('Telegram notification error:', error);
    throw error;
  }
}

/**
 * Send file to Telegram
 */
export async function sendTelegramFile(botToken, chatId, file, caption = '', options = {}) {
  try {
    const formData = new FormData();
    formData.append('chat_id', chatId);
    formData.append('caption', caption);
    formData.append('document', file);
    
    if (options.showApproval) {
      const keyboard = JSON.stringify({
        inline_keyboard: [
          [
            { text: '✅ Approve', callback_data: `approve_${options.messageId || Date.now()}` },
            { text: '❌ Reject', callback_data: `reject_${options.messageId || Date.now()}` }
          ]
        ]
      });
      formData.append('reply_markup', keyboard);
    }
    
    const url = `https://api.telegram.org/bot${botToken}/sendDocument`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.description || `Telegram API error: ${response.statusText}`);
    }
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('Telegram file send error:', error);
    throw error;
  }
}

/**
 * Send draft for review
 */
export async function sendDraftForReview(botToken, chatId, data, translations, files = []) {
  try {
    const messageId = Date.now();
    
    // Format message
    const message = formatReviewMessage(data, translations);
    
    // Send main message
    await sendTelegramNotification(botToken, chatId, message, {
      showApproval: true,
      messageId: messageId
    });
    
    // Send files if any
    for (const file of files) {
      await sendTelegramFile(botToken, chatId, file.file, file.caption, {
        showApproval: true,
        messageId: messageId
      });
    }
    
    return messageId;
  } catch (error) {
    console.error('Error sending draft for review:', error);
    throw error;
  }
}

/**
 * Format review message
 */
function formatReviewMessage(data, translations) {
  let message = '<b>📐 Drawing Analysis Draft</b>\n\n';
  
  message += '<b>Extracted Data:</b>\n';
  message += `Materials: ${translations.materials.join(', ') || 'N/A'}\n`;
  message += `Standards: ${translations.standards.join(', ') || 'N/A'}\n`;
  message += `Surface Roughness: Ra ${data.raValues.join(', ') || 'N/A'}\n`;
  message += `Fits: ${data.fits.join(', ') || 'N/A'}\n`;
  message += `Heat Treatment: ${translations.heatTreatment.join(', ') || 'N/A'}\n\n`;
  
  message += '<i>Please review and approve or reject this draft.</i>';
  
  return message;
}

/**
 * Test Telegram connection
 */
export async function testTelegramConnection(botToken, chatId) {
  try {
    await sendTelegramNotification(botToken, chatId, '✅ Connection test successful!');
    return true;
  } catch (error) {
    throw new Error(`Telegram connection failed: ${error.message}`);
  }
}

