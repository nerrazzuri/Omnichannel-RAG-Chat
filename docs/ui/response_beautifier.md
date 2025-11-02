# Response Beautifier (Frontend)

- Normalizes markdown (bullets, ordered lists, code fences) idempotently.
- Renders via react-markdown + remark-gfm with custom CodeBlock (copy button) and table overflow.
- Enable with `NEXT_PUBLIC_RESPONSE_BEAUTIFY=true`.

Files:
- `frontend/src/lib/beautify/index.ts`
- `frontend/src/components/MessageRenderer.tsx`
- `frontend/src/components/CodeBlock.tsx`
- `frontend/src/styles/beautify.css`

Validation:
- Snapshot render mixed content
- A11y: focusable copy button; external links are rel=noopener noreferrer
