# Public provider-catalog check — 12 September 2026

This is documentation verification, **not** authenticated access, pricing approval or a successful model call.

- The [official Groq model catalog](https://console.groq.com/docs/models) lists `openai/gpt-oss-120b` and `openai/gpt-oss-20b` as production models, while Qwen 3.6/3.8 27B are preview models. The new-install/Cloud default is now `openai/gpt-oss-120b`, not a preview model. Existing explicit custom models are retained. Owner must recheck pricing, their account's eligibility and budget before enabling operator-funded use.
- The same catalog still lists Llama 3.1 8B and Llama 3.3 70B for Enterprise. Their automatic migration was removed: the application cannot infer that a valid saved account-specific model is retired for that customer. An inaccessible model must be tested/configured deliberately; no successful paid access was inferred.
- The [official Gemini catalog](https://ai.google.dev/gemini-api/docs/models) lists Gemini 3.6 Flash as stable, alongside newer variants. Existing Desktop Gemini defaults are not replaced merely because a newer release exists. Cloud's separate text contract remains independently configured/tested.
- The [official Claude catalog](https://platform.claude.com/docs/en/models/overview) lists `claude-sonnet-5`; its existing Desktop identifier was not invented or replaced speculatively.

A documentation listing does not establish quality for a customer's brief, regional/account availability, free entitlement, or agreement to a higher model price. Verify every enabled provider/model with the actual authorized account and recheck image models and model-bound image budget settings. Other optional providers remain configuration/real-service gates. No key, purchase or paid inference was used in this review.
