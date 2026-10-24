import test from "node:test";
import assert from "node:assert/strict";

import { sanitizeSvg } from "../../app/lib/sanitizeSvg.ts";

test("keeps ordinary svg", () => {
  const svg = '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#fff"/><use href="#a"/></svg>';
  assert.equal(sanitizeSvg(svg), svg);
});

test("removes scripts, foreignObject and event handlers in every quoting style", () => {
  const dirty = [
    '<svg onload="alert(1)"><script>alert(1)</script></svg>',
    "<svg onload='alert(1)'></svg>",
    "<svg onload=alert(1)></svg>",
    '<svg/onload=alert(1)></svg>',
    '<svg><foreignObject><body onload="x()"></body></foreignObject></svg>',
    '<svg><iframe src="https://evil.example"></iframe></svg>',
    '<svg><scr<script>ipt>alert(1)</scr</script>ipt></svg>',
  ];
  for (const svg of dirty) {
    const clean = sanitizeSvg(svg);
    assert.ok(!/<script|<iframe|foreignobject|\son\w+\s*=|\/on\w+\s*=/i.test(clean), `still dirty: ${clean}`);
  }
});

test("only same-document or image data hrefs survive", () => {
  assert.ok(!sanitizeSvg('<a href="javascript:alert(1)">x</a>').includes("javascript"));
  assert.ok(!sanitizeSvg('<a xlink:href="java&#115;cript:alert(1)">x</a>').includes("href"));
  assert.ok(!sanitizeSvg('<use href="https://evil.example/x.svg#a"/>').includes("evil"));
  assert.ok(sanitizeSvg('<image href="data:image/png;base64,AAAA"/>').includes("data:image/png"));
  assert.ok(!sanitizeSvg('<image href="data:text/html;base64,AAAA"/>').includes("data:text"));
});
