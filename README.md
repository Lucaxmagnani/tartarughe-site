# Le Tartarughe — guest guide (auto-updating)

Mini-sito guest de "Le Tartarughe" (Via della Reginella 2, Roma) con sezione
**"During your stay"** aggiornata automaticamente ogni mattina: allerte
scioperi trasporti (fonte: osservatorio MIT), ingressi gratuiti ed eventi in zona.

## Struttura

```
site/                        ← il sito pubblicato su Netlify
  index.html …               ← pagine della guida
  stay.html                  ← "During your stay" (legge events.json)
  events.json                ← DATI: rigenerato ogni giorno dalla Action
scripts/update_events.py     ← raccoglie scioperi dal RSS MIT + pulisce eventi scaduti
.github/workflows/update-events.yml  ← cron giornaliero 06:30 (ora di Roma)
```

## Setup una tantum (10 minuti)

1. **GitHub** — crea un account su github.com (se non ce l'hai) → "New repository"
   → nome `tartarughe-site`, private o public → carica il contenuto di questa
   cartella (o `git push` se usi git).
2. **Netlify** — dashboard Netlify → il sito `tartarughe` → *Site configuration*
   → *Build & deploy* → *Link repository* → scegli GitHub → repo `tartarughe-site`
   → **Publish directory: `site`** (nessun build command). Da ora ogni commit
   rideploya il sito da solo.
3. **Fine.** La Action gira ogni mattina alle 06:30: se ci sono scioperi
   nuovi o voci scadute, committa `events.json` e Netlify pubblica. Zero
   interventi manuali. (Nella tab *Actions* del repo c'è anche il bottone
   "Run workflow" per forzare un aggiornamento.)

## Cosa è automatico e cosa no (v1)

- ✅ **Allerte scioperi**: 100% automatiche dal RSS ufficiale MIT (filtrate:
  trasporti, nazionali o Lazio/Roma, prossimi 30 giorni, EN+IT).
- ✅ **Scadenze**: eventi/mostre/gratuità con data `to` passata spariscono da soli.
- ✍️ **Eventi e ingressi gratuiti**: curati a mano in `site/events.json`
  (aggiungi una voce con `from`/`to`, testi EN/IT, distanza e link mappa).
  L'automazione completa di questa parte (LLM multi-fonte) è la feature Pro
  del SaaS Home Sapiens — vedi `HomeSapiens_GuestGuide_SaaS_Spec.md`.

## Nota

`stay.html` contiene una copia embedded dei dati come fallback se il fetch di
`events.json` fallisce (es. apertura in locale). La fonte di verità è il JSON.
