import { chromium } from "/Users/debotta/dbrepos/ripiano/apps/web/node_modules/@playwright/test/index.mjs";
const b = await chromium.launch({channel:"chrome"}); console.log(b.version()); await b.close();
