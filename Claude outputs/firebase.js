// RagGita — Firebase setup for Expo (works in Expo Go today)
//
// Install:
//   npx expo install firebase @react-native-async-storage/async-storage
//
// Kaam kaise karta hai:
//   Abhi anonymous sign-in — Expo Go me chalta hai, zero native code, aur
//   asli Firebase uid + ID token deta hai. Backend usse verify karta hai.
//
//   Baad me dev build pe Google add karoge toh linkWithCredential se YAHI
//   account upgrade ho jayega — uid wahi rahega, history apne aap saath
//   aayegi. Isliye yeh kaam dobara nahi likhna padega.

import { initializeApp, getApps } from 'firebase/app';
import {
  initializeAuth,
  getAuth,
  signInAnonymously,
  onAuthStateChanged,
  getReactNativePersistence,
} from 'firebase/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Firebase console -> Project settings -> General -> Your apps -> Web app
// Yeh values secret NAHI hain; client me rehna hi hota hai.
const firebaseConfig = {
  apiKey: 'REPLACE_ME',
  authDomain: 'REPLACE_ME.firebaseapp.com',
  projectId: 'REPLACE_ME',
  storageBucket: 'REPLACE_ME.firebasestorage.app',
  messagingSenderId: 'REPLACE_ME',
  appId: 'REPLACE_ME',
};

const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);

// initializeAuth + AsyncStorage zaroori hai. Bina iske React Native me
// session memory me rehti hai — app band karte hi user logged out, aur
// har baar naya uid. Yeh sabse aam Expo + Firebase bug hai.
let auth;
try {
  auth = initializeAuth(app, {
    persistence: getReactNativePersistence(AsyncStorage),
  });
} catch {
  // Fast refresh pe dobara initialize ho sakta hai
  auth = getAuth(app);
}

export { auth };

/** App khulte hi ek baar call karo. Sign-in hone tak rukta hai. */
export function ensureSignedIn() {
  return new Promise((resolve, reject) => {
    const stop = onAuthStateChanged(
      auth,
      async (user) => {
        if (user) {
          stop();
          resolve(user);
          return;
        }
        try {
          const cred = await signInAnonymously(auth);
          stop();
          resolve(cred.user);
        } catch (e) {
          stop();
          reject(e);
        }
      },
      (e) => {
        stop();
        reject(e);
      }
    );
  });
}

/** Abhi ka ID token. SDK khud refresh karta hai, toh har request pe call karo. */
export async function idToken() {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken();   // cached; expire hone pe khud refresh
}

export function currentUid() {
  return auth.currentUser?.uid ?? null;
}

export function isAnonymous() {
  return auth.currentUser?.isAnonymous ?? true;
}

// ── Dev build pe jaane ke baad ───────────────────────────────
// Google sign-in add karna ho toh sirf yeh function chahiye. Anonymous
// account upgrade ho jaata hai, uid badalta nahi, history saath aati hai.
//
// import { GoogleAuthProvider, linkWithCredential, signInWithCredential } from 'firebase/auth';
//
// export async function upgradeToGoogle(googleIdToken) {
//   const credential = GoogleAuthProvider.credential(googleIdToken);
//   try {
//     const res = await linkWithCredential(auth.currentUser, credential);
//     return res.user;                    // wahi uid, ab Google se juda
//   } catch (e) {
//     if (e.code === 'auth/credential-already-in-use') {
//       // Iss Google account ka pehle se apna uid hai (doosre phone se).
//       // Us account me sign in karo, phir anonymous wali history ko
//       // backend ke POST /link se le aao.
//       const res = await signInWithCredential(auth, credential);
//       return res.user;
//     }
//     throw e;
//   }
// }
