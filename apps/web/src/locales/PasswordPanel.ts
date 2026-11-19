import { defineMessages } from "../i18n";

export default defineMessages({
  mismatch: "The two new passwords are different",
  changed: "Password changed. Your other devices were signed out, your API tokens and agents were disconnected, and your share links and bundles were revoked.",
  warning: "Changing your password signs out your other devices, disconnects your API tokens and agents, and revokes your share links and bundles.",
  changeError: "Could not change your password",
  heading: "Password",
  current: "Current password",
  next: "New password",
  nextHint: "At least 12 characters",
  repeat: "Repeat new password",
  changing: "Changing…",
  change: "Change password",
}, {
  mismatch: "Le due nuove password non coincidono",
  changed: "Password cambiata. Gli altri dispositivi sono stati disconnessi, così come i tuoi token API e i tuoi agenti, e i tuoi link e pacchetti condivisi sono stati revocati.",
  warning: "Cambiare la password disconnette gli altri dispositivi, i token API e gli agenti, e revoca i tuoi link e pacchetti condivisi.",
  changeError: "Impossibile cambiare la password",
  heading: "Password",
  current: "Password attuale",
  next: "Nuova password",
  nextHint: "Almeno 12 caratteri",
  repeat: "Ripeti la nuova password",
  changing: "Modifica in corso…",
  change: "Cambia password",
});
