# Italian source copy — wording review (2026-11-17)

Scope: `apps/web/src/locales/*.ts`, with attention to daily navigation, Library, document details, Sources, semantic search, mail, workflows, people, and background jobs. This is a source-copy review; it is not a claim that a native speaker has read every screen on a device.

Findings corrected:

- The language picker still called Italian a preview although every screen now has Italian messages.
- The failed scan-upload message had an unclear pronoun and verb agreement; it now distinguishes the saved scan from the upload that will be retried.
- Sources used an awkward phrase about what happens to stored files, an English “self-hosted” fragment, and “access token” where the stored secret is a refresh token.
- Semantic-search copy changed grammatical subject mid-sentence and made the 15-minute retry sound like an instruction to the person.
- Mail-rule and workflow descriptions were stilted; job and page errors used the vague “Non ha funzionato.”
- The People introduction omitted that filing objects can now be shared. The document-sharing introduction also implied all filing remained private, although individual filing objects can be shared.

- Share-link revocation gave the link itself the ability to download; the revised sentence names the real effect. Saved views were called both “viste salvate” and “ricerche salvate”; they now use the latter consistently. The Shared with me heading and the learning-model status also had literal or stilted phrasing.

English values were compared with the committed versions using the TypeScript AST; all English message objects in the edited locale files are unchanged. TypeScript and production PWA build results are recorded in the commit checkpoint. A running-browser review with an Italian-speaking user remains for the R4 language gate.
