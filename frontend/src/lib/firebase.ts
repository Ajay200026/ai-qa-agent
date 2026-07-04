import { initializeApp, getApps, getApp, type FirebaseApp } from "firebase/app";
import { getAnalytics, isSupported, type Analytics } from "firebase/analytics";
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  onIdTokenChanged,
  type Auth,
  type User as FirebaseUser,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let analytics: Analytics | null = null;

function ensureFirebaseApp(): FirebaseApp {
  if (!app) {
    app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
    if (typeof window !== "undefined" && firebaseConfig.measurementId) {
      void isSupported().then((supported) => {
        if (supported && app) {
          analytics = getAnalytics(app);
        }
      });
    }
  }
  return app;
}

/** Lazily initialize Firebase only in the browser (avoids SSR vendor-chunk errors). */
export function getFirebaseAuth(): Auth {
  if (typeof window === "undefined") {
    throw new Error("Firebase auth is only available in the browser");
  }
  if (!auth) {
    auth = getAuth(ensureFirebaseApp());
  }
  return auth!;
}

export async function firebaseRegister(email: string, password: string): Promise<FirebaseUser> {
  const credential = await createUserWithEmailAndPassword(getFirebaseAuth(), email, password);
  return credential.user;
}

export async function firebaseLogin(email: string, password: string): Promise<FirebaseUser> {
  const credential = await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
  return credential.user;
}

export async function firebaseLogout(): Promise<void> {
  await signOut(getFirebaseAuth());
}

export async function getFirebaseIdToken(forceRefresh = false): Promise<string | null> {
  const user = getFirebaseAuth().currentUser;
  if (!user) return null;
  return user.getIdToken(forceRefresh);
}

/** Keep localStorage token in sync when Firebase refreshes the ID token (~hourly). */
export function subscribeIdTokenRefresh(
  onToken: (token: string | null) => void
): () => void {
  return onIdTokenChanged(getFirebaseAuth(), async (user) => {
    if (!user) {
      onToken(null);
      return;
    }
    onToken(await user.getIdToken());
  });
}

export { onAuthStateChanged, type FirebaseUser };
