// RagGita — API client for the Expo app
//
// Ek hi jagah se backend baat karta hai. Har request pe Firebase ID token
// lagta hai, isliye backend ko pata hota hai kaun bol raha hai aur kiski
// chat kiski hai.
//
// LAMBDA_URL apne Function URL se badal dena (trailing slash ke bina).

import AsyncStorage from '@react-native-async-storage/async-storage';
import { idToken, ensureSignedIn } from './firebase';

export const LAMBDA_URL =
  'https://lht7s7xvklyxrd46xwgi22x23i0ofhyn.lambda-url.ap-south-1.on.aws';

const TIMEOUT_MS = 60000;   // Lambda ka timeout 60s hai, usse match

// ── conversation id ─────────────────────────────────────────────
// Device pe yaad rakhte hain taaki app band karke kholne pe wahi chat
// continue ho. Naya chat chahiye toh newConversation() call karo.

const CONV_KEY = 'raggita.convId';
let _convId = null;

export async function conversationId() {
  if (_convId) return _convId;
  _convId = (await AsyncStorage.getItem(CONV_KEY)) || null;
  return _convId;
}

async function setConversationId(id) {
  if (!id || id === _convId) return;
  _convId = id;
  try {
    await AsyncStorage.setItem(CONV_KEY, id);
  } catch {
    // storage fail ho gaya toh bhi chat chalti rahe
  }
}

/** Naya chat shuru karo. Purani chat server pe safe rehti hai. */
export async function newConversation() {
  _convId = null;
  try {
    await AsyncStorage.removeItem(CONV_KEY);
  } catch {}
}

// ── core request ────────────────────────────────────────────────

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
    // 401 ka matlab token purana ho gaya — app ko dobara sign-in karna hai
    this.needsSignIn = status === 401;
  }
}

export { ApiError };

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };

  if (auth) {
    let token = await idToken();
    if (!token) {
      // App start pe ensureSignedIn chhoot gaya, ya session gir gaya
      await ensureSignedIn();
      token = await idToken();
    }
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);

  let res;
  try {
    res = await fetch(`${LAMBDA_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (e) {
    clearTimeout(timer);
    if (e.name === 'AbortError') {
      throw new ApiError('Jawab aane me bahut der lagi. Dobara bhejo.', 0, null);
    }
    throw new ApiError('Internet connection check karo.', 0, null);
  }
  clearTimeout(timer);

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text.slice(0, 300) };
  }

  if (!res.ok) {
    const msg = data?.detail || data?.error || `Server error (${res.status})`;
    throw new ApiError(String(msg), res.status, data);
  }

  return data;
}

// ── chat ────────────────────────────────────────────────────────

/**
 * Ek message bhejo.
 *
 * @param {string} question
 * @param {object} opts
 * @param {string} [opts.lang]       'en' | 'hi' | 'hi-latn'
 * @param {string} [opts.userClass]  chhod do — backend khud detect karta hai
 * @returns {Promise<{answer: string, crisis: boolean, conversationId: string,
 *                    userClass: string, lang: string}>}
 */
export async function sendMessage(question, { lang = 'en', userClass } = {}) {
  const convId = await conversationId();

  const data = await request('/chat', {
    method: 'POST',
    body: {
      question,
      lang,
      ...(userClass ? { user_class: userClass } : {}),
      ...(convId ? { conversation_id: convId } : {}),
    },
  });

  // Pehle message pe server naya conversation_id deta hai — usse pakad lo
  await setConversationId(data.conversation_id);

  return {
    answer: data.answer ?? '',
    crisis: Boolean(data.crisis),
    conversationId: data.conversation_id,
    userClass: data.user_class ?? 'auto',
    lang: data.lang ?? lang,
  };
}

// ── history ─────────────────────────────────────────────────────

/** User ki saari chats — sidebar / history screen ke liye. */
export function listConversations() {
  return request('/conversations');
}

/** Ek chat ke messages — chat kholne pe. */
export function getConversation(id) {
  return request(`/conversations/${encodeURIComponent(id)}`);
}

export async function deleteConversation(id) {
  const out = await request(`/conversations/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
  if (id === (await conversationId())) await newConversation();
  return out;
}

/** Account delete — settings me "Delete my data" ke liye. Wapsi nahi hoti. */
export function deleteMyData() {
  return request('/me', { method: 'DELETE' });
}

// ── anonymous se sign-in pe shift ───────────────────────────────
//
// Sirf tab zaroorat padti hai jab user device-id waali purani build se
// aa raha ho, ya doosre Google account me sign in kar liya ho.
// linkWithCredential se upgrade hua account ka uid wahi rehta hai, toh
// waha yeh bulana hi nahi padta.

export function linkPreviousData(deviceId) {
  return request('/link', { method: 'POST', body: { device_id: deviceId } });
}

// ── health ──────────────────────────────────────────────────────

/** App khulte hi ek baar — server jaga hua hai ya cold start pe hai. */
export function health() {
  return request('/health', { auth: false });
}

/** Server ne sign-in enable kiya hai ya nahi + class list. */
export function serverInfo() {
  return request('/classes', { auth: false });
}
