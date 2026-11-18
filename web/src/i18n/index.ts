import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en";
import hi from "./hi";

export type Lang = "en" | "hi";
const KEY = "up_lang";

function initial(): Lang {
  try {
    return localStorage.getItem(KEY) === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi } },
  lng: initial(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* private mode */
  }
  void i18n.changeLanguage(lang);
}

export default i18n;
