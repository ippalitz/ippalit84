const LEAD_STEPS = [
  ["vin", "Укажите VIN автомобиля."],
  ["car", "Укажите марку, модель и год."],
  ["part", "Какая деталь нужна?"],
  ["city", "В какой город нужна доставка?"],
  ["phone", "Оставьте телефон для связи."],
];

const OEM_RE = /\b(?:[A-ZА-Я]{0,4}\d[A-ZА-Я0-9]{4,16}|\d{4,12}[- ]?\d{2,8}[- ]?\d{0,6})\b/giu;
const VIN_RE = /\b[A-HJ-NPR-Z0-9]{17}\b/iu;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "GET" && url.pathname === "/") {
      return new Response("OK", { status: 200 });
    }

    if (request.method === "GET" && url.pathname === "/setup") {
      return setupWebhook(request, env);
    }

    if (request.method === "POST" && url.pathname === `/telegram/${env.WEBHOOK_SECRET}`) {
      const update = await request.json();
      ctx.waitUntil(handleUpdate(update, env));
      return new Response("OK", { status: 200 });
    }

    return new Response("Not found", { status: 404 });
  },
};

async function setupWebhook(request, env) {
  const url = new URL(request.url);
  if (url.searchParams.get("key") !== env.SETUP_SECRET) {
    return new Response("Forbidden", { status: 403 });
  }

  const webhookUrl = `${env.WORKER_URL.replace(/\/$/, "")}/telegram/${env.WEBHOOK_SECRET}`;
  const result = await telegram(env, "setWebhook", { url: webhookUrl });
  return json({ webhookUrl, result });
}

async function handleUpdate(update, env) {
  if (update.message) {
    await handleMessage(update.message, env);
    return;
  }

  if (update.callback_query) {
    await handleCallback(update.callback_query, env);
  }
}

async function handleMessage(message, env) {
  const chatId = String(message.chat.id);
  const text = (message.text || "").trim();

  if (text === "/start" || text === "/help") {
    await rememberManager(chatId, env);
    await deleteState(chatId, env);
    await sendMessage(
      env,
      chatId,
      "Здравствуйте! Я помогу проверить наличие автозапчастей.\n\n" +
        "Если вы знаете номер детали/OEM, отправьте его сюда, и я проверю актуальное наличие в Adeo.\n\n" +
        "Если номер неизвестен, нажмите «Не знаю номер детали» — я соберу данные для менеджера.",
      mainKeyboard(),
    );
    return;
  }

  if (text === "Проверить по номеру/OEM") {
    await deleteState(chatId, env);
    await sendMessage(env, chatId, "Отправьте номер детали/OEM одним сообщением. Например: 2108-3501800", mainKeyboard());
    return;
  }

  if (text === "Не знаю номер детали") {
    await saveState(chatId, env, { mode: "lead", step: 0, data: userInfo(message) });
    await sendMessage(env, chatId, LEAD_STEPS[0][1], leadKeyboard());
    return;
  }

  if (text === "Отменить заявку") {
    await deleteState(chatId, env);
    await sendMessage(env, chatId, "Заявку отменил. Можете отправить номер детали/OEM.", mainKeyboard());
    return;
  }

  const state = await getState(chatId, env);
  if (state?.mode === "lead") {
    await handleLeadStep(message, state, env);
    return;
  }

  const codes = extractOems(text);
  if (codes.length) {
    for (const code of codes.slice(0, 3)) {
      await sendOffers(message, code, env);
    }
    return;
  }

  await sendMessage(
    env,
    chatId,
    "Не увидел номер детали/OEM. Если номера нет, нажмите «Не знаю номер детали», и я передам заявку менеджеру.",
    mainKeyboard(),
  );
}

async function handleLeadStep(message, state, env) {
  const chatId = String(message.chat.id);
  const step = Number(state.step || 0);
  const [key] = LEAD_STEPS[step];
  state.data[key] = (message.text || "").trim();

  if (step + 1 >= LEAD_STEPS.length) {
    await deleteState(chatId, env);
    const row = {
      created_at: new Date().toISOString(),
      status: "needs_oem",
      ...state.data,
    };
    await saveRecord(env, "lead", row);
    await notifyManager(
      env,
      "Новая заявка: нужно подобрать номер детали/OEM\n\n" +
        `VIN: ${row.vin || ""}\n` +
        `Авто: ${row.car || ""}\n` +
        `Деталь: ${row.part || ""}\n` +
        `Город: ${row.city || ""}\n` +
        `Телефон: ${row.phone || ""}\n` +
        `Telegram: ${row.telegram_username || ""}\n` +
        `Telegram ID: ${row.telegram_id || ""}`,
    );
    await sendMessage(
      env,
      chatId,
      "Заявка принята. Менеджер подберет номер детали/OEM и свяжется с вами.\n\n" +
        "Когда получите номер, отправьте его сюда — я проверю наличие и цены в Adeo.",
      mainKeyboard(),
    );
    return;
  }

  state.step = step + 1;
  await saveState(chatId, env, state);
  await sendMessage(env, chatId, LEAD_STEPS[state.step][1], leadKeyboard());
}

async function sendOffers(message, code, env) {
  const chatId = String(message.chat.id);
  await sendMessage(env, chatId, `Проверяю наличие по номеру ${escapeHtml(code)} в Adeo...`);
  const offers = await searchArticle(code, env);

  if (!offers.length) {
    await sendMessage(env, chatId, `По номеру ${escapeHtml(code)} сейчас не нашел предложений. Менеджер может проверить вручную.`, mainKeyboard());
    await notifyManager(
      env,
      "Клиент проверял номер, предложений нет:\n" +
        `Номер: ${code}\nTelegram ID: ${chatId}\nUsername: ${userInfo(message).telegram_username}`,
    );
    return;
  }

  for (let i = 0; i < offers.slice(0, maxOffers(env)).length; i++) {
    const offer = { ...offers[i], ...userInfo(message) };
    const callbackId = `${chatId}:${code}:${i + 1}`;
    await kvPut(env, `offer:${callbackId}`, offer, 3600);
    await sendMessage(env, chatId, formatOffer(offer, i + 1), {
      inline_keyboard: [[{ text: "Купить", callback_data: `buy:${callbackId}` }]],
    });
  }
}

async function handleCallback(call, env) {
  const data = call.data || "";
  if (!data.startsWith("buy:")) return;

  const callbackId = data.slice(4);
  const offer = await kvGet(env, `offer:${callbackId}`);
  if (!offer) {
    await telegram(env, "answerCallbackQuery", {
      callback_query_id: call.id,
      text: "Предложение устарело. Отправьте номер детали еще раз.",
    });
    return;
  }

  const row = { created_at: new Date().toISOString(), status: "new_purchase", ...offer };
  await saveRecord(env, "purchase", row);
  await notifyManager(
    env,
    "Новая покупка из Telegram\n\n" +
      `Номер запроса: ${row.requested_code || ""}\n` +
      `Позиция: ${row.producer || ""} ${row.code || ""}\n` +
      `Название: ${row.caption || ""}\n` +
      `Цена клиенту: ${row.sell_price || ""} ${row.currency || ""}\n` +
      `Наличие: ${row.rest || ""}\n` +
      `Срок: ${row.delivery || ""}\n` +
      `Склад: ${row.stock || ""}\n` +
      `Telegram: ${row.telegram_username || ""}\n` +
      `Telegram ID: ${row.telegram_id || ""}`,
  );

  await telegram(env, "answerCallbackQuery", { callback_query_id: call.id, text: "Заявка принята" });
  await sendMessage(env, String(call.message.chat.id), "Заявка на покупку принята. Менеджер свяжется с вами для подтверждения и доставки.", mainKeyboard());
}

async function searchArticle(code, env) {
  const brands = parseBrands(await adeoRequest(env, code));
  const offers = [];
  for (const brand of brands.slice(0, maxBrands(env))) {
    const xml = await adeoRequest(env, code, brand);
    offers.push(...parseOffers(xml, code, env));
  }
  return offers.sort(bestScore);
}

async function adeoRequest(env, code, brand = "") {
  const brandXml = brand ? `<brand>${xmlEscape(brand)}</brand><crosses>allow</crosses>` : "";
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?><message><param>` +
    `<action>price</action><login>${xmlEscape(env.ADEO_LOGIN)}</login>` +
    `<password>${xmlEscape(env.ADEO_PASSWORD)}</password><code>${xmlEscape(code)}</code>` +
    brandXml +
    `</param></message>`;

  const body = new URLSearchParams({ xml });
  const response = await fetch(env.ADEO_URL_PRICES || "https://xml.adeo.pro/pricedetails2.php", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body,
  });
  return response.text();
}

function parseBrands(xml) {
  return unique(parseDetails(xml).map((detail) => tag(detail, "producer")).filter(Boolean));
}

function parseOffers(xml, requestedCode, env) {
  return parseDetails(xml)
    .map((detail) => {
      const price = toFloat(tag(detail, "price"));
      if (price <= 0) return null;
      return {
        requested_code: requestedCode,
        producer: tag(detail, "producer"),
        code: tag(detail, "code") || requestedCode,
        caption: tag(detail, "caption"),
        price,
        sell_price: sellPrice(price, env),
        currency: tag(detail, "currency") || "руб",
        rest: toInt(tag(detail, "rest")),
        delivery: tag(detail, "deliveryDisplay") || tag(detail, "delivery"),
        deliverydays: toInt(tag(detail, "deliverydays"), 99),
        region: tag(detail, "RegionName"),
        stock: tag(detail, "stock"),
        refuse: toInt(tag(detail, "PercentRefuse")),
      };
    })
    .filter(Boolean);
}

function parseDetails(xml) {
  return [...String(xml || "").matchAll(/<detail\b[^>]*>([\s\S]*?)<\/detail>/gi)].map((m) => m[1]);
}

function tag(xml, name) {
  const match = String(xml || "").match(new RegExp(`<${name}\\b[^>]*>([\\s\\S]*?)<\\/${name}>`, "i"));
  return decodeXml(match?.[1] || "").trim();
}

function bestScore(a, b) {
  const ak = [a.rest <= 0 ? 1000 : 0, a.deliverydays || 99, a.refuse || 0, a.sell_price || a.price || 0];
  const bk = [b.rest <= 0 ? 1000 : 0, b.deliverydays || 99, b.refuse || 0, b.sell_price || b.price || 0];
  return ak[0] - bk[0] || ak[1] - bk[1] || ak[2] - bk[2] || ak[3] - bk[3];
}

function formatOffer(offer, index) {
  const title = [offer.producer, offer.code].filter(Boolean).join(" ");
  return (
    `<b>${index}. ${escapeHtml(title)}</b>\n` +
    `${escapeHtml(offer.caption)}\n` +
    `Бренд: ${escapeHtml(offer.producer)}\n` +
    `Цена: <b>${escapeHtml(offer.sell_price)} ${escapeHtml(offer.currency || "руб")}</b>\n` +
    `Наличие: ${escapeHtml(offer.rest)}\n` +
    `Срок: ${escapeHtml(offer.delivery || "уточняется")}\n` +
    `Склад/поставщик: ${escapeHtml(offer.stock || offer.region || "уточняется")}`
  );
}

async function sendMessage(env, chatId, text, replyMarkup = null) {
  const payload = { chat_id: chatId, text, parse_mode: "HTML" };
  if (replyMarkup) payload.reply_markup = replyMarkup;
  return telegram(env, "sendMessage", payload);
}

async function notifyManager(env, text) {
  const chatId = env.MANAGER_CHAT_ID || (await kvGet(env, "manager_chat_id"));
  if (chatId) await telegram(env, "sendMessage", { chat_id: String(chatId), text });
}

async function telegram(env, method, payload) {
  const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function saveRecord(env, kind, row) {
  await kvPut(env, `${kind}:${Date.now()}:${crypto.randomUUID()}`, row);
  if (env.STORAGE_WEBHOOK_URL) {
    await fetch(env.STORAGE_WEBHOOK_URL, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ kind, row }),
    }).catch(() => null);
  }
}

async function rememberManager(chatId, env) {
  if (!env.MANAGER_CHAT_ID && !(await kvGet(env, "manager_chat_id"))) {
    await kvPut(env, "manager_chat_id", chatId);
  }
}

async function getState(chatId, env) {
  return kvGet(env, `state:${chatId}`);
}

async function saveState(chatId, env, state) {
  await kvPut(env, `state:${chatId}`, state, 86400);
}

async function deleteState(chatId, env) {
  if (env.BOT_KV) await env.BOT_KV.delete(`state:${chatId}`);
}

async function kvGet(env, key) {
  if (!env.BOT_KV) return null;
  return env.BOT_KV.get(key, "json");
}

async function kvPut(env, key, value, expirationTtl = null) {
  if (!env.BOT_KV) return;
  const options = expirationTtl ? { expirationTtl } : undefined;
  await env.BOT_KV.put(key, JSON.stringify(value), options);
}

function extractOems(text) {
  const vin = text.match(VIN_RE)?.[0]?.toUpperCase();
  return unique(
    [...text.matchAll(OEM_RE)]
      .map((m) => m[0].toUpperCase().replace(/[\s_]+/g, ""))
      .filter((code) => code.length >= 5 && /\d/.test(code) && code !== vin),
  );
}

function userInfo(message) {
  return {
    telegram_id: String(message.from?.id || message.chat.id),
    telegram_username: message.from?.username ? `@${message.from.username}` : "",
  };
}

function mainKeyboard() {
  return {
    keyboard: [["Проверить по номеру/OEM"], ["Не знаю номер детали"]],
    resize_keyboard: true,
  };
}

function leadKeyboard() {
  return { keyboard: [["Отменить заявку"]], resize_keyboard: true };
}

function maxOffers(env) {
  return Number(env.MAX_OFFERS_PER_QUERY || 5);
}

function maxBrands(env) {
  return Number(env.MAX_BRANDS_PER_QUERY || 8);
}

function sellPrice(price, env) {
  const markup = Number(env.MARKUP_PERCENT || 30);
  return Math.ceil((price * (1 + markup / 100)) / 10) * 10;
}

function toInt(value, fallback = 0) {
  const parsed = Number.parseInt(String(value || "").replace(",", "."), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toFloat(value) {
  const parsed = Number.parseFloat(String(value || "").replace(",", "."));
  return Number.isFinite(parsed) ? parsed : 0;
}

function unique(values) {
  return [...new Set(values)];
}

function xmlEscape(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function decodeXml(value) {
  return String(value || "")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&apos;", "'")
    .replaceAll("&amp;", "&");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function json(value) {
  return new Response(JSON.stringify(value, null, 2), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
